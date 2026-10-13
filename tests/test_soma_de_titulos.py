from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import Item, MotivoDeNaoIdentificacao, Resultado, TipoDeEvidencia
from conciliacao.execucao import executar_conciliacao
from tests.arquivos import LinhaItau, TituloProtheus, configuracao_itau, escrever_extrato_itau, escrever_protheus
from tests.parecerista import PareceristaFalso

CNPJ_A = "10.200.300/0001-40"
CNPJ_B = "20.400.600/0001-80"
PIX_DO_CNPJ_A = "PIX RECEBIDO 10200300000140"


def _titulos_do_a(*valores: str, vencimento: str = "05/03/2025") -> list[TituloProtheus]:
    return [
        TituloProtheus(documento=f"NF {n}", valor=valor, cnpj=CNPJ_A, vencimento=vencimento)
        for n, valor in enumerate(valores, start=1)
    ]


def _executar(pasta: Path, armazenamento: Armazenamento, limite_de_combinacoes: int = 100_000) -> Resultado:
    return executar_conciliacao(pasta, armazenamento, configuracao_itau(limite_de_combinacoes=limite_de_combinacoes), PareceristaFalso())


def _unico_da_fila(resultado: Resultado) -> Item:
    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    return item


def test_soma_exata_e_unica_com_pagador_identificado_por_documento_vai_para_a_lista_com_a_soma(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, _titulos_do_a("1.200,00", "800,00", "450,00"))
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "2.000,00")])

    resultado = _executar(pasta, armazenamento)

    [item] = resultado.lista_de_baixa
    assert sorted(t.documento for t in item.titulos) == ["NF 1", "NF 2"]
    assert item.evidencia == (TipoDeEvidencia.CNPJ_CPF,)
    assert "R$ 1.200,00" in item.explicacao
    assert "R$ 800,00" in item.explicacao
    assert "R$ 2.000,00" in item.explicacao
    assert "soma" in item.explicacao
    assert resultado.fila_de_excecoes == []


def test_soma_com_titulo_atrasado_pago_pelo_valor_original_registra_encargo_nao_pago(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", cnpj=CNPJ_A, vencimento="03/03/2025"),
            TituloProtheus(documento="NF 2", valor="500,00", cnpj=CNPJ_A, vencimento="20/03/2025"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", PIX_DO_CNPJ_A, "1.500,00")])

    [item] = _executar(pasta, armazenamento).lista_de_baixa

    assert sorted(t.documento for t in item.titulos) == ["NF 1", "NF 2"]
    assert "Encargo não pago" in item.explicacao


def test_soma_que_so_fecha_com_encargo_pago_vai_para_a_fila_como_valor_nao_fecha(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, _titulos_do_a("1.000,00", "500,00", vencimento="03/03/2025"))
    escrever_extrato_itau(pasta, [LinhaItau("10/03/2025", PIX_DO_CNPJ_A, "1.520,00")])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA


def test_soma_exata_e_unica_com_nome_nao_confirmado_vai_para_a_fila_como_pagador_provavel_com_a_combinacao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 1", valor="1.200,00", cliente="Panificadora Aurora Ltda"),
            TituloProtheus(documento="NF 2", valor="800,00", cliente="Panificadora Aurora Ltda"),
            TituloProtheus(documento="NF 3", valor="450,00", cliente="Panificadora Aurora Ltda"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", "PIX RECEBIDO PANIFICADORA AURORA LT", "1.650,00")])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ
    assert sorted(t.documento for t in item.titulos) == ["NF 1", "NF 3"]
    assert item.evidencia == (TipoDeEvidencia.NOME_POR_PREFIXO,)
    assert "soma" in item.explicacao


@pytest.mark.parametrize(
    ("valores", "credito"),
    [
        (("300,00", "200,00", "100,00", "400,00"), "500,00"),
        (("700,00", "500,00", "200,00"), "700,00"),
    ],
    ids=["duas somas", "um titulo e uma soma"],
)
def test_mais_de_uma_combinacao_que_fecha_o_valor_vai_para_a_fila(
    pasta: Path, armazenamento: Armazenamento, valores: tuple[str, ...], credito: str
) -> None:
    escrever_protheus(pasta, _titulos_do_a(*valores))
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, credito)])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO
    assert item.titulos == ()


