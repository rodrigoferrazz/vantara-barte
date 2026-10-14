import argparse
import random
import shutil
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from fnmatch import fnmatch
from fractions import Fraction
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from conciliacao.acompanhamento import chave_do_titulo
from conciliacao.adaptadores import EXTRATOS
from conciliacao.armazenamento import Armazenamento
from conciliacao.conferencia import ConferenciaDeSomaFalhou
from conciliacao.configuracao import (
    Configuracao,
    ConfiguracaoDeMigracao,
    ConfiguracaoInvalida,
    ContaDeExtrato,
    FaixaDeNossoNumero,
    carregar_configuracao,
)
from conciliacao.dominio import (
    ChaveNatural,
    Destino,
    Item,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    NumerosDoCenario,
    OndaNoRelatorio,
    PorQueFicaSolto,
    RankingDeMigracao,
    RelatorioDeImpacto,
    Resultado,
    TipoDeDecisao,
    TipoDeEvidencia,
    Titulo,
    TotalDoDestino,
    ValorDaPremissa,
)
from conciliacao.emissao import emitir, titulos_em_aberto_fora_de_duplicidade
from conciliacao.execucao import executar_conciliacao
from conciliacao.gerador import LancamentoEsperado
from conciliacao.normalizacao import formatar_adesao
from conciliacao.parecerista import PareceristaDeNome, parecerista_da_configuracao
from conciliacao.porta import CobrancaIdentificada, PortaSimulada
from conciliacao.simulador import Contrafactual, PagamentoSimulado, PlanoDePagamentos

ABA_DO_RESUMO = "Resumo do impacto"
ABA_DAS_ONDAS = "Ondas"
ABA_DA_FILA_POR_MOTIVO = "Fila por motivo"
ABA_DO_RANKING = "Ranking de migração"
ABA_DE_PREMISSAS = "Premissas"

RAZOES_DO_RESUMO = tuple(razao for razao in PorQueFicaSolto if razao is not PorQueFicaSolto.FRANQUEADO_NAO_MIGRADO)
EXPLICACAO_DAS_ONDAS = (
    "Cada onda acumulada migra os Franqueados das ondas do Ranking de migração até ela; só os Créditos "
    "desses Franqueados podem chegar identificados."
)
EXPLICACAO_DO_SEM_FRANQUEADO = "Créditos sem Franqueado não entram em nenhuma Onda de migração."

_FORMATO_DE_VALOR = "#,##0.00"
_FORMATO_DE_PERCENTUAL = "0.0%"
_FAIXA_DE_NOSSO_NUMERO_DA_ANALISE = ("90000000000000000001", "99999999999999999999")
_EVIDENCIAS_DE_IDENTIFICADOR = frozenset({TipoDeEvidencia.NOSSO_NUMERO, TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA})
_DECISOES_SEM_TITULO = (
    TipoDeDecisao.ANTECIPACAO,
    TipoDeDecisao.DEVOLUCAO,
    TipoDeDecisao.ERRO,
    TipoDeDecisao.CONCILIADO_FORA,
    TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA,
)

type _ChaveDoTitulo = tuple[str, str]
type _ChaveDoGabarito = tuple[str, date, str, str, int, Natureza]


class FonteDaVerdade(StrEnum):
    GABARITO = "gabarito do gerador"
    DECISOES_DA_ANALISTA = "decisões confirmadas da Analista"
    PROPOSTA_OU_SUGESTAO = "Proposta da Lista ou sugestão da Fila do antes"


@dataclass(frozen=True)
class CenarioDeAdesao:
    adesao: Decimal
    depois: Resultado
    soltos: dict[PorQueFicaSolto, TotalDoDestino]


@dataclass(frozen=True)
class OndaAcumulada:
    onda: int
    franqueados: frozenset[str]
    cenarios: tuple[CenarioDeAdesao, ...]


