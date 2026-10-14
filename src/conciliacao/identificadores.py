from collections.abc import Iterator, Set

from conciliacao.configuracao import FaixaDeNossoNumero

_PREFIXO_DO_TXID = "CI"
_DIGITOS_DO_TXID = 30


class FaixaDeNossoNumeroEsgotada(Exception):
    pass


def gerar_txid(sequencial: int) -> str:
    if not 0 < sequencial < 10**_DIGITOS_DO_TXID:
        raise ValueError(f"sequencial {sequencial} fora da faixa do txid")
    return f"{_PREFIXO_DO_TXID}{sequencial:0{_DIGITOS_DO_TXID}d}"


def nossos_numeros_livres(faixa: FaixaDeNossoNumero, usados: Set[str]) -> Iterator[str]:
    digitos = len(faixa.inicial)
    for numero in range(int(faixa.inicial), int(faixa.final) + 1):
        if (nosso_numero := f"{numero:0{digitos}d}") not in usados:
            yield nosso_numero
    raise FaixaDeNossoNumeroEsgotada(
        f"a faixa de nosso número {faixa.inicial} a {faixa.final} da conta {faixa.conta} ({faixa.banco}) está "
        "esgotada; configure uma nova faixa em [migracao.boleto]"
    )
