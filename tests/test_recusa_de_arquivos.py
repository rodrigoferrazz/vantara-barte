from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.dominio import ArquivoRecusado, Destino
from conciliacao.execucao import executar_conciliacao
from tests.arquivos import (
    CABECALHO_ITAU,
    LinhaItau,
    TituloProtheus,
    configuracao_itau,
    escrever_extrato_itau,
    escrever_protheus,
)

_CREDITO = LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00").linha()


def _escrever(pasta: Path, nome: str, *linhas: str) -> None:
    (pasta / nome).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _motivo(recusados: tuple[ArquivoRecusado, ...], nome: str) -> str:
    motivos = {recusado.nome: recusado.motivo for recusado in recusados}
    assert nome in motivos, f"{nome} não foi recusado; recusados: {motivos}"
    return motivos[nome]


@pytest.mark.parametrize(
    ("cabecalho", "linha", "trechos"),
    [
        ("data;historico;documento;valor;tipo;saldo", _CREDITO + ";1.000,00", ["a mais", "saldo"]),
        ("data;historico;valor;tipo", "14/03/2025;PIX RECEBIDO BELTRANO;95,00;C", ["falta", "documento"]),
        ("data;historico;documento;valor_lancamento;tipo", _CREDITO, ["falta", "'valor'", "a mais", "valor_lancamento"]),
        ("historico;data;documento;valor;tipo", "PIX RECEBIDO BELTRANO;14/03/2025;;95,00;C", ["ordem"]),
    ],
)
def test_extrato_com_coluna_diferente_e_recusado_citando_a_diferenca(
    pasta: Path, armazenamento: Armazenamento, cabecalho: str, linha: str, trechos: list[str]
) -> None:
    _escrever(pasta, "itau_cobranca.csv", cabecalho, linha)

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    motivo = _motivo(resultado.arquivos_recusados, "itau_cobranca.csv")
    assert "Itaú" in motivo
    for trecho in trechos:
        assert trecho in motivo
    assert resultado.itens == ()


def test_arquivo_sem_semelhanca_com_nenhum_layout_e_recusado_com_motivo(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    _escrever(pasta, "titulos_outra_unidade.csv", "customer_name,tax_id,amount", "Fulano,123,10.00")
    (pasta / "planilha.xlsx").write_bytes(b"PK\x03\x04\xff\xfe\x00")
    (pasta / "vazio.csv").write_text("", encoding="utf-8")

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert "cabeçalho" in _motivo(resultado.arquivos_recusados, "titulos_outra_unidade.csv")
    assert _motivo(resultado.arquivos_recusados, "planilha.xlsx")
    assert "vazio" in _motivo(resultado.arquivos_recusados, "vazio.csv")
    assert resultado.resumo.arquivos_lidos == ()


@pytest.mark.parametrize(
    ("linha_ruim", "trecho"),
    [
        (LinhaItau("2025-03-15", "PIX RECEBIDO CICLANO", "60,00"), "2025-03-15"),
        (LinhaItau("15/03/2025", "PIX RECEBIDO CICLANO", "60.00"), "60.00"),
        (LinhaItau("31/02/2025", "PIX RECEBIDO CICLANO", "60,00"), "31/02/2025"),
        (LinhaItau("15/03/2025", "PIX RECEBIDO CICLANO", "60,00", tipo="X"), "'X'"),
    ],
)
def test_extrato_com_formato_inesperado_e_recusado_inteiro_sem_processar_parcialmente(
    pasta: Path, armazenamento: Armazenamento, linha_ruim: LinhaItau, trecho: str
) -> None:
    escrever_extrato_itau(pasta, [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00"), linha_ruim])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    motivo = _motivo(resultado.arquivos_recusados, "itau_cobranca.csv")
    assert "linha 3" in motivo
    assert trecho in motivo
    assert resultado.itens == ()
    assert resultado.resumo.lancamentos_novos == 0


def test_protheus_com_valor_em_formato_inesperado_e_recusado_inteiro(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 900201", valor="100,00", nosso_numero="000066600011"),
            TituloProtheus(documento="NF 900202", valor="R$ 200,00"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "100,00", documento="000066600011")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert "R$ 200,00" in _motivo(resultado.arquivos_recusados, "receber_protheus.csv")
    assert resultado.lista_de_baixa == []
    assert len(resultado.fila_de_excecoes) == 1


def test_protheus_com_cnpj_em_formato_inesperado_e_recusado_inteiro(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 900211", valor="100,00", nosso_numero="000066600021"),
            TituloProtheus(documento="NF 900212", valor="200,00", cnpj="10.200.300/0001"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "100,00", documento="000066600021")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert "10.200.300/0001" in _motivo(resultado.arquivos_recusados, "receber_protheus.csv")
    assert resultado.lista_de_baixa == []


def test_extrato_de_banco_sem_adaptador_e_recusado_com_motivo(pasta: Path, armazenamento: Armazenamento) -> None:
    _escrever(pasta, "bradesco_conta.csv", "Data;Lançamento;Dcto.;Crédito (R$);Débito (R$);Saldo (R$)", "14/03/2025;PIX;1;95,00;;95,00")
    configuracao = Configuracao(
        contas=(
            ContaDeExtrato(padrao="itau_cobranca*", banco="itau", conta="1111-1"),
            ContaDeExtrato(padrao="bradesco_*", banco="bradesco", conta="3333-3"),
        )
    )

    resultado = executar_conciliacao(pasta, armazenamento, configuracao)

    motivo = _motivo(resultado.arquivos_recusados, "bradesco_conta.csv")
    assert "bradesco" in motivo
    assert "adaptador" in motivo


def test_extrato_com_nome_fora_da_configuracao_e_recusado_com_motivo(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_extrato_itau(pasta, [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00")], nome="extrato_sem_conta.csv")

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert "configuração" in _motivo(resultado.arquivos_recusados, "extrato_sem_conta.csv")


def test_demais_arquivos_sao_processados_e_a_conferencia_considera_so_os_aceitos(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900301", valor="700,00", nosso_numero="000055500011")])
    escrever_extrato_itau(
        pasta,
        [
            LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "700,00", documento="000055500011"),
            LinhaItau("06/03/2025", "TARIFA", "3,00", tipo="D"),
        ],
        nome="itau_cobranca_marco.csv",
    )
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "PIX RECEBIDO FULANO", "9.999,00")], nome="sem_conta.csv")
    _escrever(pasta, "itau_cobranca_quebrado.csv", CABECALHO_ITAU, "07/03/2025;PIX RECEBIDO CICLANO;;8.888,00;C;extra")

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.resumo.arquivos_lidos == ("itau_cobranca_marco.csv", "receber_protheus.csv")
    assert sorted(r.nome for r in resultado.arquivos_recusados) == ["itau_cobranca_quebrado.csv", "sem_conta.csv"]
    assert len(resultado.lista_de_baixa) == 1
    assert len(resultado.fora_do_escopo) == 1
    assert resultado.fila_de_excecoes == []
    totais = resultado.resumo.totais
    assert sum(t.valor_centavos for t in totais.values()) == 70300
    assert totais[Destino.LISTA_DE_BAIXA].valor_centavos == 70000


def test_coluna_repetida_e_citada_como_a_mais(pasta: Path, armazenamento: Armazenamento) -> None:
    _escrever(pasta, "itau_cobranca.csv", "data;data;historico;documento;valor;tipo", "14/03/2025;" + _CREDITO)

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert "a mais 'data'" in _motivo(resultado.arquivos_recusados, "itau_cobranca.csv")