@dataclass(frozen=True)
class AnaliseDeImpacto:
    momento: datetime
    pasta: Path
    configuracao: Configuracao
    antes: Resultado
    ranking: RankingDeMigracao
    fontes: dict[FonteDaVerdade, int]
    conta_de_cobranca: ContaDeExtrato
    franqueados: frozenset[str]
    cenarios: tuple[CenarioDeAdesao, ...]
    ondas: tuple[OndaAcumulada, ...]

    @property
    def relatorio(self) -> RelatorioDeImpacto:
        todos = len(self.franqueados)
        return RelatorioDeImpacto(
            momento=self.momento,
            pasta_base=str(self.pasta.resolve()),
            semente=self.configuracao.analise_de_impacto.semente,
            antes=_numeros(self.antes, None, 0),
            todos_migrados=tuple(_numeros(c.depois, c.adesao, todos, c.soltos) for c in self.cenarios),
            ondas=tuple(
                OndaNoRelatorio(
                    onda.onda,
                    tuple(_numeros(c.depois, c.adesao, len(onda.franqueados), c.soltos) for c in onda.cenarios),
                )
                for onda in self.ondas
            ),
            ranking=self.ranking,
            premissas=_premissas(self),
        )


def _numeros(
    resultado: Resultado,
    adesao: Decimal | None,
    franqueados_migrados: int,
    soltos: Mapping[PorQueFicaSolto, TotalDoDestino] | None = None,
) -> NumerosDoCenario:
    chegada = ChegadaDosCreditos.do_resultado(resultado)
    return NumerosDoCenario(
        adesao=adesao,
        franqueados_migrados=franqueados_migrados,
        identificados=chegada.identificados,
        soltos=chegada.soltos,
        lista_de_baixa=resultado.resumo.totais[Destino.LISTA_DE_BAIXA],
        fila_de_excecoes=resultado.resumo.totais[Destino.FILA_DE_EXCECOES],
        fila_por_motivo={
            motivo: _total(item for item in resultado.fila_de_excecoes if item.motivo is motivo)
            for motivo in MotivoDeNaoIdentificacao
        },
        soltos_por_razao=dict(soltos or {}),
    )


@dataclass(frozen=True)
class ChegadaDosCreditos:
    identificados: TotalDoDestino
    soltos: TotalDoDestino

    @classmethod
    def do_resultado(cls, resultado: Resultado) -> "ChegadaDosCreditos":
        creditos = [*resultado.lista_de_baixa, *resultado.fila_de_excecoes]
        identificados = [item for item in creditos if _EVIDENCIAS_DE_IDENTIFICADOR & set(item.evidencia)]
        soltos = [item for item in creditos if not _EVIDENCIAS_DE_IDENTIFICADOR & set(item.evidencia)]
        return cls(_total(identificados), _total(soltos))


def analisar_impacto(
    pasta: Path,
    configuracao: Configuracao,
    parecerista: PareceristaDeNome,
    gabarito: Iterable[LancamentoEsperado] = (),
    estado: Path | None = None,
) -> AnaliseDeImpacto:
    momento = datetime.now()
    with TemporaryDirectory(prefix="analise_de_impacto_") as nome_da_temporaria:
        temporaria = Path(nome_da_temporaria)
        armazenamento = Armazenamento(temporaria / "antes.sqlite")
        try:
            antes = executar_conciliacao(pasta, armazenamento, configuracao, parecerista)
            nomes = {raiz: franqueado.todos_os_nomes for raiz, franqueado in armazenamento.franqueados().items()}
            titulos = titulos_em_aberto_fora_de_duplicidade(armazenamento)
        finally:
            armazenamento.fechar()
        verdades = _verdades(antes, _do_gabarito(gabarito), _decisoes_da_analista(estado, temporaria), configuracao)
        ranking = RankingDeMigracao.da_fila(antes.itens, nomes, configuracao.analise_de_impacto.tamanho_da_onda)
        depois = _Depois(pasta, temporaria, configuracao, parecerista, antes, titulos, verdades)
        faixa = configuracao.analise_de_impacto.faixa_de_adesao
        todos = frozenset(titulo.franqueado for titulo in titulos)
        cenarios = tuple(depois.cenario(adesao, todos) for adesao in faixa)
        ondas = []
        migrados: frozenset[str] = frozenset()
        for numero, da_onda in enumerate(ranking.ondas, start=1):
            migrados |= {franqueado.raiz for franqueado in da_onda}
            ondas.append(OndaAcumulada(numero, migrados, tuple(depois.cenario(adesao, migrados) for adesao in faixa)))
    return AnaliseDeImpacto(
        momento=momento,
        pasta=pasta,
        configuracao=configuracao,
        antes=antes,
        ranking=ranking,
        fontes=dict(Counter(verdade.fonte for verdade in verdades)),
        conta_de_cobranca=depois.conta_de_cobranca,
        franqueados=todos,
        cenarios=cenarios,
        ondas=tuple(ondas),
    )


