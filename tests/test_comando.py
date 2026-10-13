from pathlib import Path

import pytest

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from conciliacao.cli import main
from tests.arquivos import LinhaItau, TituloProtheus, escrever_extrato_itau, escrever_protheus


def _escrever_configuracao(caminho: Path) -> Path:
    caminho.write_text('[[contas]]\npadrao = "itau_cobranca*.csv"\nbanco = "itau"\nconta = "1234-5"\n', encoding="utf-8")
    return caminho


def test_comando_gera_workbook_com_resumo_no_topo_e_as_quatro_abas(tmp_path: Path) -> None:
    pasta = tmp_path / "entrada"
    pasta.mkdir()
    escrever_protheus(pasta, [TituloProtheus(documento="NF 900101", valor="1.000,00", nosso_numero="000088800011")])
    escrever_extrato_itau(
        pasta,
        [
            LinhaItau("06/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.000,00", documento="000088800011"),
            LinhaItau("07/03/2025", "PIX RECEBIDO FULANO", "250,00"),
            LinhaItau("07/03/2025", "TARIFA PIX", "2,50", tipo="D"),
        ],
    )
    saida = tmp_path / "conciliacao.xlsx"

    codigo = main(
        [
            str(pasta),
            "--configuracao",
            str(_escrever_configuracao(tmp_path / "conciliacao.toml")),
            "--estado",
            str(tmp_path / "estado.sqlite"),
            "--saida",
            str(saida),
        ]
    )

    assert codigo == 0
    workbook = load_workbook(saida)
    assert workbook.sheetnames == [
        "Resumo",
        "Lista de baixa",
        "Baixa manual no ERP",
        "Fila de exceções",
        "Lista de cobrança",
        "Causa raiz",
        "Fora do escopo",
        "Arquivos recusados",
    ]
    lista = _linhas(workbook["Lista de baixa"])
    assert len(lista) == 1
    assert "NF 900101" in str(lista[0]["Títulos"])
    assert "000088800011" in str(lista[0]["Explicação"])
    assert lista[0]["Valor"] == 1000
    fila = _linhas(workbook["Fila de exceções"])
    assert [linha["Histórico"] for linha in fila] == ["PIX RECEBIDO FULANO"]
    assert fila[0]["Motivo"]
    assert [linha["Histórico"] for linha in _linhas(workbook["Fora do escopo"])] == ["TARIFA PIX"]
    resumo = {linha[0]: linha[1] for linha in workbook["Resumo"].iter_rows(values_only=True)}
    assert resumo["Lista de baixa"] == "1 lançamento(s), R$ 1.000,00"
    assert resumo["Fila de exceções"] == "1 lançamento(s), R$ 250,00"
    assert resumo["Fora do escopo"] == "1 lançamento(s), R$ 2,50"


def test_comando_falha_com_mensagem_quando_a_configuracao_nao_existe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pasta = tmp_path / "entrada"
    pasta.mkdir()

    codigo = main([str(pasta), "--configuracao", str(tmp_path / "nao_existe.toml"), "--estado", str(tmp_path / "e.sqlite")])

    assert codigo != 0
    assert "nao_existe.toml" in capsys.readouterr().err


def test_comando_lista_arquivos_recusados_em_aba_propria_e_conta_lidos_e_recusados_no_resumo(tmp_path: Path) -> None:
    pasta = tmp_path / "entrada"
    pasta.mkdir()
    escrever_protheus(pasta, [])
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "PIX RECEBIDO FULANO", "250,00")])
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "PIX RECEBIDO FULANO", "250,00")], nome="sem_conta.csv")
    (pasta / "estranho.txt").write_text("qualquer coisa\n", encoding="utf-8")
    saida = tmp_path / "conciliacao.xlsx"

    codigo = main(
        [
            str(pasta),
            "--configuracao",
            str(_escrever_configuracao(tmp_path / "conciliacao.toml")),
            "--estado",
            str(tmp_path / "estado.sqlite"),
            "--saida",
            str(saida),
        ]
    )

    assert codigo == 0
    workbook = load_workbook(saida)
    recusados = _linhas(workbook["Arquivos recusados"])
    assert [linha["Arquivo"] for linha in recusados] == ["estranho.txt", "sem_conta.csv"]
    assert all(linha["Motivo"] for linha in recusados)
    resumo = {linha[0]: linha[1] for linha in workbook["Resumo"].iter_rows(values_only=True)}
    assert resumo["Arquivos lidos"] == 2
    assert resumo["Arquivos recusados"] == 2


def _linhas(aba: Worksheet) -> list[dict[str, object]]:
    cabecalho, *linhas = aba.iter_rows(values_only=True)
    return [dict(zip([str(c) for c in cabecalho], linha)) for linha in linhas]
