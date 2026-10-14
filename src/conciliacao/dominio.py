from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from typing import ClassVar

from conciliacao.normalizacao import formatar_percentual, formatar_reais, raiz_do_cnpj


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


class Canal(StrEnum):
    PIX = "Pix"
    TED = "TED"
    BOLETO = "boleto"
    DEPOSITO = "depósito"
    NAO_IDENTIFICADO = "canal não identificado"


class TipoDeEvidencia(StrEnum):
    NOSSO_NUMERO = "nosso número"
    CNPJ_CPF = "CNPJ/CPF"
    NOME_POR_PREFIXO = "nome por prefixo"
    SO_VALOR = "só valor"
    PARECER_DE_LLM = "parecer de LLM"
    PAGADOR_CONHECIDO = "Pagador conhecido"
    IDENTIFICADOR_DE_COBRANCA = "Identificador de cobrança"


class RegraDaProposta(StrEnum):
    NOSSO_NUMERO_E_VALOR = "nosso número + valor exato ou dentro do Encargo"
    DOCUMENTO_E_VALOR_UNICO = "CNPJ/CPF + Valor único"
    DOCUMENTO_E_SOMA_EXATA = "CNPJ/CPF + soma exata com uma única combinação"
    PAGADOR_CONHECIDO_E_VALOR_UNICO = "nome de Pagador conhecido + Valor único"
    PAGADOR_CONHECIDO_E_SOMA_EXATA = "nome de Pagador conhecido + soma exata com uma única combinação"
    IDENTIFICADOR_E_VALOR = "Identificador de cobrança + valor exato ou dentro do Encargo"


class TipoDeDecisao(StrEnum):
    CONFIRMAR = "confirmar"
    REJEITAR = "rejeitar"
    ANTECIPACAO = "antecipação"
    DEVOLUCAO = "devolução"
    ERRO = "erro"
    CONCILIADO_FORA = "conciliado fora"
    POSSIVEL_FONTE_NAO_INTEGRADA = "possível fonte não integrada"
    MESMA_DIVIDA = "mesma dívida"
    DIVIDAS_DISTINTAS = "dívidas distintas"
    REVERTER = "reverter"

    @property
    def encerra_o_credito(self) -> bool:
        return self in (
            TipoDeDecisao.CONFIRMAR,
            TipoDeDecisao.DEVOLUCAO,
            TipoDeDecisao.ERRO,
            TipoDeDecisao.CONCILIADO_FORA,
        )

    @property
    def classifica_credito_sem_titulo(self) -> bool:
        return self in (TipoDeDecisao.ANTECIPACAO, TipoDeDecisao.DEVOLUCAO, TipoDeDecisao.ERRO)


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
    nome_do_franqueado: str
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

    @property
    def chave(self) -> frozenset[tuple[str, str]]:
        return frozenset((titulo.sistema_de_origem, titulo.documento) for titulo in self.titulos)


@dataclass(frozen=True)
class PagadorConhecido:
    nome: str
    franqueados: tuple[str, ...]

    @property
    def franqueado(self) -> str | None:
        return self.franqueados[0] if len(self.franqueados) == 1 else None


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


class TipoDeIdentificador(StrEnum):
    TXID = "txid"


class OrigemDoIdentificador(StrEnum):
    PLATAFORMA = "plataforma"


type ChaveDoIdentificador = tuple[TipoDeIdentificador, str]


@dataclass(frozen=True)
class VinculoDeCobranca:
    tipo: TipoDeIdentificador
    identificador: str
    origem: OrigemDoIdentificador
    sistema_de_origem: str
    documento: str
    cnpj: str
    valor_centavos: int
    vencimento: date

    @property
    def chave(self) -> ChaveDoIdentificador:
        return (self.tipo, self.identificador)

    def descrever(self) -> str:
        return f"{self.tipo.value} {self.identificador} (Identificador de cobrança de origem {self.origem.value})"


@dataclass(frozen=True)
class ComponentesDoValor:
    principal_centavos: int
    multa_centavos: int
    juros_centavos: int

    def descrever(self) -> str:
        return (
            f"principal {formatar_reais(self.principal_centavos)}, multa {formatar_reais(self.multa_centavos)} "
            f"e juros {formatar_reais(self.juros_centavos)}"
        )


