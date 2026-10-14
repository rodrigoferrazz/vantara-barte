import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, fields, replace
from datetime import date, timedelta
from enum import StrEnum
from fnmatch import fnmatch

from conciliacao.adaptadores import EXTRATOS
from conciliacao.calendario import eh_dia_util, vencimento_efetivo
from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.dominio import (
    Canal,
    Destino,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    TipoDeIdentificador,
    Titulo,
)
from conciliacao.encargo import enquadrar, multa_e_juros
from conciliacao.gerador import (
    DEPOSITOS,
    LIQUIDACAO,
    Caso,
    OpcoesDeValor,
    Proporcoes,
    abreviar,
    cnpj_com_digitos,
    como_o_banco_escreve,
    extrato_itau,
    truncar_como_o_banco,
)
from conciliacao.normalizacao import nome_normalizado
from conciliacao.porta import (
    CobrancaIdentificada,
    PagamentoDeCobranca,
    arquivo_de_pix_recebidos,
    arquivo_de_retorno_cnab,
)

_DIAS_ANTES_DO_VENCIMENTO = 7
_DIAS_DE_ATRASO = 20
_PARTE_PAGA_NO_PARCIAL = (0.3, 0.9)
_CHANCE_DE_CNPJ_DE_FILIAL = 0.2
_BAGUNCA_DO_CREDITO_SOLTO = {
    Caso.CNPJ_NO_HISTORICO: Proporcoes.cnpj_no_historico,
    Caso.NOME_TRUNCADO: Proporcoes.nome_truncado,
    Caso.NOME_ABREVIADO: Proporcoes.nome_abreviado,
    Caso.NOME_INVERTIDO: Proporcoes.nome_invertido,
    Caso.DEPOSITO_SEM_NOME: Proporcoes.deposito_sem_nome,
}
_BAGUNCA_SEM_NOME = (Caso.CNPJ_NO_HISTORICO, Caso.DEPOSITO_SEM_NOME)


class ConfiguracaoDoSimuladorInvalida(ValueError):
    pass


class Desfecho(StrEnum):
    EM_DIA = "em dia"
    ATRASO_COM_MULTA = "atraso com multa"
    ATRASO_SEM_ENCARGO = "atraso sem Encargo"
    PARCIAL = "parcial em boleto autorizado"
    CREDITO_SOLTO = "Crédito solto"


@dataclass(frozen=True)
class ProporcoesDoSimulador:
    em_dia: float = 0.55
    atraso_com_multa: float = 0.10
    atraso_sem_encargo: float = 0.10
    parcial: float = 0.05
    credito_solto: float = 0.20

    def de(self, desfecho: Desfecho) -> float:
        return float(getattr(self, desfecho.name.lower()))


@dataclass(frozen=True)
class ConfiguracaoDoSimulador:
    semente: int
    inicio: date
    proporcoes: ProporcoesDoSimulador = ProporcoesDoSimulador()


@dataclass(frozen=True)
class CreditoEsperado:
    conta: str
    data: date
    historico: str
    documento: str
    valor_centavos: int
    desfecho: Desfecho
    canal: Canal
    identificador: TipoDeIdentificador | None
    destino: Destino
    titulos: frozenset[tuple[str, str]]
    motivo: MotivoDeNaoIdentificacao | None
    pagador: str
    bagunca: Caso | None = None
    nome_no_extrato: str | None = None


@dataclass(frozen=True)
class PagamentoSimulado:
    esperado: CreditoEsperado
    de_cobranca: PagamentoDeCobranca | None


@dataclass(frozen=True)
class PlanoDePagamentos:
    pagamentos: tuple[PagamentoSimulado, ...]

    @property
    def gabarito(self) -> tuple[CreditoEsperado, ...]:
        return tuple(pagamento.esperado for pagamento in self.pagamentos)

    @property
    def pagamentos_de_cobranca(self) -> tuple[PagamentoDeCobranca, ...]:
        return tuple(p.de_cobranca for p in self.pagamentos if p.de_cobranca is not None)

    @property
    def ultimo_dia(self) -> date:
        return max(esperado.data for esperado in self.gabarito)

    def extrato(self, conta: str, mantidos: Iterable[Lancamento] = ()) -> str:
        linhas = [
            *((e.data, e.historico, e.documento, e.valor_centavos, Natureza.CREDITO) for e in self.gabarito if e.conta == conta),
            *((m.data, m.historico, m.documento, m.valor_centavos, m.natureza) for m in mantidos if m.conta == conta),
        ]
        return extrato_itau(sorted(linhas, key=lambda linha: (linha[0], linha[1], linha[3])))