@dataclass(frozen=True)
class _Verdade:
    item: Item
    fonte: FonteDaVerdade
    titulos: frozenset[_ChaveDoTitulo]
    sorteio: float

    @property
    def ja_identificado(self) -> bool:
        return bool(_EVIDENCIAS_DE_IDENTIFICADOR & set(self.item.evidencia))


def _verdades(
    antes: Resultado,
    gabarito: Mapping[_ChaveDoGabarito, frozenset[_ChaveDoTitulo]],
    decisoes: Mapping[ChaveNatural, frozenset[_ChaveDoTitulo]],
    configuracao: Configuracao,
) -> list[_Verdade]:
    sorteio = random.Random(configuracao.analise_de_impacto.semente)
    creditos = sorted(
        (*antes.lista_de_baixa, *antes.fila_de_excecoes),
        key=lambda item: (item.lancamento.data, item.lancamento.chave_natural),
    )
    verdades = []
    for item in creditos:
        lancamento = item.lancamento
        do_gabarito = gabarito.get(
            (lancamento.conta, lancamento.data, lancamento.historico, lancamento.documento, lancamento.valor_centavos, lancamento.natureza)
        )
        if do_gabarito is not None:
            fonte, titulos = FonteDaVerdade.GABARITO, do_gabarito
        elif (decididos := decisoes.get(lancamento.chave_natural)) is not None:
            fonte, titulos = FonteDaVerdade.DECISOES_DA_ANALISTA, decididos
        else:
            fonte, titulos = FonteDaVerdade.PROPOSTA_OU_SUGESTAO, frozenset(map(chave_do_titulo, item.titulos))
        verdades.append(_Verdade(item, fonte, titulos, sorteio.random()))
    return verdades


def _do_gabarito(gabarito: Iterable[LancamentoEsperado]) -> dict[_ChaveDoGabarito, frozenset[_ChaveDoTitulo]]:
    return {
        (e.conta, e.data, e.historico, e.documento, e.valor_centavos, e.natureza): e.titulos
        for e in gabarito
        if e.natureza is Natureza.CREDITO
    }


def _decisoes_da_analista(estado: Path | None, temporaria: Path) -> dict[ChaveNatural, frozenset[_ChaveDoTitulo]]:
    if estado is None:
        return {}
    copia = temporaria / "estado.sqlite"
    shutil.copyfile(estado, copia)
    armazenamento = Armazenamento(copia)
    try:
        decisoes: dict[ChaveNatural, frozenset[_ChaveDoTitulo]] = {
            credito: frozenset() for tipo in _DECISOES_SEM_TITULO for credito in armazenamento.classificados_como(tipo)
        }
        for confirmacao in armazenamento.confirmacoes_em_vigor():
            decisoes[confirmacao.credito] = frozenset(chave_do_titulo(t.titulo) for t in confirmacao.titulos)
    finally:
        armazenamento.fechar()
    return decisoes