@dataclass(frozen=True)
class RetornoDeCobranca:
    tipo: TipoDeIdentificador
    chave_natural: str
    identificador: str
    banco: str
    conta: str
    data: date
    valor_centavos: int
    componentes: ComponentesDoValor | None = None

    @property
    def chave_do_identificador(self) -> ChaveDoIdentificador:
        return (self.tipo, self.identificador)


@dataclass(frozen=True)
class Classificacao:
    lancamento: Lancamento
    destino: Destino
    titulos: tuple[Titulo, ...]
    explicacao: str
    motivo: MotivoDeNaoIdentificacao | None = None
    evidencia: tuple[TipoDeEvidencia, ...] = ()
    pareceres: tuple[ParecerSobreFranqueado, ...] = ()
    citados: tuple[Titulo, ...] = ()
    franqueado: str | None = None
    canal: Canal | None = None
    regra: RegraDaProposta | None = None

    @property
    def titulos_candidatos(self) -> tuple[Titulo, ...]:
        return tuple(dict.fromkeys((*self.titulos, *self.citados)))


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
    franqueado: str | None = None
    canal: Canal | None = None
    regra: RegraDaProposta | None = None

    @property
    def o_que_falta(self) -> str:
        return self.motivo.o_que_falta if self.motivo else ""

    @property
    def ia_indisponivel(self) -> bool:
        return any(p.parecer.resposta is Resposta.INDISPONIVEL for p in self.pareceres)


@dataclass(frozen=True)
class ParRejeitado:
    credito: ChaveNatural
    sistema_de_origem: str
    documento: str
    motivo: str

    def rejeita(self, titulo: Titulo) -> bool:
        return (self.sistema_de_origem, self.documento) == (titulo.sistema_de_origem, titulo.documento)


@dataclass(frozen=True)
class DecisaoRegistrada:
    item: str
    tipo: TipoDeDecisao
    motivo: str | None
    autor: str
    momento: datetime
    origem: str
    execucao: int
    titulos: tuple[Titulo, ...]
    evidencia: tuple[TipoDeEvidencia, ...]
    explicacao: str
    regra: RegraDaProposta | None
    pareceres: tuple[ParecerSobreFranqueado, ...] = ()
    franqueado: str | None = None
    referencia: str | None = None


@dataclass(frozen=True)
class TituloACancelar:
    item: str
    titulo: Titulo
    oficial: Titulo


@dataclass(frozen=True)
class BaixaManual:
    item: str
    titulo: Titulo
    principal_centavos: int
    encargo_centavos: int
    credito: Lancamento


@dataclass(frozen=True)
class LinhaDeDecisao:
    aba: str
    item: str
    decisao: str
    motivo: str = ""
    titulos: str = ""
    franqueado: str = ""
    referencia: str = ""


@dataclass(frozen=True)
class DecisaoDaTela:
    identificador: int
    execucao: int
    linha: LinhaDeDecisao
    autor: str
    momento: datetime


@dataclass(frozen=True)
class DecisoesLidas:
    confirmadas: int = 0
    rejeitadas: int = 0
    nao_aplicadas: tuple[str, ...] = ()
    classificadas: int = 0
    conciliados_fora: int = 0
    fontes_nao_integradas: int = 0
    duplicidades: int = 0
    revertidas: int = 0
    conflitos: tuple[str, ...] = ()


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
class ParteAutomatica:
    resolvidos: TotalDoDestino
    creditos: TotalDoDestino

    @classmethod
    def dos_totais(cls, totais: Mapping[Destino, TotalDoDestino]) -> "ParteAutomatica":
        lista, fila = totais[Destino.LISTA_DE_BAIXA], totais[Destino.FILA_DE_EXCECOES]
        return cls(
            resolvidos=lista,
            creditos=TotalDoDestino(lista.quantidade + fila.quantidade, lista.valor_centavos + fila.valor_centavos),
        )

    @property
    def percentual_da_quantidade(self) -> Fraction | None:
        if not self.creditos.quantidade:
            return None
        return Fraction(100 * self.resolvidos.quantidade, self.creditos.quantidade)

    @property
    def percentual_do_valor(self) -> Fraction | None:
        if not self.creditos.valor_centavos:
            return None
        return Fraction(100 * self.resolvidos.valor_centavos, self.creditos.valor_centavos)


@dataclass(frozen=True)
class UltimaDataDaConta:
    banco: str
    conta: str
    ultima_data: date | None


@dataclass(frozen=True)
class DataDeReferencia:
    contas: tuple[UltimaDataDaConta, ...]

    @property
    def data(self) -> date | None:
        datas = [conta.ultima_data for conta in self.contas]
        if not datas or None in datas:
            return None
        return min(d for d in datas if d is not None)

    @property
    def contas_que_seguram(self) -> tuple[UltimaDataDaConta, ...]:
        sem_extrato = tuple(conta for conta in self.contas if conta.ultima_data is None)
        if sem_extrato:
            return sem_extrato
        return tuple(conta for conta in self.contas if conta.ultima_data == self.data)


class SituacaoNoErp(StrEnum):
    AGUARDANDO_BAIXA_NO_ERP = "Aguardando baixa no ERP"
    BAIXADO_POR_FORA = "Baixado por fora"
    DIVERGENCIA_DE_BAIXA = "Divergência de baixa"
    ESTORNO_NECESSARIO_NO_ERP = "Estorno necessário no ERP"


@dataclass(frozen=True)
class TituloNoAcompanhamento:
    situacao: SituacaoNoErp
    titulo: Titulo
    item: str | None
    explicacao: str
    saldo_centavos: int | None = None


@dataclass(frozen=True)
class TituloConfirmado:
    titulo: Titulo
    principal_centavos: int
    valores_posteriores: frozenset[int]

    def absorvido_pelo_erp(self, valor_atual_centavos: int) -> bool:
        return any(valor != self.titulo.valor_centavos for valor in self.valores_posteriores | {valor_atual_centavos})


@dataclass(frozen=True)
class ConfirmacaoEmVigor:
    decisao: int
    item: str
    credito: ChaveNatural
    titulos: tuple[TituloConfirmado, ...]


@dataclass(frozen=True)
class ConfirmacaoRevertida:
    item: str
    motivo: str
    sem_reaparecer: tuple[Titulo, ...]


@dataclass(frozen=True)
class TituloNaCobranca:
    titulo: Titulo
    saldo_centavos: int
    creditos_candidatos: tuple[Lancamento, ...]

    @property
    def em_analise(self) -> bool:
        return bool(self.creditos_candidatos)


@dataclass(frozen=True)
class Resumo:
    execucao: int
    arquivos_lidos: tuple[str, ...]
    arquivos_recusados: tuple[ArquivoRecusado, ...]
    lancamentos_novos: int
    totais: dict[Destino, TotalDoDestino]
    itens_com_parecer: int
    itens_ia_indisponivel: int
    data_de_referencia: DataDeReferencia
    decisoes: DecisoesLidas
    limite_de_queda: Decimal | None
    execucao_anterior: int | None = None
    parte_automatica_anterior: ParteAutomatica | None = None

    @property
    def parte_automatica(self) -> ParteAutomatica:
        return ParteAutomatica.dos_totais(self.totais)

    @property
    def alerta_de_queda(self) -> str | None:
        anterior, atual = self.parte_automatica_anterior, self.parte_automatica
        if anterior is None or self.limite_de_queda is None:
            return None
        limite = Fraction(self.limite_de_queda)
        quedas = [
            f"{medida} de {formatar_percentual(antes)} para {formatar_percentual(agora)} "
            f"(queda de {formatar_percentual(antes - agora, simbolo=False)})"
            for medida, antes, agora in (
                ("em quantidade", anterior.percentual_da_quantidade, atual.percentual_da_quantidade),
                ("em valor", anterior.percentual_do_valor, atual.percentual_do_valor),
            )
            if antes is not None and agora is not None and antes - agora > limite
        ]
        if not quedas:
            return None
        return (
            f"ATENÇÃO: a parte resolvida sozinha caiu além do limite de {formatar_limite(self.limite_de_queda)} "
            f"pontos percentuais em relação à execução {self.execucao_anterior}: {'; '.join(quedas)}. "
            "Verifique se alguma exportação veio quebrada."
        )


def formatar_limite(limite: Decimal) -> str:
    return f"{limite:f}".replace(".", ",")


@dataclass(frozen=True)
class GrupoDaCausaRaiz:
    nome: str
    quantidade: int
    valor_centavos: int