def plano_por_proporcoes(
    cobrancas: Iterable[CobrancaIdentificada],
    titulos: Iterable[Titulo],
    configuracao: Configuracao,
    simulador: ConfiguracaoDoSimulador,
) -> PlanoDePagamentos:
    _validar(simulador.proporcoes)
    return _PorProporcoes(
        configuracao=configuracao, titulos=list(titulos), inicio=simulador.inicio, simulador=simulador
    ).planejar(cobrancas)


def _validar(proporcoes: ProporcoesDoSimulador) -> None:
    for campo in fields(proporcoes):
        valor = getattr(proporcoes, campo.name)
        if not 0 <= valor <= 1:
            raise ConfiguracaoDoSimuladorInvalida(f"proporção {campo.name} = {valor} fora do intervalo de 0 a 1")
    soma = sum(proporcoes.de(desfecho) for desfecho in Desfecho)
    if abs(soma - 1) > 1e-9:
        raise ConfiguracaoDoSimuladorInvalida(f"as proporções dos desfechos somam {soma:.2f}, e não 1")


type _Chave = tuple[str, date, int]


@dataclass
class _Simulador:
    configuracao: Configuracao
    titulos: list[Titulo]
    inicio: date

    def __post_init__(self) -> None:
        self.por_chave = {(t.sistema_de_origem, t.documento): t for t in self.titulos}
        valores: dict[str, list[int]] = defaultdict(list)
        nomes: dict[str, set[str]] = defaultdict(set)
        for titulo in self.titulos:
            valores[titulo.franqueado].append(titulo.valor_centavos)
            nomes[titulo.franqueado].add(titulo.nome_do_franqueado)
        self.valores = dict(valores)
        self.nomes = {raiz: sorted(do_franqueado) for raiz, do_franqueado in nomes.items()}
        self.nomes_normalizados = [(nome_normalizado(n), raiz) for raiz, todos in self.nomes.items() for n in todos]
        self.opcoes = OpcoesDeValor(self.valores, self.configuracao.encargo)
        bancos_com_extrato = {extrato.banco for extrato in EXTRATOS}
        self.contas_do_extrato = list(
            dict.fromkeys(c.conta for c in self.configuracao.contas if c.banco in bancos_com_extrato)
        )

    def _aceita(self, tipo: TipoDeIdentificador, cobranca: CobrancaIdentificada, data: date, valor: int) -> bool:
        com_encargo = self._valor_com_encargo(cobranca, data)
        return valor == com_encargo if tipo is TipoDeIdentificador.TXID else valor <= com_encargo

    def _valor_com_encargo(self, cobranca: CobrancaIdentificada, data: date) -> int:
        return cobranca.valor_centavos + sum(self._multa_e_juros(cobranca, data))

    def _multa_e_juros(self, cobranca: CobrancaIdentificada, data: date) -> tuple[int, int]:
        return multa_e_juros(cobranca.valor_centavos, cobranca.vencimento, data, self.configuracao.encargo)

    def _pagamento_identificado(
        self,
        titulo: Titulo,
        cobranca: CobrancaIdentificada,
        tipo: TipoDeIdentificador,
        conta: ContaDeExtrato,
        desfecho: Desfecho,
        data: date,
        valor: int,
    ) -> PagamentoSimulado:
        multa, juros = self._multa_e_juros(cobranca, data)
        if valor != cobranca.valor_centavos + multa + juros:
            multa, juros = max(valor - cobranca.valor_centavos, 0), 0
        nome = self._nome_principal(titulo.franqueado)
        historico = (f"PIX RECEBIDO {truncar_como_o_banco(nome)}", "") if tipo is TipoDeIdentificador.TXID else (LIQUIDACAO, "")
        fecha = enquadrar(replace(titulo, valor_centavos=cobranca.valor_centavos), valor, data, self.configuracao.encargo).fecha
        esperado = CreditoEsperado(
            conta=conta.conta,
            data=data,
            historico=historico[0],
            documento=historico[1],
            valor_centavos=valor,
            desfecho=desfecho,
            canal=Canal.PIX if tipo is TipoDeIdentificador.TXID else Canal.BOLETO,
            identificador=tipo,
            destino=Destino.LISTA_DE_BAIXA if fecha else Destino.FILA_DE_EXCECOES,
            titulos=frozenset({(titulo.sistema_de_origem, titulo.documento)}),
            motivo=None if fecha else MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
            pagador=titulo.franqueado,
        )
        de_cobranca = PagamentoDeCobranca(
            cobranca=cobranca,
            tipo=tipo,
            banco=conta.banco,
            data=data,
            valor_centavos=valor,
            multa_centavos=multa,
            juros_centavos=juros,
            documento_do_pagador=cobranca.cnpj,
            nome_do_pagador=como_o_banco_escreve(nome),
        )
        return PagamentoSimulado(esperado, de_cobranca)

    def _nome_principal(self, raiz: str) -> str:
        return self.nomes[raiz][0]

    def _conta_do_identificador(self, tipo: TipoDeIdentificador) -> ContaDeExtrato:
        inicio = self.inicio
        if tipo is TipoDeIdentificador.TXID:
            return self._conta_do_arquivo(arquivo_de_pix_recebidos(inicio, inicio))
        migracao = self.configuracao.migracao
        faixa = migracao.boleto if migracao is not None else None
        if faixa is None:
            raise ConfiguracaoDoSimuladorInvalida("cobrança com nosso número sem [migracao.boleto] na configuração")
        conta = self._conta_do_arquivo(arquivo_de_retorno_cnab(faixa.banco, inicio, inicio))
        if (conta.banco, conta.conta) != (faixa.banco, faixa.conta):
            raise ConfiguracaoDoSimuladorInvalida(
                f"o retorno CNAB casa com a conta {conta.conta}, mas a faixa de nosso número é da conta {faixa.conta}"
            )
        return conta

    def _conta_do_arquivo(self, nome: str) -> ContaDeExtrato:
        contas = [conta for conta in self.configuracao.contas if fnmatch(nome, conta.padrao)]
        if len(contas) != 1:
            raise ConfiguracaoDoSimuladorInvalida(f"o arquivo {nome} da porta precisa casar com uma única [[contas]]")
        if contas[0].conta not in self.contas_do_extrato:
            raise ConfiguracaoDoSimuladorInvalida(f"a conta {contas[0].conta} do arquivo {nome} não tem Extrato")
        return contas[0]


