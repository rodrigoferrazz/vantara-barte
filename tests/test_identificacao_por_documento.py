from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.dominio import MotivoDeNaoIdentificacao
from conciliacao.execucao import executar_conciliacao
from tests.arquivos import LinhaItau, TituloProtheus, configuracao_itau, escrever_extrato_itau, escrever_protheus
from tests.parecerista import PareceristaFalso

CNPJ_MATRIZ = "10.200.300/0001-40"
CNPJ_OUTRO_FRANQUEADO = "20.400.600/0001-80"


@pytest.mark.parametrize(
    "historico",
    [
        "PIX RECEBIDO 10200300000140",
        "TED RECEBIDA CNPJ 10.200.300/0001-40",
        "PIX RECEBIDO 10200300000299",
    ],
    ids=["sem pontuacao", "com pontuacao", "filial"],
)
def test_cnpj_no_historico_com_valor_unico_vai_para_a_lista_citando_o_documento(
    pasta: Path, armazenamento: Armazenamento, historico: str
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 910001", valor="740,00", cnpj=CNPJ_MATRIZ),
            TituloProtheus(documento="NF 910002", valor="1.100,00", cnpj=CNPJ_MATRIZ),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", historico, "740,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    [item] = resultado.lista_de_baixa
    assert [t.documento for t in item.titulos] == ["NF 910001"]
    documento_citado = "".join(c for c in historico if c.isdigit())
    assert documento_citado in item.explicacao
    assert "Valor único" in item.explicacao
    assert resultado.fila_de_excecoes == []


def test_valor_unico_considera_so_os_titulos_do_franqueado_identificado(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 910011", valor="520,00", cnpj=CNPJ_OUTRO_FRANQUEADO, cliente="Outra Franquia"),
            TituloProtheus(documento="NF 910012", valor="520,00", cnpj=CNPJ_MATRIZ),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "PIX RECEBIDO 10200300000140", "520,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    [item] = resultado.lista_de_baixa
    assert [t.documento for t in item.titulos] == ["NF 910012"]


def test_valor_que_bate_com_mais_de_um_titulo_do_franqueado_vai_para_a_fila(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 910021", valor="300,00", cnpj=CNPJ_MATRIZ),
            TituloProtheus(documento="NF 910022", valor="300,00", cnpj=CNPJ_MATRIZ, vencimento="20/03/2025"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "PIX RECEBIDO 10200300000140", "300,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO
    assert "NF 910021" in item.explicacao
    assert "NF 910022" in item.explicacao


def test_valor_que_nao_bate_com_titulo_do_franqueado_vai_para_a_fila_como_valor_nao_fecha(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 910031", valor="900,00", cnpj=CNPJ_MATRIZ)])
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "PIX RECEBIDO 10200300000140", "650,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [t.documento for t in item.titulos] == ["NF 910031"]


def test_franqueado_com_varios_titulos_e_valor_que_nao_fecha_com_nenhum_e_credito_sem_titulo_em_aberto(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 910035", valor="900,00", cnpj=CNPJ_MATRIZ),
            TituloProtheus(documento="NF 910036", valor="400,00", cnpj=CNPJ_MATRIZ),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "PIX RECEBIDO 10200300000140", "650,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO
    assert item.titulos == ()
    assert "10200300000140" in item.explicacao


def test_cnpj_que_nao_e_de_franqueado_nao_identifica_o_pagador(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 910041", valor="410,00", cnpj=CNPJ_MATRIZ)])
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "PIX RECEBIDO 99888777000166", "410,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR


def test_franqueado_identificado_sem_titulo_em_aberto_vai_para_a_fila_e_casa_com_titulo_novo_depois(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 910051", valor="200,00", cnpj=CNPJ_MATRIZ)])
    executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    escrever_protheus(pasta, [TituloProtheus(documento="NF 910061", valor="80,00", cnpj=CNPJ_OUTRO_FRANQUEADO)])
    escrever_extrato_itau(pasta, [LinhaItau("12/03/2025", "PIX RECEBIDO 10200300000140", "1.250,00")])
    antecipado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    [item] = antecipado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO
    assert item.titulos == ()
    assert "10200300000140" in item.explicacao

    escrever_protheus(pasta, [TituloProtheus(documento="NF 910071", valor="1.250,00", cnpj=CNPJ_MATRIZ)])
    retentado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert retentado.fila_de_excecoes == []
    [baixa] = retentado.lista_de_baixa
    assert baixa.identificador == item.identificador
    assert [t.documento for t in baixa.titulos] == ["NF 910071"]


def test_cnpjs_de_franqueados_diferentes_no_mesmo_historico_nao_identificam_o_pagador(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 910081", valor="610,00", cnpj=CNPJ_MATRIZ),
            TituloProtheus(documento="NF 910082", valor="610,00", cnpj=CNPJ_OUTRO_FRANQUEADO, cliente="Outra Franquia"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", "TED 10200300000140 REF 20400600000180", "610,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau(), PareceristaFalso())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR
