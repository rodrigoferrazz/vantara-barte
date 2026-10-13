import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from conciliacao.encargo import ParametrosDeEncargo


class ConfiguracaoInvalida(ValueError):
    pass


@dataclass(frozen=True)
class ContaDeExtrato:
    padrao: str
    banco: str
    conta: str


@dataclass(frozen=True)
class Configuracao:
    contas: tuple[ContaDeExtrato, ...]
    encargo: ParametrosDeEncargo = ParametrosDeEncargo()


def carregar_configuracao(caminho: Path) -> Configuracao:
    with caminho.open("rb") as arquivo:
        try:
            dados = tomllib.load(arquivo)
        except tomllib.TOMLDecodeError as erro:
            raise ConfiguracaoInvalida(f"{caminho}: {erro}") from None
    contas = dados.get("contas")
    if not isinstance(contas, list) or not contas:
        raise ConfiguracaoInvalida(f"{caminho}: faltam as [[contas]] com padrao, banco e conta")
    return Configuracao(
        contas=tuple(_conta(caminho, conta) for conta in contas), encargo=_encargo(caminho, dados.get("encargo", {}))
    )


def _conta(caminho: Path, conta: object) -> ContaDeExtrato:
    campos = ("padrao", "banco", "conta")
    if not isinstance(conta, dict) or not all(isinstance(conta.get(c), str) and conta[c] for c in campos):
        raise ConfiguracaoInvalida(f"{caminho}: cada [[contas]] precisa de padrao, banco e conta como texto")
    return ContaDeExtrato(padrao=conta["padrao"], banco=conta["banco"], conta=conta["conta"])


_CAMPOS_DE_ENCARGO = ("multa_percentual", "juros_ao_mes_percentual", "tolerancia_reais")


def _encargo(caminho: Path, encargo: object) -> ParametrosDeEncargo:
    if not isinstance(encargo, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [encargo] precisa ser uma seção")
    desconhecidos = sorted(set(encargo) - set(_CAMPOS_DE_ENCARGO))
    if desconhecidos:
        raise ConfiguracaoInvalida(
            f"{caminho}: [encargo] não conhece {', '.join(desconhecidos)}; use {', '.join(_CAMPOS_DE_ENCARGO)}"
        )
    padrao = ParametrosDeEncargo()
    tolerancia = _numero(caminho, encargo, "tolerancia_reais", Decimal(padrao.tolerancia_centavos) / 100)
    if tolerancia != tolerancia.quantize(Decimal("0.01")):
        raise ConfiguracaoInvalida(f"{caminho}: [encargo] tolerancia_reais não pode ter fração de centavo")
    return ParametrosDeEncargo(
        multa_percentual=_numero(caminho, encargo, "multa_percentual", padrao.multa_percentual),
        juros_ao_mes_percentual=_numero(caminho, encargo, "juros_ao_mes_percentual", padrao.juros_ao_mes_percentual),
        tolerancia_centavos=int(tolerancia * 100),
    )


def _numero(caminho: Path, encargo: dict[str, object], campo: str, padrao: Decimal) -> Decimal:
    valor = encargo.get(campo)
    if valor is None:
        return padrao
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor < 0:
        raise ConfiguracaoInvalida(f"{caminho}: [encargo] {campo} precisa ser um número maior ou igual a zero")
    return Decimal(str(valor))
