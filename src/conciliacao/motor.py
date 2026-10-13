from collections import defaultdict
from collections.abc import Iterable

from conciliacao.dominio import Classificacao, Destino, Lancamento, MotivoDeNaoIdentificacao, Natureza, Titulo
from conciliacao.normalizacao import formatar_reais


def conciliar(titulos: Iterable[Titulo], lancamentos: Iterable[Lancamento]) -> list[Classificacao]:
    por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
    for titulo in titulos:
        if titulo.nosso_numero:
            por_nosso_numero[titulo.nosso_numero].append(titulo)
    return [_classificar(lancamento, por_nosso_numero) for lancamento in lancamentos]


def _classificar(lancamento: Lancamento, por_nosso_numero: dict[str, list[Titulo]]) -> Classificacao:
    if lancamento.natureza is Natureza.DEBITO:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FORA_DO_ESCOPO,
            titulos=(),
            explicacao="Débito do Extrato; não é Crédito de Franqueado.",
        )
    candidatos = por_nosso_numero.get(lancamento.documento, []) if lancamento.documento else []
    if len(candidatos) == 1:
        return _por_nosso_numero(lancamento, candidatos[0])
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(),
        explicacao="Nenhuma regra identificou o pagador.",
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
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
