from datetime import date, timedelta
from functools import cache

_FERIADOS_FIXOS = ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25))
_CONSCIENCIA_NEGRA = (11, 20)
_PRIMEIRO_ANO_DA_CONSCIENCIA_NEGRA = 2024
_DESLOCAMENTOS_DA_PASCOA = (-48, -47, -2, 60)


def eh_dia_util(dia: date) -> bool:
    return dia.weekday() < 5 and dia not in _feriados_bancarios_nacionais(dia.year)


def vencimento_efetivo(vencimento: date) -> date:
    dia = vencimento
    while not eh_dia_util(dia):
        dia += timedelta(days=1)
    return dia


@cache
def _feriados_bancarios_nacionais(ano: int) -> frozenset[date]:
    pascoa = _pascoa(ano)
    return frozenset(
        [date(ano, mes, dia) for mes, dia in _FERIADOS_FIXOS]
        + [pascoa + timedelta(days=deslocamento) for deslocamento in _DESLOCAMENTOS_DA_PASCOA]
        + ([date(ano, *_CONSCIENCIA_NEGRA)] if ano >= _PRIMEIRO_ANO_DA_CONSCIENCIA_NEGRA else [])
    )


def _pascoa(ano: int) -> date:
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)
