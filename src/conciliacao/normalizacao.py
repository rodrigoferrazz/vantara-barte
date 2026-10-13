import re
from datetime import date, datetime

_VALOR_PTBR = re.compile(r"\d{1,3}(\.\d{3})*,\d{2}")
_DATA_PTBR = re.compile(r"\d{2}/\d{2}/\d{4}")


class FormatoInvalido(ValueError):
    pass


def centavos_de_valor_ptbr(texto: str) -> int:
    if not _VALOR_PTBR.fullmatch(texto):
        raise FormatoInvalido(f"valor '{texto}' não está no formato 1.234,56")
    return int(texto.replace(".", "").replace(",", ""))


def data_ptbr(texto: str) -> date:
    if not _DATA_PTBR.fullmatch(texto):
        raise FormatoInvalido(f"data '{texto}' não está no formato dd/mm/aaaa")
    try:
        return datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError as erro:
        raise FormatoInvalido(f"data '{texto}' não existe") from erro


def formatar_reais(centavos: int) -> str:
    reais, resto = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"
