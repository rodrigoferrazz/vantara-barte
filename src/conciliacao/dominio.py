from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from conciliacao.normalizacao import raiz_do_cnpj


class Destino(StrEnum):
    LISTA_DE_BAIXA = "Lista de baixa"
    FILA_DE_EXCECOES = "Fila de exceções"
    FORA_DO_ESCOPO = "Fora do escopo"


class Natureza(StrEnum):
    CREDITO = "C"
    DEBITO = "D"


class MotivoDeNaoIdentificacao(StrEnum):
    SEM_IDENTIFICACAO_DO_PAGADOR = "sem identificação do pagador"
    NOME_AMBIGUO = "nome ambíguo"
    VALOR_NAO_FECHA = "valor não fecha"
    CREDITO_SEM_TITULO_EM_ABERTO = "Crédito sem título em aberto"
    MAIS_DE_UMA_COMBINACAO = "mais de uma combinação possível"
    POSSIVEL_DUPLICIDADE = "Possível duplicidade entre sistemas"
    POSSIVEL_FONTE_NAO_INTEGRADA = "Possível fonte não integrada"
    PAGADOR_PROVAVEL_PRIMEIRA_VEZ = "pagador provável, primeira vez"


@dataclass(frozen=True)
class Titulo:
    sistema_de_origem: str
    documento: str
    cliente: str
    cnpj: str
    nosso_numero: str | None
    vencimento: date
    valor_centavos: int

    @property
    def franqueado(self) -> str:
        return raiz_do_cnpj(self.cnpj)


@dataclass(frozen=True)
class Franqueado:
    raiz: str
    nomes: dict[str, frozenset[str]]

    @property
    def todos_os_nomes(self) -> frozenset[str]:
        return frozenset().union(*self.nomes.values())


@dataclass(frozen=True)
class PossivelDuplicidade:
    titulos: tuple[Titulo, ...]
    explicacao: str


type ChaveNatural = tuple[str, str, date, Natureza, int, str, str, int]


@dataclass(frozen=True)
class Lancamento:
    banco: str
    conta: str
    data: date
    historico: str
    documento: str
    valor_centavos: int
    natureza: Natureza
    ordinal: int

    @property
    def chave_natural(self) -> ChaveNatural:
        return (
            self.banco,
            self.conta,
            self.data,
            self.natureza,
            self.valor_centavos,
            self.historico,
            self.documento,
            self.ordinal,
        )


@dataclass(frozen=True)
class Classificacao:
    lancamento: Lancamento
    destino: Destino
    titulos: tuple[Titulo, ...]
    explicacao: str
    motivo: MotivoDeNaoIdentificacao | None = None


@dataclass(frozen=True)
class Item:
    identificador: str
    destino: Destino
    lancamento: Lancamento
    titulos: tuple[Titulo, ...]
    explicacao: str
    motivo: MotivoDeNaoIdentificacao | None


@dataclass(frozen=True)
class ItemDeTitulo:
    identificador: str
    titulos: tuple[Titulo, ...]
    explicacao: str
    motivo: MotivoDeNaoIdentificacao


@dataclass(frozen=True)
class ArquivoRecusado:
    nome: str
    motivo: str


@dataclass(frozen=True)
class TotalDoDestino:
    quantidade: int
    valor_centavos: int


@dataclass(frozen=True)
class Resumo:
    execucao: int
    arquivos_lidos: tuple[str, ...]
    arquivos_recusados: tuple[ArquivoRecusado, ...]
    lancamentos_novos: int
    totais: dict[Destino, TotalDoDestino]


@dataclass(frozen=True)
class Resultado:
    resumo: Resumo
    itens: tuple[Item, ...]
    itens_de_titulo: tuple[ItemDeTitulo, ...]

    def _do_destino(self, destino: Destino) -> list[Item]:
        return [item for item in self.itens if item.destino is destino]

    @property
    def lista_de_baixa(self) -> list[Item]:
        return self._do_destino(Destino.LISTA_DE_BAIXA)

    @property
    def fila_de_excecoes(self) -> list[Item]:
        return self._do_destino(Destino.FILA_DE_EXCECOES)

    @property
    def fora_do_escopo(self) -> list[Item]:
        return self._do_destino(Destino.FORA_DO_ESCOPO)

    @property
    def arquivos_recusados(self) -> tuple[ArquivoRecusado, ...]:
        return self.resumo.arquivos_recusados