class _Depois:
    def __init__(
        self,
        pasta: Path,
        temporaria: Path,
        configuracao: Configuracao,
        parecerista: PareceristaDeNome,
        antes: Resultado,
        titulos: list[Titulo],
        verdades: list[_Verdade],
    ) -> None:
        self.pasta = pasta
        self.temporaria = temporaria
        self.configuracao = configuracao
        self.parecerista = parecerista
        self.titulos = titulos
        self.verdades = verdades
        self.lancamentos = [item.lancamento for item in antes.itens]
        pares = list(dict.fromkeys((conta.banco, conta.conta) for conta in configuracao.contas))
        self.extratos = tuple(
            ContaDeExtrato(f"depois_extrato_{numero:02d}.csv", banco, conta)
            for numero, (banco, conta) in enumerate(pares, start=1)
        )
        bancos_com_extrato = {extrato.banco for extrato in EXTRATOS}
        com_lancamentos = {(l.banco, l.conta) for l in self.lancamentos if l.banco in bancos_com_extrato}
        banco, conta = next((par for par in pares if par in com_lancamentos), pares[0])
        self.conta_de_cobranca = ContaDeExtrato("pix_recebidos_*.json", banco, conta)
        inicial, final = _FAIXA_DE_NOSSO_NUMERO_DA_ANALISE
        self.migracao = ConfiguracaoDeMigracao(
            franqueados=frozenset(titulo.franqueado for titulo in titulos),
            boleto=FaixaDeNossoNumero(banco=banco, conta=conta, inicial=inicial, final=final),
        )
        self.configuracao_do_depois = replace(
            configuracao,
            contas=(*self.extratos, self.conta_de_cobranca, ContaDeExtrato("retorno_cnab_*.ret", banco, conta)),
            migracao=self.migracao,
        )
        self.contrafactual = Contrafactual(
            configuracao=self.configuracao_do_depois,
            titulos=titulos,
            inicio=min((l.data for l in self.lancamentos), default=date.min),
        )
        self.franqueado_do_titulo = {chave_do_titulo(titulo): titulo.franqueado for titulo in titulos}
        self.cenarios = count(1)
        self.elegiveis, self.sempre_soltos = self._elegibilidade()

    def _elegibilidade(self) -> tuple[list[_Verdade], list[tuple[_Verdade, PorQueFicaSolto]]]:
        armazenamento = Armazenamento(self.temporaria / "elegibilidade.sqlite")
        try:
            cobrancas = emitir(self.titulos, armazenamento, self.migracao, PortaSimulada(self.configuracao.encargo))
        finally:
            armazenamento.fechar()
        por_titulo = {(c.sistema_de_origem, c.documento): c for c in cobrancas}
        pagos: set[_ChaveDoTitulo] = set()
        elegiveis: list[_Verdade] = []
        soltos: list[tuple[_Verdade, PorQueFicaSolto]] = []
        for verdade in self.verdades:
            if verdade.ja_identificado:
                continue
            if not verdade.titulos:
                soltos.append((verdade, PorQueFicaSolto.SEM_TITULO_CONHECIDO))
                continue
            if any(titulo not in por_titulo or titulo in pagos for titulo in verdade.titulos):
                soltos.append((verdade, PorQueFicaSolto.TITULO_SEM_COBRANCA))
                continue
            if self._pagamentos(verdade, por_titulo) is None:
                soltos.append((verdade, PorQueFicaSolto.NAO_IDENTIFICAVEL_PELO_VALOR))
                continue
            pagos.update(verdade.titulos)
            elegiveis.append(verdade)
        return elegiveis, soltos

    def _pagamentos(
        self, verdade: _Verdade, por_titulo: Mapping[_ChaveDoTitulo, CobrancaIdentificada]
    ) -> tuple[PagamentoSimulado, ...] | None:
        return self.contrafactual.pagamentos(
            verdade.item.lancamento, [por_titulo[titulo] for titulo in sorted(verdade.titulos)]
        )

    def cenario(self, adesao: Decimal, migrados: frozenset[str]) -> CenarioDeAdesao:
        nome = f"depois_{next(self.cenarios):03d}"
        armazenamento = Armazenamento(self.temporaria / f"{nome}.sqlite")
        try:
            porta = PortaSimulada(self.configuracao.encargo)
            migracao = replace(self.migracao, franqueados=migrados)
            cobrancas = emitir((t for t in self.titulos if t.franqueado in migrados), armazenamento, migracao, porta)
            identificados, soltos = self._planejar(cobrancas, adesao, migrados)
            plano = PlanoDePagamentos(tuple(p for pagamentos in identificados.values() for p in pagamentos))
            for pagamento in plano.pagamentos_de_cobranca:
                porta.pagar(pagamento)
            pasta = self._pasta_do_depois(self.temporaria / nome, plano, identificados, porta)
            depois = executar_conciliacao(
                pasta, armazenamento, replace(self.configuracao_do_depois, migracao=migracao), self.parecerista
            )
        finally:
            armazenamento.fechar()
        return CenarioDeAdesao(
            adesao=adesao,
            depois=depois,
            soltos={
                razao: _total(verdade.item for verdade, da_verdade in soltos if da_verdade is razao)
                for razao in PorQueFicaSolto
            },
        )

    def _planejar(
        self, cobrancas: Iterable[CobrancaIdentificada], adesao: Decimal, migrados: frozenset[str]
    ) -> tuple[dict[ChaveNatural, tuple[PagamentoSimulado, ...]], list[tuple[_Verdade, PorQueFicaSolto]]]:
        por_titulo = {(c.sistema_de_origem, c.documento): c for c in cobrancas}
        identificados: dict[ChaveNatural, tuple[PagamentoSimulado, ...]] = {}
        soltos = list(self.sempre_soltos)
        for verdade in self.elegiveis:
            if any(self.franqueado_do_titulo[titulo] not in migrados for titulo in verdade.titulos):
                soltos.append((verdade, PorQueFicaSolto.FRANQUEADO_NAO_MIGRADO))
            elif verdade.sorteio * 100 >= adesao:
                soltos.append((verdade, PorQueFicaSolto.FORA_DA_ADESAO))
            else:
                pagamentos = self._pagamentos(verdade, por_titulo)
                assert pagamentos is not None
                identificados[verdade.item.lancamento.chave_natural] = pagamentos
        return identificados, soltos

    def _pasta_do_depois(
        self,
        destino: Path,
        plano: PlanoDePagamentos,
        identificados: Mapping[ChaveNatural, tuple[PagamentoSimulado, ...]],
        porta: PortaSimulada,
    ) -> Path:
        destino.mkdir()
        for arquivo in sorted(self.pasta.iterdir()):
            de_banco = any(fnmatch(arquivo.name, conta.padrao) for conta in self.configuracao.contas)
            if arquivo.is_file() and not arquivo.name.startswith(".") and not de_banco:
                shutil.copyfile(arquivo, destino / arquivo.name)
        mantidos = [l for l in self.lancamentos if l.chave_natural not in identificados]
        com_lancamentos = {l.conta for l in mantidos} | {e.conta for e in plano.gabarito}
        for extrato in self.extratos:
            if extrato.conta in com_lancamentos:
                (destino / extrato.padrao).write_text(plano.extrato(extrato.conta, mantidos), encoding="utf-8")
        if plano.pagamentos:
            porta.trazer_retornos(destino, min(e.data for e in plano.gabarito), plano.ultimo_dia)
        return destino


