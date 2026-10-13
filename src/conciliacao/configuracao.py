import tomllib
from dataclasses import dataclass
from pathlib import Path


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


def carregar_configuracao(caminho: Path) -> Configuracao:
    with caminho.open("rb") as arquivo:
        try:
            dados = tomllib.load(arquivo)
        except tomllib.TOMLDecodeError as erro:
            raise ConfiguracaoInvalida(f"{caminho}: {erro}") from None
    contas = dados.get("contas")
    if not isinstance(contas, list) or not contas:
        raise ConfiguracaoInvalida(f"{caminho}: faltam as [[contas]] com padrao, banco e conta")
    return Configuracao(contas=tuple(_conta(caminho, conta) for conta in contas))


def _conta(caminho: Path, conta: object) -> ContaDeExtrato:
    campos = ("padrao", "banco", "conta")
    if not isinstance(conta, dict) or not all(isinstance(conta.get(c), str) and conta[c] for c in campos):
        raise ConfiguracaoInvalida(f"{caminho}: cada [[contas]] precisa de padrao, banco e conta como texto")
    return ContaDeExtrato(padrao=conta["padrao"], banco=conta["banco"], conta=conta["conta"])