@dataclass(frozen=True)
class CausaRaiz:
    SEM_FRANQUEADO: ClassVar[str] = "sem Franqueado"

    quantidade: int
    valor_centavos: int
    por_motivo: tuple[GrupoDaCausaRaiz, ...]
    por_franqueado: tuple[GrupoDaCausaRaiz, ...]
    por_banco: tuple[GrupoDaCausaRaiz, ...]
    por_canal: tuple[GrupoDaCausaRaiz, ...]

    @classmethod
    def da_fila(cls, fila: Iterable[Item], nomes_dos_franqueados: Mapping[str, Iterable[str]]) -> "CausaRaiz":
        creditos = list(fila)

        def franqueado(item: Item) -> str:
            if item.franqueado is None:
                return cls.SEM_FRANQUEADO
            nomes = sorted(nomes_dos_franqueados.get(item.franqueado, ()))
            return f"{' / '.join(nomes)} (raiz {item.franqueado})" if nomes else f"raiz {item.franqueado}"

        por_franqueado = _agrupar(creditos, franqueado)
        return cls(
            quantidade=len(creditos),
            valor_centavos=sum(item.lancamento.valor_centavos for item in creditos),
            por_motivo=_agrupar(creditos, lambda item: str(item.motivo), [m.value for m in MotivoDeNaoIdentificacao]),
            por_franqueado=_por_concentracao([g for g in por_franqueado if g.nome != cls.SEM_FRANQUEADO])
            + tuple(g for g in por_franqueado if g.nome == cls.SEM_FRANQUEADO),
            por_banco=_por_concentracao(_agrupar(creditos, lambda item: item.lancamento.banco)),
            por_canal=_agrupar(creditos, lambda item: str(item.canal), [c.value for c in Canal]),
        )

    def fracao_da_quantidade(self, grupo: GrupoDaCausaRaiz) -> Fraction | None:
        return Fraction(grupo.quantidade, self.quantidade) if self.quantidade else None

    def fracao_do_valor(self, grupo: GrupoDaCausaRaiz) -> Fraction | None:
        return Fraction(grupo.valor_centavos, self.valor_centavos) if self.valor_centavos else None


@dataclass(frozen=True)
class RejeicaoDasPropostas:
    nome: str
    confirmadas: int
    rejeitadas: int
    revertidas: int

    @property
    def taxa_de_rejeicao(self) -> Fraction | None:
        decididas = self.confirmadas + self.rejeitadas
        return Fraction(self.rejeitadas, decididas) if decididas else None


@dataclass(frozen=True)
class AcertoDaIa:
    modelo: str
    versao_do_prompt: str
    avaliados: int
    acertos: int
    aguardando_decisao: int

    @property
    def taxa_de_acerto(self) -> Fraction | None:
        return Fraction(self.acertos, self.avaliados) if self.avaliados else None


@dataclass(frozen=True)
class DecisaoSobreProposta:
    tipo: TipoDeDecisao
    regra: RegraDaProposta
    evidencia: tuple[TipoDeEvidencia, ...]
    revertida: bool


@dataclass(frozen=True)
class PrimeiroParecerDaIa:
    pareceres: tuple[ParecerSobreFranqueado, ...]
    franqueados_decididos: frozenset[str] | None


@dataclass(frozen=True)
class Metricas:
    por_evidencia: tuple[RejeicaoDasPropostas, ...] = ()
    por_regra: tuple[RejeicaoDasPropostas, ...] = ()
    acerto_da_ia: tuple[AcertoDaIa, ...] = ()

    @classmethod
    def calcular(
        cls, propostas: Iterable[DecisaoSobreProposta], primeiros_pareceres: Iterable[PrimeiroParecerDaIa]
    ) -> "Metricas":
        decididas = list(propostas)
        return cls(
            por_evidencia=_rejeicao(
                decididas, [e.value for e in TipoDeEvidencia], lambda d: [e.value for e in d.evidencia]
            ),
            por_regra=_rejeicao(decididas, [r.value for r in RegraDaProposta], lambda d: [d.regra.value]),
            acerto_da_ia=_acerto_da_ia(primeiros_pareceres),
        )


