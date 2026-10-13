from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from conciliacao.dominio import ArquivoRecusado, Destino, Item, ItemDeTitulo, Resultado, Resumo, Titulo
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
    fila = workbook.create_sheet(Destino.FILA_DE_EXCECOES.value)
    _aba_de_itens(
        fila,
        resultado.fila_de_excecoes,
        ("Motivo", "Títulos sugeridos", "Evidência", "O que falta", "Explicação", "Parecer da IA"),
    )
    _acrescentar_itens_de_titulo(fila, resultado.itens_de_titulo)
    _aba_de_itens(workbook.create_sheet(Destino.FORA_DO_ESCOPO.value), resultado.fora_do_escopo, ("Explicação",))
    _aba_de_arquivos_recusados(workbook.create_sheet("Arquivos recusados"), resultado.arquivos_recusados)
    workbook.save(caminho)


def _preencher_resumo(aba: Worksheet, resultado: Resultado) -> None:
    resumo = resultado.resumo
    aba.append(("Execução", resumo.execucao))
    aba.append(("Arquivos lidos", len(resumo.arquivos_lidos)))
    for lido in resumo.arquivos_lidos:
        aba.append((f"Lido: {lido}", ""))
    aba.append(("Arquivos recusados", len(resumo.arquivos_recusados)))
    for recusado in resumo.arquivos_recusados:
        aba.append((f"Recusado: {recusado.nome}", recusado.motivo))
    aba.append(("Lançamentos novos no Extrato", resumo.lancamentos_novos))
    for destino, total in resumo.totais.items():
        aba.append((destino.value, f"{total.quantidade} lançamento(s), {formatar_reais(total.valor_centavos)}"))
    aba.append(("Itens de Título na Fila", len(resultado.itens_de_titulo)))
    aba.append(("IA (parecer de nome)", _situacao_da_ia(resumo)))
    aba.column_dimensions["A"].width = 32
    aba.column_dimensions["B"].width = 60


def _situacao_da_ia(resumo: Resumo) -> str:
    if resumo.itens_ia_indisponivel:
        return (
            f"indisponível: {resumo.itens_ia_indisponivel} item(ns) da Fila sem parecer, marcados 'IA indisponível'; "
            f"{resumo.itens_com_parecer} item(ns) com parecer"
        )
    if resumo.itens_com_parecer:
        return f"funcionando: {resumo.itens_com_parecer} item(ns) da Fila com parecer"
    return "não foi necessária nesta execução"


def _aba_de_itens(aba: Worksheet, itens: list[Item], colunas_do_destino: tuple[str, ...]) -> None:
    aba.append(("Item", "Banco", "Conta", "Data", "Histórico", "Documento", "Valor", *colunas_do_destino))
    for item in itens:
        lancamento = item.lancamento
        valores_do_destino = {
            "Títulos": _titulos(item.titulos),
            "Títulos sugeridos": _titulos(item.titulos),
            "Motivo": item.motivo.value if item.motivo else "",
            "Evidência": "; ".join(tipo.value for tipo in item.evidencia),
            "O que falta": item.o_que_falta,
            "Explicação": item.explicacao,
            "Parecer da IA": "; ".join(parecer.descrever() for parecer in item.pareceres),
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


def _acrescentar_itens_de_titulo(aba: Worksheet, itens: tuple[ItemDeTitulo, ...]) -> None:
    for item in itens:
        sem_lancamento = (None,) * 6
        aba.append(
            (
                item.identificador,
                *sem_lancamento,
                item.motivo.value,
                _titulos(item.titulos),
                None,
                item.motivo.o_que_falta,
                item.explicacao,
            )
        )


def _aba_de_arquivos_recusados(aba: Worksheet, recusados: tuple[ArquivoRecusado, ...]) -> None:
    aba.append(("Arquivo", "Motivo"))
    for recusado in recusados:
        aba.append((recusado.nome, recusado.motivo))
    aba.column_dimensions["A"].width = 40
    aba.column_dimensions["B"].width = 100
    aba.freeze_panes = "A2"


def _titulos(titulos: tuple[Titulo, ...]) -> str:
    return "; ".join(f"{titulo.documento} ({titulo.sistema_de_origem})" for titulo in titulos)
