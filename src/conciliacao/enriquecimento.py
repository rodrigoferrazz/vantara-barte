from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from conciliacao.dominio import Lancamento, Natureza, RetornoDeCobranca

type _Par = tuple[str, str, date, int]


def enriquecer(
    retornos: Iterable[RetornoDeCobranca], creditos: Iterable[Lancamento]
) -> list[tuple[RetornoDeCobranca, Lancamento]]:
    retornos_por_par: dict[_Par, list[RetornoDeCobranca]] = defaultdict(list)
    for retorno in retornos:
        retornos_por_par[(retorno.banco, retorno.conta, retorno.data, retorno.valor_centavos)].append(retorno)
    creditos_por_par: dict[_Par, list[Lancamento]] = defaultdict(list)
    for credito in creditos:
        if credito.natureza is Natureza.CREDITO:
            creditos_por_par[(credito.banco, credito.conta, credito.data, credito.valor_centavos)].append(credito)
    return [
        (do_par[0], creditos_por_par[par][0])
        for par, do_par in retornos_por_par.items()
        if len(do_par) == 1 and len(creditos_por_par.get(par, [])) == 1
    ]
