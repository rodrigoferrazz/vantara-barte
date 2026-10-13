from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.conferencia import ConferenciaDeSomaFalhou
from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.dominio import MotivoDeNaoIdentificacao
from conciliacao.execucao import executar_conciliacao
from conciliacao.motor import conciliar
from tests.arquivos import LinhaItau, TituloProtheus, configuracao_itau, escrever_extrato_itau, escrever_protheus


def test_liquidacao_com_nosso_numero_e_valor_exato_vai_para_a_lista_com_explicacao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900001", valor="1.234,56", nosso_numero="000077700011")])
    escrever_extrato_itau(pasta, [LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.234,56", documento="000077700011")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert len(resultado.lista_de_baixa) == 1
    item = resultado.lista_de_baixa[0]
    assert [t.documento for t in item.titulos] == ["NF 900001"]
    assert item.lancamento.valor_centavos == 123456
    assert "000077700011" in item.explicacao
    assert "1.234,56" in item.explicacao
    assert resultado.fila_de_excecoes == []
    assert resultado.fora_do_escopo == []


def test_debitos_e_tarifas_vao_para_fora_do_escopo(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900002", valor="500,00", nosso_numero="000077700022")])
    escrever_extrato_itau(
        pasta,
        [
            LinhaItau("03/03/2025", "TARIFA MANUTENCAO CONTA", "35,90", tipo="D"),
            LinhaItau("04/03/2025", "PAGAMENTO FORNECEDOR", "500,00", tipo="D", documento="000077700022"),
        ],
    )

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert [item.lancamento.historico for item in resultado.fora_do_escopo] == [
        "TARIFA MANUTENCAO CONTA",
        "PAGAMENTO FORNECEDOR",
    ]
    assert resultado.lista_de_baixa == []
    assert resultado.fila_de_excecoes == []


def test_credito_sem_nosso_numero_de_titulo_vai_para_a_fila_com_motivo(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900003", valor="800,00", nosso_numero="000077700033")])
    escrever_extrato_itau(
        pasta,
        [
            LinhaItau("05/03/2025", "PIX RECEBIDO FULANO DE TAL", "800,00"),
            LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "800,00", documento="000099999999"),
        ],
    )

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.lista_de_baixa == []
    assert len(resultado.fila_de_excecoes) == 2
    assert all(item.motivo is not None for item in resultado.fila_de_excecoes)


def test_nosso_numero_com_valor_diferente_vai_para_a_fila_sugerindo_o_titulo(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900004", valor="2.000,00", nosso_numero="000077700044")])
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.500,00", documento="000077700044")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [t.documento for t in item.titulos] == ["NF 900004"]


def test_nosso_numero_de_mais_de_um_titulo_nao_vai_para_a_lista(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 900005", valor="300,00", nosso_numero="000077700055"),
            TituloProtheus(documento="NF 900006", valor="300,00", nosso_numero="000077700055"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "300,00", documento="000077700055")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.lista_de_baixa == []
    assert len(resultado.fila_de_excecoes) == 1


def test_reimportar_periodo_sobreposto_nao_duplica_creditos(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900007", valor="410,00", nosso_numero="000077700077")])
    liquidacao = LinhaItau("10/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "410,00", documento="000077700077")
    pix = LinhaItau("12/03/2025", "PIX RECEBIDO BELTRANO", "95,00")
    escrever_extrato_itau(pasta, [liquidacao, pix], nome="itau_cobranca_1a15.csv")
    primeira = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    escrever_extrato_itau(
        pasta, [pix, LinhaItau("18/03/2025", "PIX RECEBIDO CICLANO", "60,00")], nome="itau_cobranca_10a31.csv"
    )
    segunda = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert primeira.resumo.lancamentos_novos == 2
    assert segunda.resumo.lancamentos_novos == 1
    assert len(segunda.lista_de_baixa) == 1
    assert sorted(item.lancamento.historico for item in segunda.fila_de_excecoes) == [
        "PIX RECEBIDO BELTRANO",
        "PIX RECEBIDO CICLANO",
    ]


def test_duas_linhas_identicas_no_mesmo_dia_viram_dois_creditos(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [])
    repetida = LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00")
    escrever_extrato_itau(pasta, [repetida, repetida])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())
    reexecucao = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert len(resultado.fila_de_excecoes) == 2
    assert len({item.identificador for item in resultado.fila_de_excecoes}) == 2
    assert len(reexecucao.fila_de_excecoes) == 2
    assert reexecucao.resumo.lancamentos_novos == 0


def test_banco_e_conta_do_extrato_vem_da_configuracao_pelo_nome_do_arquivo(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [])
    escrever_extrato_itau(pasta, [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00")], nome="itau_cobranca.csv")
    escrever_extrato_itau(pasta, [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00")], nome="itau_folha.csv")
    configuracao = Configuracao(
        contas=(
            ContaDeExtrato(padrao="itau_cobranca*", banco="itau", conta="1111-1"),
            ContaDeExtrato(padrao="itau_folha*", banco="itau", conta="2222-2"),
        )
    )

    resultado = executar_conciliacao(pasta, armazenamento, configuracao)

    assert sorted(item.lancamento.conta for item in resultado.fila_de_excecoes) == ["1111-1", "2222-2"]
    assert {item.lancamento.banco for item in resultado.fila_de_excecoes} == {"itau"}


def test_extrato_com_nome_fora_da_configuracao_nao_entra(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [])
    escrever_extrato_itau(pasta, [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00")], nome="extrato_sem_conta.csv")

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.itens == ()
    assert [recusado.nome for recusado in resultado.arquivos_recusados] == ["extrato_sem_conta.csv"]


def test_conferencia_de_soma_que_nao_fecha_para_a_execucao_sem_guardar_nada(
    pasta: Path, armazenamento: Armazenamento, monkeypatch: pytest.MonkeyPatch
) -> None:
    escrever_protheus(pasta, [])
    escrever_extrato_itau(
        pasta,
        [LinhaItau("14/03/2025", "PIX RECEBIDO BELTRANO", "95,00"), LinhaItau("15/03/2025", "TARIFA", "1,00", tipo="D")],
    )
    monkeypatch.setattr("conciliacao.execucao.conciliar", lambda *args: conciliar(*args)[1:])

    with pytest.raises(ConferenciaDeSomaFalhou, match="R\\$ 96,00"):
        executar_conciliacao(pasta, armazenamento, configuracao_itau())

    monkeypatch.undo()
    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())
    assert resultado.resumo.lancamentos_novos == 2
    assert resultado.resumo.execucao == 1
