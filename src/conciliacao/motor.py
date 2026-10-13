from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from conciliacao.dominio import Classificacao, Destino, Lancamento, MotivoDeNaoIdentificacao, Natureza, Titulo
from conciliacao.normalizacao import cnpjs_no_texto, formatar_reais, raiz_do_cnpj


@dataclass(frozen=True)
class _Titulos:
    por_nosso_numero: dict[str, list[Titulo]]
    por_franqueado: dict[str, list[Titulo]]
    franqueados: frozenset[str]


def conciliar(
    titulos: Iterable[Titulo], lancamentos: Iterable[Lancamento], franqueados_conhecidos: Iterable[str]
) -> list[Classificacao]:
    por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
    por_franqueado: dict[str, list[Titulo]] = defaultdict(list)
    for titulo in titulos:
        if titulo.nosso_numero:
            por_nosso_numero[titulo.nosso_numero].append(titulo)
        por_franqueado[titulo.franqueado].append(titulo)
    abertos = _Titulos(por_nosso_numero, por_franqueado, frozenset(franqueados_conhecidos) | por_franqueado.keys())
    return [_classificar(lancamento, abertos) for lancamento in lancamentos]


def _classificar(lancamento: Lancamento, abertos: _Titulos) -> Classificacao:
    if lancamento.natureza is Natureza.DEBITO:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FORA_DO_ESCOPO,
            titulos=(),
            explicacao="Débito do Extrato; não é Crédito de Franqueado.",
        )
    candidatos = abertos.por_nosso_numero.get(lancamento.documento, []) if lancamento.documento else []
    if len(candidatos) == 1:
        return _por_nosso_numero(lancamento, candidatos[0])
    if not candidatos:
        documentos = [c for c in cnpjs_no_texto(lancamento.historico) if raiz_do_cnpj(c) in abertos.franqueados]
        if len({raiz_do_cnpj(c) for c in documentos}) == 1:
            franqueado = raiz_do_cnpj(documentos[0])
            return _por_documento(lancamento, documentos[0], abertos.por_franqueado.get(franqueado, []))
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(),
        explicacao="Nenhuma regra identificou o pagador.",
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
    )


def _por_documento(lancamento: Lancamento, documento: str, titulos: list[Titulo]) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    pagador = f"CNPJ {documento} no histórico identifica o Franqueado de raiz {raiz_do_cnpj(documento)}"
    if not titulos:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=(),
            explicacao=f"{pagador}, que não tem Título em aberto.",
            motivo=MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO,
        )
    mesmo_valor = [titulo for titulo in titulos if titulo.valor_centavos == lancamento.valor_centavos]
    if len(mesmo_valor) == 1:
        [titulo] = mesmo_valor
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=(
                f"{pagador}; o valor {valor} é Valor único entre os Títulos em aberto dele: "
                f"Título {titulo.documento} ({titulo.sistema_de_origem})."
            ),
        )
    if mesmo_valor:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=(),
            explicacao=(
                f"{pagador}, mas o valor {valor} corresponde a mais de um Título em aberto dele: "
                f"{_documentos(mesmo_valor)}."
            ),
            motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=tuple(titulos) if len(titulos) == 1 else (),
        explicacao=(
            f"{pagador}, mas o valor {valor} não corresponde a nenhum Título em aberto dele: "
            f"{_documentos(titulos)}."
        ),
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
    )


def _documentos(titulos: list[Titulo]) -> str:
    return ", ".join(
        f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})" for titulo in titulos
    )


def _por_nosso_numero(lancamento: Lancamento, titulo: Titulo) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    if lancamento.valor_centavos == titulo.valor_centavos:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=(
                f"Nosso número {titulo.nosso_numero} é do Título {titulo.documento} ({titulo.sistema_de_origem}) "
                f"e o valor {valor} é exatamente o valor do Título."
            ),
        )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(titulo,),
        explicacao=(
            f"Nosso número {titulo.nosso_numero} é do Título {titulo.documento} ({titulo.sistema_de_origem}), "
            f"mas o valor {valor} difere do valor do Título, {formatar_reais(titulo.valor_centavos)}."
        ),
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
    )