def _rejeicao(
    decididas: list[DecisaoSobreProposta],
    ordem: list[str],
    grupos_da_decisao: Callable[[DecisaoSobreProposta], list[str]],
) -> tuple[RejeicaoDasPropostas, ...]:
    por_grupo: dict[str, list[DecisaoSobreProposta]] = {}
    for decisao in decididas:
        for grupo in grupos_da_decisao(decisao):
            por_grupo.setdefault(grupo, []).append(decisao)
    return tuple(
        RejeicaoDasPropostas(
            nome=grupo,
            confirmadas=sum(1 for d in do_grupo if d.tipo is TipoDeDecisao.CONFIRMAR),
            rejeitadas=sum(1 for d in do_grupo if d.tipo is TipoDeDecisao.REJEITAR),
            revertidas=sum(1 for d in do_grupo if d.revertida),
        )
        for grupo in ordem
        if (do_grupo := por_grupo.get(grupo))
    )


def _acerto_da_ia(primeiros_pareceres: Iterable[PrimeiroParecerDaIa]) -> tuple[AcertoDaIa, ...]:
    por_versao: dict[tuple[str, str], list[PrimeiroParecerDaIa]] = {}
    for primeiro in primeiros_pareceres:
        parecer = primeiro.pareceres[0].parecer
        por_versao.setdefault((parecer.modelo, parecer.versao_do_prompt), []).append(primeiro)
    resultado = []
    for (modelo, versao), da_versao in sorted(por_versao.items()):
        avaliaveis = [s for s in da_versao if s.franqueados_decididos is not None and len(s.franqueados_decididos) == 1]
        resultado.append(
            AcertoDaIa(
                modelo=modelo,
                versao_do_prompt=versao,
                avaliados=len(avaliaveis),
                acertos=sum(1 for s in avaliaveis if _acertou(s)),
                aguardando_decisao=sum(1 for s in da_versao if s.franqueados_decididos is None),
            )
        )
    return tuple(resultado)


def _acertou(primeiro: PrimeiroParecerDaIa) -> bool:
    decididos = primeiro.franqueados_decididos or frozenset()
    return all((p.parecer.resposta is Resposta.SIM) == (p.franqueado in decididos) for p in primeiro.pareceres)


def _agrupar(
    itens: list[Item], grupo_do_item: Callable[[Item], str], grupos_fixos: Iterable[str] = ()
) -> tuple[GrupoDaCausaRaiz, ...]:
    grupos: dict[str, list[Item]] = {nome: [] for nome in grupos_fixos}
    for item in itens:
        grupos.setdefault(grupo_do_item(item), []).append(item)
    return tuple(
        GrupoDaCausaRaiz(nome, len(do_grupo), sum(item.lancamento.valor_centavos for item in do_grupo))
        for nome, do_grupo in grupos.items()
    )


def _por_concentracao(grupos: Iterable[GrupoDaCausaRaiz]) -> tuple[GrupoDaCausaRaiz, ...]:
    return tuple(sorted(grupos, key=lambda grupo: (-grupo.quantidade, -grupo.valor_centavos, grupo.nome)))


@dataclass(frozen=True)
class Resultado:
    resumo: Resumo
    itens: tuple[Item, ...]
    itens_de_titulo: tuple[ItemDeTitulo, ...]
    cobranca: tuple[TituloNaCobranca, ...]
    causa_raiz: CausaRaiz
    baixa_manual: tuple[BaixaManual, ...]
    cancelar_na_origem: tuple[TituloACancelar, ...] = ()
    conciliados_fora: tuple[Item, ...] = ()
    acompanhamento_do_erp: tuple[TituloNoAcompanhamento, ...] = ()
    metricas: Metricas = Metricas()

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
    def lista_de_cobranca(self) -> tuple[TituloNaCobranca, ...]:
        return tuple(titulo for titulo in self.cobranca if not titulo.em_analise)

    @property
    def em_analise(self) -> tuple[TituloNaCobranca, ...]:
        return tuple(titulo for titulo in self.cobranca if titulo.em_analise)

    def item_do_lancamento(self, lancamento: Lancamento) -> Item:
        return next(item for item in self.itens if item.lancamento.chave_natural == lancamento.chave_natural)

    @property
    def arquivos_recusados(self) -> tuple[ArquivoRecusado, ...]:
        return self.resumo.arquivos_recusados
