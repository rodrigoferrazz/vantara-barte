import re
import unicodedata
from datetime import date, datetime
from fractions import Fraction

_VALOR_PTBR = re.compile(r"\d{1,3}(\.\d{3})*,\d{2}")
_VALOR_COM_PONTO = re.compile(r"\d+\.\d{2}")
_DATA_PTBR = re.compile(r"\d{2}/\d{2}/\d{4}")
_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_CNPJ_SEM_PONTUACAO = re.compile(r"\d{14}")
_CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14}"
_CNPJ_INTEIRO = re.compile(_CNPJ)
_CNPJ_NO_TEXTO = re.compile(rf"(?<![\d./-])(?:{_CNPJ})(?![\d./-]*\d)")
_CPF_NO_TEXTO = re.compile(r"(?<![\d./-])(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?![\d./-]*\d)")


class FormatoInvalido(ValueError):
    pass


def centavos_de_valor_ptbr(texto: str) -> int:
    if not _VALOR_PTBR.fullmatch(texto):
        raise FormatoInvalido(f"valor '{texto}' não está no formato 1.234,56")
    return int(texto.replace(".", "").replace(",", ""))


def centavos_de_valor_com_ponto(texto: str) -> int:
    if not _VALOR_COM_PONTO.fullmatch(texto):
        raise FormatoInvalido(f"valor '{texto}' não está no formato 1234.56")
    return int(texto.replace(".", ""))


def data_ptbr(texto: str) -> date:
    if not _DATA_PTBR.fullmatch(texto):
        raise FormatoInvalido(f"data '{texto}' não está no formato dd/mm/aaaa")
    return _data(texto, "%d/%m/%Y")


def data_iso(texto: str) -> date:
    if not _DATA_ISO.fullmatch(texto):
        raise FormatoInvalido(f"data '{texto}' não está no formato aaaa-mm-dd")
    return _data(texto, "%Y-%m-%d")


def _data(texto: str, formato: str) -> date:
    try:
        return datetime.strptime(texto, formato).date()
    except ValueError as erro:
        raise FormatoInvalido(f"data '{texto}' não existe") from erro


def formatar_reais(centavos: int) -> str:
    reais, resto = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def formatar_percentual(percentual: Fraction, simbolo: bool = True) -> str:
    return f"{float(percentual):.1f}".replace(".", ",") + ("%" if simbolo else "")


def cnpj(texto: str) -> str:
    if not _CNPJ_INTEIRO.fullmatch(texto):
        raise FormatoInvalido(f"CNPJ '{texto}' não está no formato 00.000.000/0000-00 nem tem 14 dígitos")
    return _so_digitos(texto)


def cnpj_sem_pontuacao(texto: str) -> str:
    if not _CNPJ_SEM_PONTUACAO.fullmatch(texto):
        raise FormatoInvalido(f"CNPJ '{texto}' não tem 14 dígitos sem pontuação")
    return texto


def cnpjs_no_texto(texto: str) -> list[str]:
    return [_so_digitos(encontrado) for encontrado in _CNPJ_NO_TEXTO.findall(texto)]


def cpfs_no_texto(texto: str) -> list[str]:
    return [_so_digitos(encontrado) for encontrado in _CPF_NO_TEXTO.findall(texto)]


def raiz_do_cnpj(cnpj: str) -> str:
    return cnpj[:8]


def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def nome_normalizado(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", sem_acento.upper()).split())
