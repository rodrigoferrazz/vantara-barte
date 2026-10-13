from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from conciliacao.dominio import Destino, Item, Resultado, Titulo
from conciliacao.normalizacao import formatar_reais

_FORMATO_DE_VALOR = "#,##0.00"
_FORMATO_DE_DATA = "DD/MM/YYYY"


def gerar_workbook(resultado: Resultado, caminho: Path) -> None:
    workbook = Workbook()
    resumo = workbook.active
    assert resumo is not None
    resumo.title = "Resumo"
    _preencher_resumo(resumo, resultado)
    _aba_de_itens(workbook.create_sheet(Destino.LISTA_DE_BAIXA.value), resultado.lista_de_baixa, ("Títulos", "Explicação"))
    _aba_de_itens(
        workbook.create_sheet(Destino.FILA_DE_EXCECOES.value),
        resultado.fila_de_excecoes,
        ("Motivo", "Títulos sugeridos", "Explicação"),
    )
    _aba_de_itens(workbook.create_sheet(Destino.FORA_DO_ESCOPO.value), resultado.fora_do_escopo, ("Explicação",))
    workbook.save(caminho)


def _preencher_resumo(aba: Worksheet, resultado: Resultado) -> None:
    resumo = resultado.resumo
    aba.append(("Execução", resumo.execucao))
    aba.append(("Arquivos lidos", f"{len(resumo.arquivos_lidos)}: {', '.join(resumo.arquivos_lidos)}"))
    aba.append(("Arquivos recusados", len(resumo.arquivos_recusados)))
    for recusado in resumo.arquivos_recusados:
        aba.append((f"Recusado: {recusado.nome}", recusado.motivo))
    aba.append(("Lançamentos novos no Extrato", resumo.lancamentos_novos))
    for destino, total in resumo.totais.items():
        aba.append((destino.value, f"{total.quantidade} lançamento(s), {formatar_reais(total.valor_centavos)}"))
    aba.column_dimensions["A"].width = 32
    aba.column_dimensions["B"].width = 60


def _aba_de_itens(aba: Worksheet, itens: list[Item], colunas_do_destino: tuple[str, ...]) -> None:
    aba.append(("Item", "Banco", "Conta", "Data", "Histórico", "Documento", "Valor", *colunas_do_destino))
    for item in itens:
        lancamento = item.lancamento
        valores_do_destino = {
            "Títulos": _titulos(item.titulos),
            "Títulos sugeridos": _titulos(item.titulos),
            "Motivo": item.motivo.value if item.motivo else "",
            "Explicação": item.explicacao,
        }
        aba.append(
            (
                item.identificador,
                lancamento.banco,
                lancamento.conta,
                lancamento.data,
                lancamento.historico,
                lancamento.documento,
                Decimal(lancamento.valor_centavos) / 100,
                *(valores_do_destino[coluna] for coluna in colunas_do_destino),
            )
        )
        aba.cell(row=aba.max_row, column=4).number_format = _FORMATO_DE_DATA
        aba.cell(row=aba.max_row, column=7).number_format = _FORMATO_DE_VALOR
    aba.freeze_panes = "A2"


def _titulos(titulos: tuple[Titulo, ...]) -> str:
    return "; ".join(f"{titulo.documento} ({titulo.sistema_de_origem})" for titulo in titulos)
