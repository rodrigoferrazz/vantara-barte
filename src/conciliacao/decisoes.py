from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from conciliacao.armazenamento import Armazenamento
from conciliacao.dominio import DecisoesLidas, Item, TipoDeDecisao
from conciliacao.encargo import ParametrosDeEncargo, enquadrar
from conciliacao.saidas import (
    ABA_DA_LISTA_DE_BAIXA,
    COLUNA_DA_DECISAO,
    COLUNA_DO_ITEM,
    COLUNA_DO_MOTIVO_DA_REJEICAO,
    LINHA_DA_EXECUCAO_NO_RESUMO,
)

ORIGEM_EXCEL = "Excel"


@dataclass(frozen=True)
class _LinhaDeDecisao:
    item: str
    decisao: str
    motivo: str


@dataclass(frozen=True)
class _WorkbookLido:
    execucao: object
    autor: str
    momento: datetime | None
    linhas: tuple[_LinhaDeDecisao, ...]


@dataclass(frozen=True)
class DecisoesAplicadas:
    lidas: DecisoesLidas
    registradas: tuple[int, ...]


def aplicar_decisoes_do_excel(
    caminho: Path, armazenamento: Armazenamento, encargo: ParametrosDeEncargo, agora: datetime
) -> DecisoesAplicadas:
    try:
        lido = _ler(caminho)
    except (OSError, KeyError, ValueError, BadZipFile, InvalidFileException) as erro:
        return _nada_aplicado(f"O workbook {caminho.name} não pôde ser lido ({erro}); nenhuma decisão aplicada.")
    ultima = armazenamento.ultima_execucao()
    if not lido.autor:
        return _nada_aplicado(
            f"O workbook {caminho.name} não foi salvo pela Analista (sem autor da última alteração); "
            "nenhuma decisão aplicada."
        )
    if ultima is None or lido.execucao != ultima:
        return _nada_aplicado(
            f"O workbook {caminho.name} é da execução {lido.execucao}, mas a última execução é a execução {ultima}; "
            "nenhuma decisão aplicada."
        )
    lista = {item.identificador: item for item in armazenamento.carregar_resultado(ultima).lista_de_baixa}
    repetidos = {item for item, vezes in Counter(linha.item for linha in lido.linhas).items() if vezes > 1}
    avisos: list[str] = []
    registradas: list[int] = []
    tipos: list[TipoDeDecisao] = []
    for linha in lido.linhas:
        item = lista.get(linha.item)
        if item is None:
            avisos.append(f"Item {linha.item}: não está na Lista de baixa da execução {ultima}; decisão ignorada.")
            continue
        if linha.item in repetidos:
            avisos.append(f"Item {linha.item}: aparece mais de uma vez na Lista de baixa; decisão não aplicada.")
            continue
        tipo = _tipo(linha.decisao)
        if tipo is None:
            avisos.append(
                f"Item {linha.item}: decisão '{linha.decisao}' não reconhecida "
                "(use 'confirmar', ou deixe vazio ou 'rejeitar' com motivo); não aplicada."
            )
            continue
        if tipo is TipoDeDecisao.REJEITAR and not linha.motivo:
            avisos.append(f"Item {linha.item}: rejeição sem motivo; não aplicada.")
            continue
        registradas.append(
            armazenamento.registrar_decisao(
                execucao=ultima,
                item=item.identificador,
                tipo=tipo,
                motivo=linha.motivo if tipo is TipoDeDecisao.REJEITAR else None,
                autor=lido.autor,
                momento=lido.momento or agora,
                origem=ORIGEM_EXCEL,
                encargos=_encargos(item, encargo),
            )
        )
        tipos.append(tipo)
    return DecisoesAplicadas(
        DecisoesLidas(
            confirmadas=tipos.count(TipoDeDecisao.CONFIRMAR),
            rejeitadas=tipos.count(TipoDeDecisao.REJEITAR),
            nao_aplicadas=tuple(avisos),
        ),
        tuple(registradas),
    )


def _nada_aplicado(aviso: str) -> DecisoesAplicadas:
    return DecisoesAplicadas(DecisoesLidas(nao_aplicadas=(aviso,)), ())


def _tipo(decisao: str) -> TipoDeDecisao | None:
    normalizada = decisao.strip().lower()
    if normalizada == TipoDeDecisao.CONFIRMAR.value:
        return TipoDeDecisao.CONFIRMAR
    if normalizada in ("", TipoDeDecisao.REJEITAR.value):
        return TipoDeDecisao.REJEITAR
    return None


def _encargos(item: Item, encargo: ParametrosDeEncargo) -> dict[tuple[str, str], int]:
    credito = item.lancamento
    return {
        (titulo.sistema_de_origem, titulo.documento): enquadrar(
            titulo,
            credito.valor_centavos if len(item.titulos) == 1 else titulo.valor_centavos,
            credito.data,
            encargo,
        ).encargo_pago_centavos
        for titulo in item.titulos
    }


def _ler(caminho: Path) -> _WorkbookLido:
    livro = load_workbook(caminho, read_only=True)
    try:
        execucao = next(
            (
                linha[1]
                for linha in livro["Resumo"].iter_rows(values_only=True)
                if linha and linha[0] == LINHA_DA_EXECUCAO_NO_RESUMO
            ),
            None,
        )
        cabecalho, *linhas = livro[ABA_DA_LISTA_DE_BAIXA].iter_rows(values_only=True)
        colunas = [str(c) for c in cabecalho]
        item, decisao, motivo = (
            colunas.index(COLUNA_DO_ITEM),
            colunas.index(COLUNA_DA_DECISAO),
            colunas.index(COLUNA_DO_MOTIVO_DA_REJEICAO),
        )
        return _WorkbookLido(
            execucao=execucao,
            autor=(livro.properties.lastModifiedBy or "").strip(),
            momento=livro.properties.modified,
            linhas=tuple(
                _LinhaDeDecisao(_celula(linha, item), _celula(linha, decisao), _celula(linha, motivo))
                for linha in linhas
                if _celula(linha, item)
            ),
        )
    finally:
        livro.close()


def _celula(linha: tuple[object, ...], coluna: int) -> str:
    valor = linha[coluna] if coluna < len(linha) else None
    return "" if valor is None else str(valor).strip()