def _total(itens: Iterable[Item]) -> TotalDoDestino:
    creditos = list(itens)
    return TotalDoDestino(len(creditos), sum(item.lancamento.valor_centavos for item in creditos))


def gerar_workbook_do_impacto(analise: AnaliseDeImpacto, caminho: Path) -> None:
    gerar_workbook_do_relatorio(analise.relatorio, caminho)


def gerar_workbook_do_relatorio(relatorio: RelatorioDeImpacto, caminho: Path) -> None:
    workbook = Workbook()
    resumo = workbook.active
    assert resumo is not None
    resumo.title = ABA_DO_RESUMO
    _aba_do_resumo(resumo, relatorio)
    _aba_das_ondas(workbook.create_sheet(ABA_DAS_ONDAS), relatorio)
    _aba_da_fila_por_motivo(workbook.create_sheet(ABA_DA_FILA_POR_MOTIVO), relatorio)
    _aba_do_ranking(workbook.create_sheet(ABA_DO_RANKING), relatorio.ranking)
    _aba_de_premissas(workbook.create_sheet(ABA_DE_PREMISSAS), relatorio)
    workbook.save(caminho)


def _aba_do_resumo(aba: Worksheet, relatorio: RelatorioDeImpacto) -> None:
    aba.append(
        (
            "Cenário",
            "Adesão (%)",
            "Créditos identificados",
            "Valor identificado",
            "Créditos soltos",
            "Valor solto",
            "Não identificáveis pelo valor",
            "Valor não identificável pelo valor",
            "Créditos na Fila",
            "Valor na Fila",
            "% resolvido sozinho (quantidade)",
            "% resolvido sozinho (valor)",
        )
    )
    linhas = [
        ("Antes", relatorio.antes),
        *(("Depois, todos os Franqueados migrados", cenario) for cenario in relatorio.todos_migrados),
    ]
    for nome, numeros in linhas:
        nao_identificaveis = numeros.soltos_por_razao.get(PorQueFicaSolto.NAO_IDENTIFICAVEL_PELO_VALOR)
        parte = numeros.parte_automatica
        aba.append(
            (
                nome,
                numeros.adesao,
                numeros.identificados.quantidade,
                _reais(numeros.identificados.valor_centavos),
                numeros.soltos.quantidade,
                _reais(numeros.soltos.valor_centavos),
                nao_identificaveis.quantidade if nao_identificaveis else None,
                _reais(nao_identificaveis.valor_centavos) if nao_identificaveis else None,
                numeros.fila_de_excecoes.quantidade,
                _reais(numeros.fila_de_excecoes.valor_centavos),
                _fracao(parte.percentual_da_quantidade),
                _fracao(parte.percentual_do_valor),
            )
        )
        _formatar(aba, valores=(4, 6, 8, 10), percentuais=(11, 12))
    aba.append(())
    aba.append(("Créditos do antes que ficam soltos no depois, por razão",))
    aba.append(
        (
            "Adesão (%)",
            *(f"{razao.value} ({medida})" for razao in RAZOES_DO_RESUMO for medida in ("Créditos", "valor")),
        )
    )
    for cenario in relatorio.todos_migrados:
        aba.append(
            (
                cenario.adesao,
                *(
                    valor
                    for razao in RAZOES_DO_RESUMO
                    for valor in (
                        cenario.soltos_por_razao[razao].quantidade,
                        _reais(cenario.soltos_por_razao[razao].valor_centavos),
                    )
                ),
            )
        )
        _formatar(aba, valores=range(3, 2 * len(RAZOES_DO_RESUMO) + 2, 2))
    aba.column_dimensions["A"].width = 40
    aba.freeze_panes = "A2"


