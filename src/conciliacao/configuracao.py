import re
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
class FaixaDeNossoNumero:
    banco: str
    conta: str
    inicial: str
    final: str


@dataclass(frozen=True)
class ConfiguracaoDeMigracao:
    franqueados: frozenset[str]
    boleto: FaixaDeNossoNumero | None = None


@dataclass(frozen=True)
class ConfiguracaoDaAnaliseDeImpacto:
    semente: int = 1
    tamanho_da_onda: int = 10


@dataclass(frozen=True)
class Configuracao:
    contas: tuple[ContaDeExtrato, ...]
    encargo: ParametrosDeEncargo = ParametrosDeEncargo()
    limite_de_combinacoes: int = 100_000
    ia: ConfiguracaoDaIa | None = None
    limite_de_queda: Decimal = Decimal("10")
    migracao: ConfiguracaoDeMigracao | None = None
    analise_de_impacto: ConfiguracaoDaAnaliseDeImpacto = ConfiguracaoDaAnaliseDeImpacto()


def carregar_configuracao(caminho: Path) -> Configuracao:
    with caminho.open("rb") as arquivo:
        try:
            dados = tomllib.load(arquivo)
        except tomllib.TOMLDecodeError as erro:
            raise ConfiguracaoInvalida(f"{caminho}: {erro}") from None
    contas = dados.get("contas")
    if not isinstance(contas, list) or not contas:
        raise ConfiguracaoInvalida(f"{caminho}: faltam as [[contas]] com padrao, banco e conta")
    contas_lidas = tuple(_conta(caminho, conta) for conta in contas)
    return Configuracao(
        contas=contas_lidas,
        encargo=_encargo(caminho, dados.get("encargo", {})),
        limite_de_combinacoes=_limite_de_combinacoes(caminho, dados.get("somas", {})),
        ia=_ia(caminho, dados["ia"]) if "ia" in dados else None,
        limite_de_queda=_limite_de_queda(caminho, dados.get("resumo", {})),
        migracao=_migracao(caminho, dados["migracao"], contas_lidas) if "migracao" in dados else None,
        analise_de_impacto=_analise_de_impacto(caminho, dados.get("analise_de_impacto", {})),
    )


def _analise_de_impacto(caminho: Path, analise: object) -> ConfiguracaoDaAnaliseDeImpacto:
    if not isinstance(analise, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [analise_de_impacto] precisa ser uma seção")
    desconhecidos = sorted(set(analise) - {"semente", "tamanho_da_onda"})
    if desconhecidos:
        raise ConfiguracaoInvalida(
            f"{caminho}: [analise_de_impacto] não conhece {', '.join(desconhecidos)}; use semente e tamanho_da_onda"
        )
    padrao = ConfiguracaoDaAnaliseDeImpacto()
    semente = analise.get("semente", padrao.semente)
    tamanho_da_onda = analise.get("tamanho_da_onda", padrao.tamanho_da_onda)
    if isinstance(semente, bool) or not isinstance(semente, int) or semente < 0:
        raise ConfiguracaoInvalida(
            f"{caminho}: [analise_de_impacto] semente precisa ser um número inteiro maior ou igual a zero"
        )
    if isinstance(tamanho_da_onda, bool) or not isinstance(tamanho_da_onda, int) or tamanho_da_onda < 1:
        raise ConfiguracaoInvalida(
            f"{caminho}: [analise_de_impacto] tamanho_da_onda precisa ser um número inteiro de Franqueados maior que zero"
        )
    return ConfiguracaoDaAnaliseDeImpacto(semente=semente, tamanho_da_onda=tamanho_da_onda)


_RAIZ_DO_CNPJ = re.compile(r"\d{8}")


def _migracao(caminho: Path, migracao: object, contas: tuple[ContaDeExtrato, ...]) -> ConfiguracaoDeMigracao:
    if not isinstance(migracao, dict):
        raise ConfiguracaoInvalida(f"{caminho}: [migracao] precisa ser uma seção")
    desconhecidos = sorted(set(migracao) - {"franqueados", "boleto"})
    if desconhecidos:
        raise ConfiguracaoInvalida(
            f"{caminho}: [migracao] não conhece {', '.join(desconhecidos)}; use franqueados e boleto"
        )
    franqueados = migracao.get("franqueados")
    if not isinstance(franqueados, list) or not all(
        isinstance(raiz, str) and _RAIZ_DO_CNPJ.fullmatch(raiz) for raiz in franqueados
    ):
        raise ConfiguracaoInvalida(
            f"{caminho}: [migracao] franqueados precisa ser uma lista de raízes de CNPJ, 8 dígitos sem pontuação"
        )
    return ConfiguracaoDeMigracao(
        franqueados=frozenset(franqueados),
        boleto=_boleto(caminho, migracao["boleto"], contas) if "boleto" in migracao else None,
    )


_CAMPOS_DO_BOLETO = ("banco", "conta", "nosso_numero_inicial", "nosso_numero_final")
_NOSSO_NUMERO = re.compile(r"\d{1,20}")


def _boleto(caminho: Path, boleto: object, contas: tuple[ContaDeExtrato, ...]) -> FaixaDeNossoNumero:
    secao = "[migracao.boleto]"
    if not isinstance(boleto, dict):
        raise ConfiguracaoInvalida(f"{caminho}: {secao} precisa ser uma seção")
    desconhecidos = sorted(set(boleto) - set(_CAMPOS_DO_BOLETO))
    if desconhecidos:
        raise ConfiguracaoInvalida(
            f"{caminho}: {secao} não conhece {', '.join(desconhecidos)}; use {', '.join(_CAMPOS_DO_BOLETO)}"
        )
    if not all(isinstance(boleto.get(campo), str) and boleto[campo] for campo in _CAMPOS_DO_BOLETO):
        raise ConfiguracaoInvalida(f"{caminho}: {secao} precisa de {', '.join(_CAMPOS_DO_BOLETO)} como texto")
    faixa = FaixaDeNossoNumero(
        banco=boleto["banco"],
        conta=boleto["conta"],
        inicial=boleto["nosso_numero_inicial"],
        final=boleto["nosso_numero_final"],
    )
    if not any((conta.banco, conta.conta) == (faixa.banco, faixa.conta) for conta in contas):
        raise ConfiguracaoInvalida(
            f"{caminho}: {secao} banco '{faixa.banco}' e conta '{faixa.conta}' não estão em nenhuma [[contas]]"
        )
    if not (_NOSSO_NUMERO.fullmatch(faixa.inicial) and _NOSSO_NUMERO.fullmatch(faixa.final)):
        raise ConfiguracaoInvalida(
            f"{caminho}: {secao} nosso_numero_inicial e nosso_numero_final precisam ter só dígitos, até 20 "
            "(o tamanho do nosso número no CNAB 240)"
        )
    if len(faixa.inicial) != len(faixa.final):
        raise ConfiguracaoInvalida(
            f"{caminho}: {secao} nosso_numero_inicial e nosso_numero_final precisam ter o mesmo número de dígitos"
        )
    if faixa.inicial > faixa.final:
        raise ConfiguracaoInvalida(f"{caminho}: {secao} nosso_numero_inicial é maior que nosso_numero_final")
    return faixa


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