@dataclass
class _PorProporcoes(_Simulador):
    simulador: ConfiguracaoDoSimulador
    rng: random.Random = field(init=False)
    pagamentos: list[PagamentoSimulado] = field(default_factory=list)
    chaves: set[_Chave] = field(default_factory=set)
    nomes_de_ia: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.rng = random.Random(self.simulador.semente)

    def planejar(self, cobrancas: Iterable[CobrancaIdentificada]) -> PlanoDePagamentos:
        por_titulo: dict[tuple[str, str], list[CobrancaIdentificada]] = defaultdict(list)
        for cobranca in cobrancas:
            por_titulo[(cobranca.sistema_de_origem, cobranca.documento)].append(cobranca)
        desfechos = list(Desfecho)
        pesos = [self.simulador.proporcoes.de(desfecho) for desfecho in desfechos]
        for chave in sorted(por_titulo):
            if chave not in self.por_chave:
                raise ConfiguracaoDoSimuladorInvalida(f"Título {chave[1]} ({chave[0]}) da cobrança não está entre os Títulos")
            do_titulo = sorted(por_titulo[chave], key=lambda c: (c.txid or "", c.nosso_numero or ""))
            self._pagar(self.por_chave[chave], do_titulo, self.rng.choices(desfechos, pesos)[0])
        return PlanoDePagamentos(tuple(self.pagamentos))

    def _pagar(self, titulo: Titulo, cobrancas: list[CobrancaIdentificada], desfecho: Desfecho) -> None:
        cobranca = cobrancas[0]
        match desfecho:
            case Desfecho.EM_DIA:
                self._identificado(titulo, cobrancas, desfecho, self._dias_em_dia(cobranca), lambda c, data: c.valor_centavos)
            case Desfecho.ATRASO_COM_MULTA:
                self._identificado(titulo, cobrancas, desfecho, self._dias_atrasados(cobranca), self._valor_com_encargo)
            case Desfecho.ATRASO_SEM_ENCARGO:
                self._identificado(
                    titulo, cobrancas, desfecho, self._dias_atrasados(cobranca), lambda c, data: c.valor_centavos
                )
            case Desfecho.PARCIAL:
                parte = self.rng.uniform(*_PARTE_PAGA_NO_PARCIAL)
                self._identificado(
                    titulo, cobrancas, desfecho, self._dias_em_dia(cobranca), lambda c, data: round(c.valor_centavos * parte)
                )
            case Desfecho.CREDITO_SOLTO:
                self._solto(titulo, cobranca, desfecho, self._dias_em_dia(cobranca), cobranca.valor_centavos)

    def _identificado(
        self,
        titulo: Titulo,
        cobrancas: list[CobrancaIdentificada],
        desfecho: Desfecho,
        dias: list[date],
        valor_de: Callable[[CobrancaIdentificada, date], int],
    ) -> None:
        for data in self._em_ordem(dias):
            canais = [
                (tipo, c)
                for c in cobrancas
                for tipo in TipoDeIdentificador
                if c.identificador(tipo) is not None and self._aceita(tipo, c, data, valor_de(c, data))
            ]
            if not canais:
                self._solto(titulo, cobrancas[0], desfecho, dias, valor_de(cobrancas[0], data))
                return
            tipo, cobranca = self.rng.choice(canais)
            valor = valor_de(cobranca, data)
            conta = self._conta_do_identificador(tipo)
            if (conta.conta, data, valor) in self.chaves:
                continue
            self._registrar(self._pagamento_identificado(titulo, cobranca, tipo, conta, desfecho, data, valor))
            return
        raise ConfiguracaoDoSimuladorInvalida(f"sem dia livre para o pagamento do Título {titulo.documento}")

    def _solto(self, titulo: Titulo, cobranca: CobrancaIdentificada, desfecho: Desfecho, dias: list[date], valor: int) -> None:
        if desfecho is Desfecho.CREDITO_SOLTO:
            baguncas, pesos = list(_BAGUNCA_DO_CREDITO_SOLTO), list(_BAGUNCA_DO_CREDITO_SOLTO.values())
        else:
            baguncas, pesos = list(_BAGUNCA_SEM_NOME), [_BAGUNCA_DO_CREDITO_SOLTO[caso] for caso in _BAGUNCA_SEM_NOME]
        bagunca = self.rng.choices(baguncas, pesos)[0]
        for data in self._em_ordem(dias):
            conta = self.rng.choice(self.contas_do_extrato)
            if (conta, data, valor) in self.chaves:
                continue
            esperado = self._com_bagunca(bagunca, titulo, cobranca, desfecho, conta, data, valor) or self._com_bagunca(
                Caso.DEPOSITO_SEM_NOME, titulo, cobranca, desfecho, conta, data, valor
            )
            assert esperado is not None
            self._registrar(PagamentoSimulado(esperado, None))
            return
        raise ConfiguracaoDoSimuladorInvalida(f"sem dia livre para o Crédito solto do Título {titulo.documento}")

    def _com_bagunca(
        self,
        bagunca: Caso,
        titulo: Titulo,
        cobranca: CobrancaIdentificada,
        desfecho: Desfecho,
        conta: str,
        data: date,
        valor: int,
    ) -> CreditoEsperado | None:
        raiz = titulo.franqueado
        fecha = enquadrar(replace(titulo, valor_centavos=cobranca.valor_centavos), valor, data, self.configuracao.encargo).fecha
        opcoes = self.opcoes.opcoes(raiz, valor)
        so_o_titulo = fecha and opcoes == 1
        esperado = CreditoEsperado(
            conta=conta,
            data=data,
            historico="",
            documento="",
            valor_centavos=valor,
            desfecho=desfecho,
            canal=self.rng.choice((Canal.PIX, Canal.TED)),
            identificador=None,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=frozenset({(titulo.sistema_de_origem, titulo.documento)}),
            motivo=MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
            pagador=raiz,
            bagunca=bagunca,
        )
        match bagunca:
            case Caso.CNPJ_NO_HISTORICO if so_o_titulo or (not fecha and opcoes == 0):
                cnpj = cobranca.cnpj if self.rng.random() >= _CHANCE_DE_CNPJ_DE_FILIAL else cnpj_com_digitos(raiz + "0002")
                historico = f"PIX RECEBIDO {cnpj}" if esperado.canal is Canal.PIX else f"TED RECEBIDA CNPJ {cnpj}"
                if so_o_titulo:
                    return replace(esperado, historico=historico, destino=Destino.LISTA_DE_BAIXA, motivo=None)
                return replace(esperado, historico=historico, motivo=self._motivo_sem_opcao(raiz))
            case Caso.NOME_TRUNCADO if so_o_titulo:
                nome = truncar_como_o_banco(self._nome_principal(raiz))
                if self._franqueados_do_prefixo(nome) != [raiz]:
                    return None
                return self._com_nome(esperado, nome)
            case Caso.NOME_ABREVIADO | Caso.NOME_INVERTIDO if so_o_titulo:
                nome = self._nome_para_a_ia(bagunca, self._nome_principal(raiz))
                if nome in self.nomes_de_ia or self._franqueados_do_prefixo(nome):
                    return None
                self.nomes_de_ia.add(nome)
                return self._com_nome(esperado, nome)
            case Caso.DEPOSITO_SEM_NOME:
                return replace(
                    esperado,
                    historico=self.rng.choice(DEPOSITOS),
                    canal=Canal.DEPOSITO,
                    motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
                )
        return None

    @staticmethod
    def _com_nome(esperado: CreditoEsperado, nome: str) -> CreditoEsperado:
        inicio = "PIX RECEBIDO" if esperado.canal is Canal.PIX else "TED RECEBIDA"
        return replace(esperado, historico=f"{inicio} {nome}", nome_no_extrato=nome)

    def _nome_para_a_ia(self, bagunca: Caso, nome: str) -> str:
        if bagunca is Caso.NOME_ABREVIADO:
            return abreviar(nome, self.rng)
        primeira, segunda, *resto = [*como_o_banco_escreve(nome).split(), ""]
        return truncar_como_o_banco(" ".join([segunda, primeira, *resto]))

    def _motivo_sem_opcao(self, raiz: str) -> MotivoDeNaoIdentificacao:
        if len(self.valores[raiz]) == 1:
            return MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
        return MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO

    def _franqueados_do_prefixo(self, nome: str) -> list[str]:
        normalizado = nome_normalizado(nome)
        return sorted({raiz for do_franqueado, raiz in self.nomes_normalizados if do_franqueado.startswith(normalizado)})

    def _registrar(self, pagamento: PagamentoSimulado) -> None:
        esperado = pagamento.esperado
        self.chaves.add((esperado.conta, esperado.data, esperado.valor_centavos))
        self.pagamentos.append(pagamento)

    def _em_ordem(self, dias: list[date]) -> list[date]:
        return self.rng.sample(dias, len(dias))

    def _dias_em_dia(self, cobranca: CobrancaIdentificada) -> list[date]:
        efetivo = vencimento_efetivo(cobranca.vencimento)
        dias = _dias_uteis(max(self.simulador.inicio, cobranca.vencimento - timedelta(days=_DIAS_ANTES_DO_VENCIMENTO)), efetivo)
        if not dias:
            raise ConfiguracaoDoSimuladorInvalida(
                f"a cobrança do Título {cobranca.documento} vence antes do início da simulação"
            )
        return dias

    def _dias_atrasados(self, cobranca: CobrancaIdentificada) -> list[date]:
        efetivo = vencimento_efetivo(cobranca.vencimento)
        inicio = max(self.simulador.inicio, efetivo + timedelta(days=1))
        return _dias_uteis(inicio, efetivo + timedelta(days=_DIAS_DE_ATRASO))


