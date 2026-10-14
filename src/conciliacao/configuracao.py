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
class ConfiguracaoDaIa:
    endereco: str
    modelo: str
    tempo_limite_segundos: float


@dataclass(frozen=True)
class Configuracao:
    contas: tuple[ContaDeExtrato, ...]
    encargo: ParametrosDeEncargo = ParametrosDeEncargo()
    limite_de_combinacoes: int = 100_000
    ia: ConfiguracaoDaIa | None = None
    limite_de_queda: Decimal = Decimal("10")


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
        contas=tuple(_conta(caminho, conta) for conta in contas),
        encargo=_encargo(caminho, dados.get("encargo", {})),
        limite_de_combinacoes=_limite_de_combinacoes(caminho, dados.get("somas", {})),
        ia=_ia(caminho, dados["ia"]) if "ia" in dados else None,
        limite_de_queda=_limite_de_queda(caminho, dados.get("resumo", {})),
    )


def _limite_de_queda(caminho: Path, resumo: object) -> Decimal:
    if not isinstance(resumo, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [resumo] precisa ser uma seção")
    campo = "limite_de_queda_pontos_percentuais"
    desconhecidos = sorted(set(resumo) - {campo})
    if desconhecidos:
        raise ConfiguracaoInvalida(f"{caminho}: [resumo] não conhece {', '.join(desconhecidos)}; use {campo}")
    limite = resumo.get(campo)
    if limite is None:
        return Configuracao.limite_de_queda
    if isinstance(limite, bool) or not isinstance(limite, int | float) or not 0 <= limite <= 100:
        raise ConfiguracaoInvalida(f"{caminho}: [resumo] {campo} precisa ser um número entre 0 e 100")
    return Decimal(str(limite))


_CAMPOS_DA_IA = ("endereco", "modelo", "tempo_limite_segundos")


def _ia(caminho: Path, ia: object) -> ConfiguracaoDaIa:
    if not isinstance(ia, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [ia] precisa ser uma seção")
    desconhecidos = sorted(set(ia) - set(_CAMPOS_DA_IA))
    if desconhecidos:
        raise ConfiguracaoInvalida(f"{caminho}: [ia] não conhece {', '.join(desconhecidos)}; use {', '.join(_CAMPOS_DA_IA)}")
    endereco, modelo, tempo_limite = ia.get("endereco"), ia.get("modelo"), ia.get("tempo_limite_segundos")
    if not isinstance(endereco, str) or not endereco or not isinstance(modelo, str) or not modelo:
        raise ConfiguracaoInvalida(f"{caminho}: [ia] precisa de endereco e modelo como texto")
    if isinstance(tempo_limite, bool) or not isinstance(tempo_limite, int | float) or tempo_limite <= 0:
        raise ConfiguracaoInvalida(f"{caminho}: [ia] tempo_limite_segundos precisa ser um número maior que zero")
    return ConfiguracaoDaIa(endereco=endereco, modelo=modelo, tempo_limite_segundos=float(tempo_limite))


def _conta(caminho: Path, conta: object) -> ContaDeExtrato:
    campos = ("padrao", "banco", "conta")
    if not isinstance(conta, dict) or not all(isinstance(conta.get(c), str) and conta[c] for c in campos):
        raise ConfiguracaoInvalida(f"{caminho}: cada [[contas]] precisa de padrao, banco e conta como texto")
    return ContaDeExtrato(padrao=conta["padrao"], banco=conta["banco"], conta=conta["conta"])


def _limite_de_combinacoes(caminho: Path, somas: object) -> int:
    if not isinstance(somas, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [somas] precisa ser uma seção")
    desconhecidos = sorted(set(somas) - {"limite_de_combinacoes"})
    if desconhecidos:
        raise ConfiguracaoInvalida(f"{caminho}: [somas] não conhece {', '.join(desconhecidos)}; use limite_de_combinacoes")
    limite = somas.get("limite_de_combinacoes", Configuracao.limite_de_combinacoes)
    if isinstance(limite, bool) or not isinstance(limite, int) or limite < 1:
        raise ConfiguracaoInvalida(f"{caminho}: [somas] limite_de_combinacoes precisa ser um número inteiro maior que zero")
    return limite


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