def _aba_das_ondas(aba: Worksheet, relatorio: RelatorioDeImpacto) -> None:
    aba.append(
        (
            "Onda acumulada",
            "Franqueados migrados",
            "Adesão (%)",
            "Créditos identificados",
            "Créditos de Franqueados não migrados",
            "Créditos na Fila",
            "Valor na Fila",
            "% resolvido sozinho (quantidade)",
            "% resolvido sozinho (valor)",
        )
    )
    linhas: list[tuple[str | int, NumerosDoCenario]] = [
        ("Antes", relatorio.antes),
        *((onda.onda, cenario) for onda in relatorio.ondas for cenario in onda.cenarios),
        *(("Todos os Franqueados", cenario) for cenario in relatorio.todos_migrados),
    ]
    for onda, numeros in linhas:
        nao_migrados = numeros.soltos_por_razao.get(PorQueFicaSolto.FRANQUEADO_NAO_MIGRADO)
        parte = numeros.parte_automatica
        aba.append(
            (
                onda,
                numeros.franqueados_migrados,
                numeros.adesao,
                numeros.identificados.quantidade,
                nao_migrados.quantidade if nao_migrados else None,
                numeros.fila_de_excecoes.quantidade,
                _reais(numeros.fila_de_excecoes.valor_centavos),
                _fracao(parte.percentual_da_quantidade),
                _fracao(parte.percentual_do_valor),
            )
        )
        _formatar(aba, valores=(7,), percentuais=(8, 9))
    aba.append(())
    aba.append((EXPLICACAO_DAS_ONDAS,))
    aba.column_dimensions["A"].width = 22
    aba.freeze_panes = "A2"


def _aba_da_fila_por_motivo(aba: Worksheet, relatorio: RelatorioDeImpacto) -> None:
    cenarios = (relatorio.antes, *relatorio.todos_migrados)
    aba.append(
        (
            "Motivo de não identificação",
            *(f"{cenario.nome} ({medida})" for cenario in cenarios for medida in ("Créditos", "valor")),
        )
    )
    for motivo in (*MotivoDeNaoIdentificacao, None):
        totais = [c.fila_de_excecoes if motivo is None else c.fila_por_motivo[motivo] for c in cenarios]
        aba.append(
            (
                "Total" if motivo is None else motivo.value,
                *(valor for total in totais for valor in (total.quantidade, _reais(total.valor_centavos))),
            )
        )
        _formatar(aba, valores=range(3, 2 * len(cenarios) + 2, 2))
    aba.column_dimensions["A"].width = 40
    aba.freeze_panes = "B2"