@dataclass
class Contrafactual(_Simulador):
    def pagamentos(
        self, lancamento: Lancamento, cobrancas: Sequence[CobrancaIdentificada]
    ) -> tuple[PagamentoSimulado, ...] | None:
        partes = self._partes(lancamento, cobrancas)
        if partes is None:
            return None
        pagamentos = []
        for cobranca, valor in partes:
            tipo = next(
                (
                    tipo
                    for tipo in TipoDeIdentificador
                    if cobranca.identificador(tipo) is not None and self._aceita(tipo, cobranca, lancamento.data, valor)
                ),
                None,
            )
            if tipo is None:
                return None
            pagamentos.append(
                self._pagamento_identificado(
                    self.por_chave[(cobranca.sistema_de_origem, cobranca.documento)],
                    cobranca,
                    tipo,
                    self._conta_do_identificador(tipo),
                    _desfecho(cobranca, lancamento.data, valor),
                    lancamento.data,
                    valor,
                )
            )
        return tuple(pagamentos)

    def _partes(
        self, lancamento: Lancamento, cobrancas: Sequence[CobrancaIdentificada]
    ) -> list[tuple[CobrancaIdentificada, int]] | None:
        if len(cobrancas) == 1:
            return [(cobrancas[0], lancamento.valor_centavos)]
        for valores in (
            [cobranca.valor_centavos for cobranca in cobrancas],
            [self._valor_com_encargo(cobranca, lancamento.data) for cobranca in cobrancas],
        ):
            if sum(valores) == lancamento.valor_centavos:
                return list(zip(cobrancas, valores))
        return None


def _desfecho(cobranca: CobrancaIdentificada, data: date, valor: int) -> Desfecho:
    if valor < cobranca.valor_centavos:
        return Desfecho.PARCIAL
    if data <= vencimento_efetivo(cobranca.vencimento):
        return Desfecho.EM_DIA
    if valor == cobranca.valor_centavos:
        return Desfecho.ATRASO_SEM_ENCARGO
    return Desfecho.ATRASO_COM_MULTA


def _dias_uteis(inicio: date, fim: date) -> list[date]:
    return [inicio + timedelta(days=n) for n in range((fim - inicio).days + 1) if eh_dia_util(inicio + timedelta(days=n))]
