_PREFIXO_DO_TXID = "CI"
_DIGITOS_DO_TXID = 30


def gerar_txid(sequencial: int) -> str:
    if not 0 < sequencial < 10**_DIGITOS_DO_TXID:
        raise ValueError(f"sequencial {sequencial} fora da faixa do txid")
    return f"{_PREFIXO_DO_TXID}{sequencial:0{_DIGITOS_DO_TXID}d}"
