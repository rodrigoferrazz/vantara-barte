from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from conciliacao.dominio import Classificacao, Destino, Lancamento, MotivoDeNaoIdentificacao, Natureza, Titulo
from conciliacao.encargo import ParametrosDeEncargo, enquadrar
from conciliacao.normalizacao import cnpjs_no_texto, formatar_reais, raiz_do_cnpj


@dataclass(frozen=True)
class _Titulos:
    por_nosso_numero: dict[str, list[Titulo]]
    por_franqueado: dict[str, list[Titulo]]
    franqueados: frozenset[str]
    encargo: ParametrosDeEncargo


def conciliar(
    titulos: Iterable[Titulo],
    lancamentos: Iterable[Lancamento],
    franqueados_conhecidos: Iterable[str],
    encargo: ParametrosDeEncargo,
) -> list[Classificacao]:
    por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
    por_franqueado: dict[str, list[Titulo]] = defaultdict(list)
    for titulo in titulos:
        if titulo.nosso_numero:
            por_nosso_numero[titulo.nosso_numero].append(titulo)
        por_franqueado[titulo.franqueado].append(titulo)
    abertos = _Titulos(
        por_nosso_numero, por_franqueado, frozenset(franqueados_conhecidos) | por_franqueado.keys(), encargo
    )
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
        return _por_nosso_numero(lancamento, candidatos[0], abertos.encargo)
    if not candidatos:
        documentos = [c for c in cnpjs_no_texto(lancamento.historico) if raiz_do_cnpj(c) in abertos.franqueados]
        if len({raiz_do_cnpj(c) for c in documentos}) == 1:
            franqueado = raiz_do_cnpj(documentos[0])
            return _por_documento(
                lancamento, documentos[0], abertos.por_franqueado.get(franqueado, []), abertos.encargo
            )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(),
        explicacao="Nenhuma regra identificou o pagador.",
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
    )


def _por_documento(
    lancamento: Lancamento, documento: str, titulos: list[Titulo], encargo: ParametrosDeEncargo
) -> Classificacao:
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
    que_fecham = [
        (titulo, pagamento)
        for titulo in titulos
        if (pagamento := enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo)).fecha
    ]
    if len(que_fecham) == 1:
        [(titulo, pagamento)] = que_fecham
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=(
                f"{pagador}; o valor {valor} é Valor único entre os Títulos em aberto dele: "
                f"Título {titulo.documento} ({titulo.sistema_de_origem}), {pagamento.descrever()}."
            ),
        )
    mesmo_valor = [titulo for titulo, _ in que_fecham]
    if mesmo_valor:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=(),
            explicacao=(
                f"{pagador}, mas o valor {valor} fecha com mais de um Título em aberto dele, considerando o Encargo: "
                f"{_documentos(mesmo_valor)}."
            ),
            motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        )
    detalhe = (
        f"; {enquadrar(titulos[0], lancamento.valor_centavos, lancamento.data, encargo).descrever()}"
        if len(titulos) == 1
        else ""
    )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=tuple(titulos) if len(titulos) == 1 else (),
        explicacao=(
            f"{pagador}, mas o valor {valor} não fecha com nenhum Título em aberto dele, considerando o Encargo: "
            f"{_documentos(titulos)}{detalhe}."
        ),
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
    )


def _documentos(titulos: list[Titulo]) -> str:
    return ", ".join(
        f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})" for titulo in titulos
    )


def _por_nosso_numero(lancamento: Lancamento, titulo: Titulo, encargo: ParametrosDeEncargo) -> Classificacao:
    pagamento = enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo)
    identificacao = (
        f"Nosso número {titulo.nosso_numero} é do Título {titulo.documento} ({titulo.sistema_de_origem}); "
        f"valor {formatar_reais(lancamento.valor_centavos)}: {pagamento.descrever()}."
    )
    if pagamento.fecha:
        return Classificacao(
            lancamento=lancamento, destino=Destino.LISTA_DE_BAIXA, titulos=(titulo,), explicacao=identificacao
        )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(titulo,),
        explicacao=identificacao,
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
    )
