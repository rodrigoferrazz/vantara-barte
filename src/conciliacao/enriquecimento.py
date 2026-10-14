from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from conciliacao.dominio import Lancamento, Natureza, RetornoDeCobranca, RetornoSemCredito
from conciliacao.normalizacao import cnpjs_no_texto, cpfs_no_texto, nome_normalizado

type _Par = tuple[str, str, date, int]
type _Ligacao = tuple[RetornoDeCobranca, Lancamento]


@dataclass(frozen=True)
class Enriquecimento:
    ligacoes: list[_Ligacao]
    sem_credito: list[RetornoSemCredito]


def enriquecer(
    retornos: Iterable[RetornoDeCobranca],
    creditos: Iterable[Lancamento],
    nome_do_pagador: Callable[[Lancamento], str | None],
) -> Enriquecimento:
    por_par: dict[_Par, tuple[list[RetornoDeCobranca], list[Lancamento]]] = defaultdict(lambda: ([], []))
    for retorno in retornos:
        por_par[(retorno.banco, retorno.conta, retorno.data, retorno.valor_centavos)][0].append(retorno)
    for credito in creditos:
        if credito.natureza is Natureza.CREDITO:
            por_par[(credito.banco, credito.conta, credito.data, credito.valor_centavos)][1].append(credito)
    ligacoes: list[_Ligacao] = []
    sem_credito: list[RetornoSemCredito] = []
    for do_par, candidatos in por_par.values():
        while ligadas := _ligacoes_unicas(do_par, candidatos, nome_do_pagador):
            ligacoes.extend(ligadas)
            do_par = [r for r in do_par if r not in {r for r, _ in ligadas}]
            candidatos = [c for c in candidatos if c not in {c for _, c in ligadas}]
        sem_credito.extend(RetornoSemCredito(retorno, len(candidatos), len(do_par)) for retorno in do_par)
    return Enriquecimento(ligacoes, sem_credito)


def _ligacoes_unicas(
    retornos: list[RetornoDeCobranca],
    creditos: list[Lancamento],
    nome_do_pagador: Callable[[Lancamento], str | None],
) -> list[_Ligacao]:
    if len(retornos) == 1 and len(creditos) == 1:
        return [(retornos[0], creditos[0])]
    pelo_pagador = [(r, c) for r in retornos for c in creditos if _mesmo_pagador(r, c, nome_do_pagador)]
    por_retorno = Counter(r for r, _ in pelo_pagador)
    por_credito = Counter(c for _, c in pelo_pagador)
    return [(r, c) for r, c in pelo_pagador if por_retorno[r] == 1 and por_credito[c] == 1]


def _mesmo_pagador(
    retorno: RetornoDeCobranca, credito: Lancamento, nome_do_pagador: Callable[[Lancamento], str | None]
) -> bool:
    documento = retorno.documento_do_pagador
    if documento and documento in {*cnpjs_no_texto(credito.historico), *cpfs_no_texto(credito.historico)}:
        return True
    do_retorno = nome_normalizado(retorno.nome_do_pagador or "")
    nome = nome_do_pagador(credito)
    do_extrato = nome_normalizado(nome) if nome else ""
    return bool(do_retorno and do_extrato) and (
        do_retorno.startswith(do_extrato) or do_extrato.startswith(do_retorno)
    )
