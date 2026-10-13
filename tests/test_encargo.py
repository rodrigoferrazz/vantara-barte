from decimal import Decimal
from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import Item, MotivoDeNaoIdentificacao, Resultado
from conciliacao.encargo import ParametrosDeEncargo
from conciliacao.execucao import executar_conciliacao
from tests.arquivos import LinhaItau, TituloProtheus, configuracao_itau, escrever_extrato_itau, escrever_protheus

NOSSO_NUMERO = "000077700011"


def _pagar_por_nosso_numero(
    pasta: Path,
    armazenamento: Armazenamento,
    *,
    valor_do_titulo: str,
    vencimento: str,
    data: str,
    valor_pago: str,
    encargo: ParametrosDeEncargo = ParametrosDeEncargo(),
) -> Resultado:
    escrever_protheus(
        pasta,
        [TituloProtheus(documento="NF 940001", valor=valor_do_titulo, nosso_numero=NOSSO_NUMERO, vencimento=vencimento)],
    )
    escrever_extrato_itau(pasta, [LinhaItau(data, "LIQUIDACAO COBRANCA SIMPLES", valor_pago, documento=NOSSO_NUMERO)])
    return executar_conciliacao(pasta, armazenamento, configuracao_itau(encargo=encargo))


def _na_lista(resultado: Resultado) -> Item:
    assert resultado.fila_de_excecoes == []
    [item] = resultado.lista_de_baixa
    assert [t.documento for t in item.titulos] == ["NF 940001"]
    return item


def _na_fila(resultado: Resultado) -> Item:
    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    return item


PRORROGACOES = [
    ("08/03/2025", "10/03/2025"),
    ("09/03/2025", "10/03/2025"),
    ("03/03/2025", "05/03/2025"),
    ("18/04/2025", "22/04/2025"),
    ("19/04/2025", "22/04/2025"),
    ("01/05/2026", "04/05/2026"),
    ("19/06/2025", "20/06/2025"),
    ("07/09/2026", "08/09/2026"),
    ("12/10/2026", "13/10/2026"),
    ("02/11/2026", "03/11/2026"),
    ("15/11/2027", "16/11/2027"),
    ("20/11/2025", "21/11/2025"),
    ("25/12/2025", "26/12/2025"),
    ("01/01/2026", "02/01/2026"),
]
IDS_DAS_PRORROGACOES = [
    "sabado",
    "domingo",
    "carnaval",
    "paixao e tiradentes",
    "sabado antes de tiradentes",
    "dia do trabalho",
    "corpus christi",
    "independencia",
    "nossa senhora aparecida",
    "finados",
    "proclamacao da republica",
    "consciencia negra",
    "natal",
    "confraternizacao universal",
]


@pytest.mark.parametrize(("vencimento", "vencimento_efetivo"), PRORROGACOES, ids=IDS_DAS_PRORROGACOES)
def test_pagamento_no_vencimento_efetivo_nao_tem_encargo(
    pasta: Path, armazenamento: Armazenamento, vencimento: str, vencimento_efetivo: str
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="1.000,00", vencimento=vencimento, data=vencimento_efetivo, valor_pago="1.000,00"
    )

    item = _na_lista(resultado)
    assert "Encargo não pago" not in item.explicacao


@pytest.mark.parametrize(("vencimento", "vencimento_efetivo"), PRORROGACOES, ids=IDS_DAS_PRORROGACOES)
def test_multa_paga_no_vencimento_efetivo_e_valor_a_maior(
    pasta: Path, armazenamento: Armazenamento, vencimento: str, vencimento_efetivo: str
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="1.000,00", vencimento=vencimento, data=vencimento_efetivo, valor_pago="1.020,00"
    )

    item = _na_fila(resultado)
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert "Valor a maior" in item.explicacao