def _aba_do_ranking(aba: Worksheet, ranking: RankingDeMigracao) -> None:
    aba.append(("Onda", "Posição", "Franqueado", "Raiz do CNPJ", "Créditos na Fila", "Valor"))
    for franqueado in ranking.franqueados:
        aba.append(
            (
                franqueado.onda,
                franqueado.posicao,
                franqueado.nome,
                franqueado.raiz,
                franqueado.quantidade,
                _reais(franqueado.valor_centavos),
            )
        )
        _formatar(aba, valores=(6,))
    aba.append(())
    sem_franqueado = ranking.sem_franqueado
    aba.append((None, None, sem_franqueado.nome, None, sem_franqueado.quantidade, _reais(sem_franqueado.valor_centavos)))
    _formatar(aba, valores=(6,))
    aba.append((None, None, EXPLICACAO_DO_SEM_FRANQUEADO))
    aba.column_dimensions["C"].width = 60
    aba.freeze_panes = "A2"


def _aba_de_premissas(aba: Worksheet, relatorio: RelatorioDeImpacto) -> None:
    aba.append(("Premissa", "Valor"))
    for premissa in relatorio.premissas:
        aba.append(premissa)
    aba.column_dimensions["A"].width = 52
    aba.column_dimensions["B"].width = 120


def _premissas(analise: AnaliseDeImpacto) -> tuple[tuple[str, ValorDaPremissa], ...]:
    configuracao = analise.configuracao
    encargo = configuracao.encargo
    parametros = configuracao.analise_de_impacto
    cobranca = analise.conta_de_cobranca
    return (
        ("Semente", parametros.semente),
        ("Faixa de Adesão (%)", "; ".join(formatar_adesao(adesao) for adesao in parametros.faixa_de_adesao)),
        (
            "Proporções do simulador",
            "não se aplicam: o Plano contrafactual mantém o valor, a data e o Franqueado de cada Crédito do antes; "
            "as proporções de pagamento parcial, atraso e Crédito solto só valem no Plano por proporções",
        ),
        ("Multa por atraso (%)", encargo.multa_percentual),
        ("Juros ao mês (%)", encargo.juros_ao_mes_percentual),
        ("Tolerância do Encargo (R$)", _reais(encargo.tolerancia_centavos)),
        ("Tamanho da Onda de migração (Franqueados)", parametros.tamanho_da_onda),
        (
            "Motivos do Ranking de migração",
            "; ".join(motivo.value for motivo in MotivoDeNaoIdentificacao if motivo in RankingDeMigracao.MOTIVOS),
        ),
        (
            "Franqueado do Crédito no ranking",
            "o identificado pela conciliação; sem ele, o dos Títulos sugeridos na Fila quando são de um só Franqueado",
        ),
        (
            "Conciliação do antes",
            "a mesma da execução diária, com armazenamento temporário (sem decisões da Analista) e o Parecerista "
            "de nome da configuração",
        ),
        (
            "Fonte da verdade do Título de cada Crédito",
            "o gabarito, quando a pasta vem do gerador; senão as decisões confirmadas da Analista no armazenamento "
            "da conciliação diária; senão a Proposta da Lista ou a sugestão da Fila do antes",
        ),
        *((f"Créditos pela fonte: {fonte.value}", analise.fontes.get(fonte, 0)) for fonte in FonteDaVerdade),
        (
            "Limite da fonte da verdade",
            f"{analise.fontes.get(FonteDaVerdade.PROPOSTA_OU_SUGESTAO, 0)} de {sum(analise.fontes.values())} Créditos "
            "não têm gabarito nem decisão confirmada da Analista: a verdade deles é a Proposta ou a sugestão do "
            "próprio antes, então o depois supõe que o antes acertou o Título e um erro do antes passa para o depois",
        ),
        (
            "Franqueados migrados",
            "todos, no Resumo do impacto e na Fila por motivo; na aba Ondas, os das ondas acumuladas",
        ),
        (
            "Ondas de migração",
            "cada onda acumulada migra os Franqueados do Ranking de migração até ela, para cada Adesão, com o mesmo "
            "sorteio; Crédito de Título de Franqueado não migrado fica solto e só os Títulos dos migrados recebem "
            "Cobrança identificada",
        ),
        (
            "Sorteio da Adesão",
            "um número por Crédito, fixo pela semente; o Crédito chega identificado quando o sorteio fica abaixo da "
            "Adesão, então a Adesão maior contém a menor",
        ),
        (
            "Pagamento identificado",
            "mesmo valor, data e Franqueado do Crédito do antes; Pix com txid só pelo valor da cobrança na data "
            "(com multa e juros quando atrasado); boleto da plataforma, só para Título sem nosso número do Protheus, "
            "até o valor com Encargo, inclusive parcial (todo boleto da plataforma autoriza pagamento parcial); "
            "quando os dois aceitam, o Pix",
        ),
        (
            "Crédito que pagou vários Títulos",
            "um pagamento identificado por Título, no mesmo dia, cada um pelo valor do Título ou cada um pelo valor "
            "com Encargo, quando essa soma é o Crédito; senão, não identificável pelo valor",
        ),
        (
            "Fica solto no depois",
            "Crédito sem Título conhecido; Título fora dos em aberto, em Possível duplicidade entre sistemas ou com "
            "a cobrança já paga por um Crédito anterior; valor que nenhum Identificador de cobrança aceita",
        ),
        ("Créditos que já chegavam pelo nosso número", "continuam identificados, como vieram"),
        ("Conta de cobrança", f"Pix e boleto da plataforma creditados na conta {cobranca.conta} ({cobranca.banco})"),
        (
            "Conciliação do depois",
            "emissão pela porta simulada, Extratos e Retornos de cobrança gerados pelo simulador e a mesma "
            "conciliação, com armazenamento temporário novo e o mesmo Parecerista de nome",
        ),
    )