def test_mais_de_uma_combinacao_com_nome_nao_confirmado_vai_para_a_fila_sem_sugestao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento=f"NF {n}", valor=valor, cliente="Panificadora Aurora Ltda")
            for n, valor in enumerate(["300,00", "200,00", "100,00", "400,00"], start=1)
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", "PIX RECEBIDO PANIFICADORA AURORA", "500,00")])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO
    assert item.titulos == ()


def test_soma_considera_so_os_titulos_do_mesmo_franqueado(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 1", valor="1.200,00", cnpj=CNPJ_A),
            TituloProtheus(documento="NF 2", valor="800,00", cnpj=CNPJ_B, cliente="Outra Franquia"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "2.000,00")])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA


def test_limite_de_combinacoes_atingido_vai_para_a_fila_como_mais_de_uma_combinacao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, _titulos_do_a("100,00", "200,00", "400,00", "800,00"))
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "1.300,00")])

    item = _unico_da_fila(_executar(pasta, armazenamento, limite_de_combinacoes=2))

    assert item.motivo is MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO
    assert item.titulos == ()
    assert "limite" in item.explicacao


def test_dentro_do_limite_a_mesma_soma_vai_para_a_lista(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, _titulos_do_a("100,00", "200,00", "400,00", "800,00"))
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "1.300,00")])

    [item] = _executar(pasta, armazenamento).lista_de_baixa

    assert sorted(t.documento for t in item.titulos) == ["NF 1", "NF 3", "NF 4"]


def test_limite_de_combinacoes_vem_da_configuracao(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(_configuracao_em_arquivo(tmp_path, "[somas]\nlimite_de_combinacoes = 5000\n"))

    assert configuracao.limite_de_combinacoes == 5000


@pytest.mark.parametrize(
    "somas",
    [
        "[somas]\nlimite_de_combinacoes = 0\n",
        "[somas]\nlimite_de_combinacoes = 10.5\n",
        '[somas]\nlimite_de_combinacoes = "mil"\n',
        "[somas]\nlimite = 10\n",
    ],
    ids=["zero", "fracao", "texto", "campo desconhecido"],
)
def test_limite_de_combinacoes_invalido_recusa_a_configuracao(tmp_path: Path, somas: str) -> None:
    with pytest.raises(ConfiguracaoInvalida, match="somas"):
        carregar_configuracao(_configuracao_em_arquivo(tmp_path, somas))


@pytest.mark.parametrize(
    ("valores", "credito"),
    [(("1.000,00",), "600,00"), (("1.000,00", "900,00"), "600,00")],
    ids=["um titulo", "nenhuma soma fecha"],
)
def test_credito_que_paga_parte_de_um_titulo_vai_para_a_fila_como_valor_nao_fecha(
    pasta: Path, armazenamento: Armazenamento, valores: tuple[str, ...], credito: str
) -> None:
    escrever_protheus(pasta, _titulos_do_a(*valores))
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, credito)])

    item = _unico_da_fila(_executar(pasta, armazenamento))

    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA


def test_varios_creditos_pagando_varios_titulos_nao_vao_para_a_lista(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, _titulos_do_a("300,00", "700,00"))
    escrever_extrato_itau(
        pasta,
        [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "600,00"), LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "400,00")],
    )

    resultado = _executar(pasta, armazenamento)

    assert resultado.lista_de_baixa == []
    assert len(resultado.fila_de_excecoes) == 2


def test_creditos_que_fecham_com_os_mesmos_titulos_nao_vao_para_a_lista(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, _titulos_do_a("300,00", "700,00"))
    escrever_extrato_itau(
        pasta,
        [LinhaItau("05/03/2025", PIX_DO_CNPJ_A, "1.000,00"), LinhaItau("06/03/2025", PIX_DO_CNPJ_A, "1.000,00")],
    )

    resultado = _executar(pasta, armazenamento)

    assert resultado.lista_de_baixa == []
    assert [item.motivo for item in resultado.fila_de_excecoes] == [MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO] * 2
    for item in resultado.fila_de_excecoes:
        assert sorted(t.documento for t in item.titulos) == ["NF 1", "NF 2"]
        assert "outro Crédito" in item.explicacao


def _configuracao_em_arquivo(tmp_path: Path, secao: str) -> Path:
    caminho = tmp_path / "conciliacao.toml"
    caminho.write_text(f'[[contas]]\npadrao = "itau*.csv"\nbanco = "itau"\nconta = "1"\n\n{secao}', encoding="utf-8")
    return caminho