def test_pagamento_um_dia_depois_do_vencimento_efetivo_esta_atrasado(pasta: Path, armazenamento: Armazenamento) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="1.000,00", vencimento="08/03/2025", data="11/03/2025", valor_pago="1.020,33"
    )

    item = _na_lista(resultado)
    assert "Encargo R$ 20,33" in item.explicacao


@pytest.mark.parametrize(
    ("valor_pago", "principal", "encargo"),
    [("10.233,33", "R$ 10.000,00", "R$ 233,33"), ("10.200,00", "R$ 10.000,00", "R$ 200,00"), ("10.000,01", "R$ 10.000,00", "R$ 0,01")],
    ids=["multa e juros", "so a multa", "parte do encargo"],
)
def test_atraso_pago_dentro_do_encargo_vai_para_a_lista_com_principal_e_encargo(
    pasta: Path, armazenamento: Armazenamento, valor_pago: str, principal: str, encargo: str
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="10.000,00", vencimento="10/03/2025", data="20/03/2025", valor_pago=valor_pago
    )

    item = _na_lista(resultado)
    assert f"principal {principal}" in item.explicacao
    assert f"Encargo {encargo}" in item.explicacao


def test_atraso_pago_so_pelo_valor_original_vai_para_a_lista_com_encargo_nao_pago(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="10.000,00", vencimento="10/03/2025", data="20/03/2025", valor_pago="10.000,00"
    )

    item = _na_lista(resultado)
    assert "Encargo não pago" in item.explicacao


@pytest.mark.parametrize(
    ("data", "valor_pago"), [("10/03/2025", "9.999,99"), ("20/03/2025", "9.500,00")], ids=["em dia", "atrasado"]
)
def test_valor_abaixo_do_titulo_vai_para_a_fila_como_diferenca_a_menor(
    pasta: Path, armazenamento: Armazenamento, data: str, valor_pago: str
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="10.000,00", vencimento="10/03/2025", data=data, valor_pago=valor_pago
    )

    item = _na_fila(resultado)
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [t.documento for t in item.titulos] == ["NF 940001"]
    assert "Diferença a menor" in item.explicacao


@pytest.mark.parametrize(
    ("data", "valor_pago"), [("10/03/2025", "10.000,01"), ("20/03/2025", "10.233,34")], ids=["em dia", "atrasado"]
)
def test_valor_acima_do_titulo_mais_encargo_vai_para_a_fila_como_valor_a_maior(
    pasta: Path, armazenamento: Armazenamento, data: str, valor_pago: str
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta, armazenamento, valor_do_titulo="10.000,00", vencimento="10/03/2025", data=data, valor_pago=valor_pago
    )

    item = _na_fila(resultado)
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [t.documento for t in item.titulos] == ["NF 940001"]
    assert "Valor a maior" in item.explicacao


@pytest.mark.parametrize(
    ("valor_pago", "na_lista"), [("10.233,83", True), ("10.233,84", False)], ids=["no limite", "acima do limite"]
)
def test_tolerancia_amplia_o_encargo_previsto(
    pasta: Path, armazenamento: Armazenamento, valor_pago: str, na_lista: bool
) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta,
        armazenamento,
        valor_do_titulo="10.000,00",
        vencimento="10/03/2025",
        data="20/03/2025",
        valor_pago=valor_pago,
        encargo=ParametrosDeEncargo(tolerancia_centavos=50),
    )

    assert len(resultado.lista_de_baixa) == (1 if na_lista else 0)


def test_tolerancia_nao_vale_para_pagamento_em_dia(pasta: Path, armazenamento: Armazenamento) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta,
        armazenamento,
        valor_do_titulo="10.000,00",
        vencimento="10/03/2025",
        data="10/03/2025",
        valor_pago="10.000,10",
        encargo=ParametrosDeEncargo(tolerancia_centavos=50),
    )

    assert _na_fila(resultado).motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA


def test_multa_e_juros_vem_dos_parametros(pasta: Path, armazenamento: Armazenamento) -> None:
    resultado = _pagar_por_nosso_numero(
        pasta,
        armazenamento,
        valor_do_titulo="10.000,00",
        vencimento="10/03/2025",
        data="20/03/2025",
        valor_pago="11.100,00",
        encargo=ParametrosDeEncargo(multa_percentual=Decimal("10"), juros_ao_mes_percentual=Decimal("3")),
    )

    item = _na_lista(resultado)
    assert "Encargo R$ 1.100,00" in item.explicacao


def test_cnpj_com_valor_dentro_do_encargo_vai_para_a_lista(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 940101", valor="5.000,00", vencimento="10/03/2025"),
            TituloProtheus(documento="NF 940102", valor="7.000,00", vencimento="10/03/2025"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("12/03/2025", "TED CNPJ 10200300000140", "5.100,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.fila_de_excecoes == []
    [item] = resultado.lista_de_baixa
    assert [t.documento for t in item.titulos] == ["NF 940101"]
    assert "principal R$ 5.000,00" in item.explicacao
    assert "Encargo R$ 100,00" in item.explicacao


def test_cnpj_com_valor_original_atrasado_vai_para_a_lista_com_encargo_nao_pago(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 940111", valor="5.000,00", vencimento="10/03/2025")])
    escrever_extrato_itau(pasta, [LinhaItau("12/03/2025", "PIX RECEBIDO 10200300000140", "5.000,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    [item] = resultado.lista_de_baixa
    assert "Encargo não pago" in item.explicacao


def test_cnpj_com_valor_que_fecha_com_mais_de_um_titulo_considerando_o_encargo_vai_para_a_fila(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF 940121", valor="5.000,00", vencimento="10/03/2025"),
            TituloProtheus(documento="NF 940122", valor="5.100,00", vencimento="20/03/2025"),
        ],
    )
    escrever_extrato_itau(pasta, [LinhaItau("12/03/2025", "PIX RECEBIDO 10200300000140", "5.100,00")])

    resultado = executar_conciliacao(pasta, armazenamento, configuracao_itau())

    assert resultado.lista_de_baixa == []
    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO
    assert "NF 940121" in item.explicacao
    assert "NF 940122" in item.explicacao


def _configuracao_em_arquivo(tmp_path: Path, encargo: str) -> Path:
    caminho = tmp_path / "conciliacao.toml"
    caminho.write_text(
        f'[[contas]]\npadrao = "itau*.csv"\nbanco = "itau"\nconta = "1"\n\n{encargo}', encoding="utf-8"
    )
    return caminho


def test_parametros_de_encargo_vem_da_configuracao(tmp_path: Path) -> None:
    caminho = _configuracao_em_arquivo(
        tmp_path, "[encargo]\nmulta_percentual = 2.5\njuros_ao_mes_percentual = 1\ntolerancia_reais = 0.75\n"
    )

    configuracao = carregar_configuracao(caminho)

    assert configuracao.encargo == ParametrosDeEncargo(
        multa_percentual=Decimal("2.5"), juros_ao_mes_percentual=Decimal("1"), tolerancia_centavos=75
    )


def test_sem_secao_de_encargo_vale_a_multa_padrao_de_2_por_cento(tmp_path: Path) -> None:
    configuracao = carregar_configuracao(_configuracao_em_arquivo(tmp_path, ""))

    assert configuracao.encargo.multa_percentual == Decimal("2")


@pytest.mark.parametrize(
    "encargo",
    [
        '[encargo]\nmulta_percentual = "2%"\n',
        "[encargo]\nmulta_percentual = -1\n",
        "[encargo]\ntolerancia_reais = 0.001\n",
        "[encargo]\njuros_ao_dia = 1\n",
    ],
    ids=["texto", "negativo", "fracao de centavo", "campo desconhecido"],
)
def test_parametro_de_encargo_invalido_recusa_a_configuracao(tmp_path: Path, encargo: str) -> None:
    with pytest.raises(ConfiguracaoInvalida, match="encargo"):
        carregar_configuracao(_configuracao_em_arquivo(tmp_path, encargo))