def _formatar(aba: Worksheet, valores: Iterable[int] = (), percentuais: Iterable[int] = ()) -> None:
    for coluna in valores:
        aba.cell(row=aba.max_row, column=coluna).number_format = _FORMATO_DE_VALOR
    for coluna in percentuais:
        aba.cell(row=aba.max_row, column=coluna).number_format = _FORMATO_DE_PERCENTUAL


def _reais(centavos: int) -> Decimal:
    return Decimal(centavos) / 100


def _fracao(percentual: Fraction | None) -> float | None:
    return float(percentual) / 100 if percentual is not None else None


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="analisar-impacto",
        description="Analisa o impacto da Cobrança identificada sobre uma pasta base: o antes, o depois para cada "
        "Adesão e o Ranking de migração.",
    )
    parser.add_argument("pasta", type=Path, help="pasta base com as exportações e os Extratos, do jeito que vêm")
    parser.add_argument("--configuracao", type=Path, default=Path("conciliacao.toml"))
    parser.add_argument("--saida", type=Path, default=Path("analise_de_impacto.xlsx"))
    parser.add_argument(
        "--estado",
        type=Path,
        default=Path("conciliacao.sqlite"),
        help="armazenamento da conciliação diária: as decisões confirmadas da Analista dizem qual Título cada "
        "Crédito paga, e o resultado da análise é gravado nele para a tela local",
    )
    opcoes = parser.parse_args(argumentos)

    if not opcoes.pasta.is_dir():
        print(f"Pasta base não encontrada: {opcoes.pasta}", file=sys.stderr)
        return 2
    try:
        configuracao = carregar_configuracao(opcoes.configuracao)
    except FileNotFoundError:
        print(f"Configuração não encontrada: {opcoes.configuracao}", file=sys.stderr)
        return 2
    except ConfiguracaoInvalida as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        return 2

    try:
        analise = analisar_impacto(
            opcoes.pasta,
            configuracao,
            parecerista_da_configuracao(configuracao.ia),
            estado=opcoes.estado if opcoes.estado.is_file() else None,
        )
    except ConferenciaDeSomaFalhou as erro:
        print(str(erro), file=sys.stderr)
        return 1
    relatorio = analise.relatorio
    gerar_workbook_do_relatorio(relatorio, opcoes.saida)
    armazenamento = Armazenamento(opcoes.estado)
    try:
        with armazenamento.transacao():
            armazenamento.registrar_analise_de_impacto(relatorio)
    finally:
        armazenamento.fechar()
    print(f"Análise de impacto gerada em {opcoes.saida} e gravada em {opcoes.estado}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
