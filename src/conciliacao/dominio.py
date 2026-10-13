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

    @property
    def o_que_falta(self) -> str:
        return _O_QUE_FALTA[self]


_O_QUE_FALTA = {
    MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR: "identificar o pagador do Crédito",
    MotivoDeNaoIdentificacao.NOME_AMBIGUO: "decidir de qual Franqueado é o Crédito",
    MotivoDeNaoIdentificacao.VALOR_NAO_FECHA: (
        "explicar a diferença entre o Crédito e o valor do Título (desconto, retenção, pagamento parcial ou Valor a maior)"
    ),
    MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO: (
        "Título em aberto do Franqueado para o Crédito; ele é retentado a cada nova importação"
    ),
    MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO: "escolher entre os Títulos que fecham o valor",
    MotivoDeNaoIdentificacao.POSSIVEL_DUPLICIDADE: "decidir se os Títulos são a mesma dívida",
    MotivoDeNaoIdentificacao.POSSIVEL_FONTE_NAO_INTEGRADA: "Título no Sistema de origem fora da plataforma",
    MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ: (
        "confirmar que o pagador é o Franqueado; o nome do Extrato ainda não é Pagador conhecido"
    ),
}


class TipoDeEvidencia(StrEnum):
    NOSSO_NUMERO = "nosso número"
    CNPJ_CPF = "CNPJ/CPF"
    NOME_POR_PREFIXO = "nome por prefixo"
    SO_VALOR = "só valor"
    PARECER_DE_LLM = "parecer de LLM"


class Resposta(StrEnum):
    SIM = "sim"
    NAO = "não"
    INDISPONIVEL = "IA indisponível"


@dataclass(frozen=True)
class Parecer:
    resposta: Resposta
    explicacao: str
    modelo: str
    versao_do_prompt: str


@dataclass(frozen=True)
class ParecerSobreFranqueado:
    franqueado: str
    parecer: Parecer

    def descrever(self) -> str:
        parecer = self.parecer
        return (
            f"Franqueado de raiz {self.franqueado}: {parecer.resposta.value}, {parecer.explicacao} "
            f"(modelo {parecer.modelo}, prompt {parecer.versao_do_prompt})"
        )


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
    evidencia: tuple[TipoDeEvidencia, ...] = ()
    pareceres: tuple[ParecerSobreFranqueado, ...] = ()


@dataclass(frozen=True)
class Item:
    identificador: str
    destino: Destino
    lancamento: Lancamento
    titulos: tuple[Titulo, ...]
    explicacao: str
    motivo: MotivoDeNaoIdentificacao | None
    evidencia: tuple[TipoDeEvidencia, ...]
    pareceres: tuple[ParecerSobreFranqueado, ...]

    @property
    def o_que_falta(self) -> str:
        return self.motivo.o_que_falta if self.motivo else ""

    @property
    def ia_indisponivel(self) -> bool:
        return any(p.parecer.resposta is Resposta.INDISPONIVEL for p in self.pareceres)


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
    itens_com_parecer: int
    itens_ia_indisponivel: int


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
