import argparse
import random
import shutil
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum
from fnmatch import fnmatch
from fractions import Fraction
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
    ParteAutomatica,
    RankingDeMigracao,
    Resultado,
    TipoDeDecisao,
    TipoDeEvidencia,
    Titulo,
    TotalDoDestino,
)
from conciliacao.emissao import emitir, titulos_em_aberto_fora_de_duplicidade
from conciliacao.execucao import executar_conciliacao
from conciliacao.gerador import LancamentoEsperado
from conciliacao.parecerista import PareceristaDeNome, parecerista_da_configuracao
from conciliacao.porta import CobrancaIdentificada, PortaSimulada
from conciliacao.simulador import Contrafactual, PagamentoSimulado, PlanoDePagamentos

ABA_DO_RESUMO = "Resumo do impacto"
ABA_DA_FILA_POR_MOTIVO = "Fila por motivo"
ABA_DO_RANKING = "Ranking de migração"
ABA_DE_PREMISSAS = "Premissas"

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


class PorQueFicaSolto(StrEnum):
    SEM_TITULO_CONHECIDO = "sem Título conhecido"
    TITULO_SEM_COBRANCA = "Título sem Cobrança identificada"
    NAO_IDENTIFICAVEL_PELO_VALOR = "não identificável pelo valor"
    FORA_DA_ADESAO = "sorteio acima da Adesão"


@dataclass(frozen=True)
class CenarioDeAdesao:
    adesao: Decimal
    depois: Resultado
    soltos: dict[PorQueFicaSolto, TotalDoDestino]


@dataclass(frozen=True)
class AnaliseDeImpacto:
    configuracao: Configuracao
    antes: Resultado
    ranking: RankingDeMigracao
    fontes: dict[FonteDaVerdade, int]
    conta_de_cobranca: ContaDeExtrato
    cenarios: tuple[CenarioDeAdesao, ...]


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
        depois = _Depois(pasta, temporaria, configuracao, parecerista, antes, titulos, verdades)
        cenarios = tuple(depois.cenario(adesao) for adesao in configuracao.analise_de_impacto.faixa_de_adesao)
    return AnaliseDeImpacto(
        configuracao=configuracao,
        antes=antes,
        ranking=RankingDeMigracao.da_fila(antes.itens, nomes, configuracao.analise_de_impacto.tamanho_da_onda),
        fontes=dict(Counter(verdade.fonte for verdade in verdades)),
        conta_de_cobranca=depois.conta_de_cobranca,
        cenarios=cenarios,
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

    def cenario(self, adesao: Decimal) -> CenarioDeAdesao:
        nome = f"depois_{adesao}"
        armazenamento = Armazenamento(self.temporaria / f"{nome}.sqlite")
        try:
            porta = PortaSimulada(self.configuracao.encargo)
            cobrancas = emitir(self.titulos, armazenamento, self.migracao, porta)
            identificados, soltos = self._planejar(cobrancas, adesao)
            plano = PlanoDePagamentos(tuple(p for pagamentos in identificados.values() for p in pagamentos))
            for pagamento in plano.pagamentos_de_cobranca:
                porta.pagar(pagamento)
            pasta = self._pasta_do_depois(self.temporaria / nome, plano, identificados, porta)
            depois = executar_conciliacao(pasta, armazenamento, self.configuracao_do_depois, self.parecerista)
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
        self, cobrancas: Iterable[CobrancaIdentificada], adesao: Decimal
    ) -> tuple[dict[ChaveNatural, tuple[PagamentoSimulado, ...]], list[tuple[_Verdade, PorQueFicaSolto]]]:
        por_titulo = {(c.sistema_de_origem, c.documento): c for c in cobrancas}
        pagos: set[_ChaveDoTitulo] = set()
        identificados: dict[ChaveNatural, tuple[PagamentoSimulado, ...]] = {}
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
            pagamentos = self.contrafactual.pagamentos(
                verdade.item.lancamento, [por_titulo[titulo] for titulo in sorted(verdade.titulos)]
            )
            if pagamentos is None:
                soltos.append((verdade, PorQueFicaSolto.NAO_IDENTIFICAVEL_PELO_VALOR))
                continue
            pagos.update(verdade.titulos)
            if verdade.sorteio * 100 < adesao:
                identificados[verdade.item.lancamento.chave_natural] = pagamentos
            else:
                soltos.append((verdade, PorQueFicaSolto.FORA_DA_ADESAO))
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
    workbook = Workbook()
    resumo = workbook.active
    assert resumo is not None
    resumo.title = ABA_DO_RESUMO
    _aba_do_resumo(resumo, analise)
    _aba_da_fila_por_motivo(workbook.create_sheet(ABA_DA_FILA_POR_MOTIVO), analise)
    _aba_do_ranking(workbook.create_sheet(ABA_DO_RANKING), analise.ranking)
    _aba_de_premissas(workbook.create_sheet(ABA_DE_PREMISSAS), analise)
    workbook.save(caminho)


def _aba_do_resumo(aba: Worksheet, analise: AnaliseDeImpacto) -> None:
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
    linhas: list[tuple[str, Decimal | None, Resultado, TotalDoDestino | None]] = [
        ("Antes", None, analise.antes, None),
        *(
            (
                "Depois, todos os Franqueados migrados",
                cenario.adesao,
                cenario.depois,
                cenario.soltos[PorQueFicaSolto.NAO_IDENTIFICAVEL_PELO_VALOR],
            )
            for cenario in analise.cenarios
        ),
    ]
    for nome, adesao, resultado, nao_identificaveis in linhas:
        chegada = ChegadaDosCreditos.do_resultado(resultado)
        fila = resultado.resumo.totais[Destino.FILA_DE_EXCECOES]
        parte = ParteAutomatica.dos_totais(resultado.resumo.totais)
        aba.append(
            (
                nome,
                adesao,
                chegada.identificados.quantidade,
                _reais(chegada.identificados.valor_centavos),
                chegada.soltos.quantidade,
                _reais(chegada.soltos.valor_centavos),
                nao_identificaveis.quantidade if nao_identificaveis else None,
                _reais(nao_identificaveis.valor_centavos) if nao_identificaveis else None,
                fila.quantidade,
                _reais(fila.valor_centavos),
                _fracao(parte.percentual_da_quantidade),
                _fracao(parte.percentual_do_valor),
            )
        )
        _formatar(aba, valores=(4, 6, 8, 10), percentuais=(11, 12))
    aba.append(())
    aba.append(("Créditos do antes que ficam soltos no depois, por razão",))
    aba.append(("Adesão (%)", *(f"{razao.value} ({medida})" for razao in PorQueFicaSolto for medida in ("Créditos", "valor"))))
    for cenario in analise.cenarios:
        aba.append(
            (
                cenario.adesao,
                *(
                    valor
                    for razao in PorQueFicaSolto
                    for valor in (cenario.soltos[razao].quantidade, _reais(cenario.soltos[razao].valor_centavos))
                ),
            )
        )
        _formatar(aba, valores=range(3, 2 * len(PorQueFicaSolto) + 2, 2))
    aba.column_dimensions["A"].width = 40
    aba.freeze_panes = "A2"


def _aba_da_fila_por_motivo(aba: Worksheet, analise: AnaliseDeImpacto) -> None:
    cenarios = [("antes", analise.antes), *((f"Adesão {_adesao(c.adesao)}", c.depois) for c in analise.cenarios)]
    aba.append(("Motivo de não identificação", *(f"{nome} ({medida})" for nome, _ in cenarios for medida in ("Créditos", "valor"))))
    fila_por_cenario = [resultado.fila_de_excecoes for _, resultado in cenarios]
    for motivo in (*MotivoDeNaoIdentificacao, None):
        totais = [_total(i for i in fila if motivo is None or i.motivo is motivo) for fila in fila_por_cenario]
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
    aba.append((None, None, "Créditos sem Franqueado não entram em nenhuma Onda de migração."))
    aba.column_dimensions["C"].width = 60
    aba.freeze_panes = "A2"


def _aba_de_premissas(aba: Worksheet, analise: AnaliseDeImpacto) -> None:
    configuracao = analise.configuracao
    encargo = configuracao.encargo
    parametros = configuracao.analise_de_impacto
    cobranca = analise.conta_de_cobranca
    premissas: list[tuple[str, int | Decimal | str]] = [
        ("Semente", parametros.semente),
        ("Faixa de Adesão (%)", "; ".join(_adesao(adesao) for adesao in parametros.faixa_de_adesao)),
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
            "o gabarito, quando a pasta vem do gerador; senão as decisões confirmadas da Analista, quando um "
            "armazenamento é informado; senão a Proposta da Lista ou a sugestão da Fila do antes",
        ),
        *((f"Créditos pela fonte: {fonte.value}", analise.fontes.get(fonte, 0)) for fonte in FonteDaVerdade),
        ("Franqueados migrados", "todos"),
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
    ]
    aba.append(("Premissa", "Valor"))
    for premissa in premissas:
        aba.append(premissa)
    aba.column_dimensions["A"].width = 52
    aba.column_dimensions["B"].width = 120


def _formatar(aba: Worksheet, valores: Iterable[int] = (), percentuais: Iterable[int] = ()) -> None:
    for coluna in valores:
        aba.cell(row=aba.max_row, column=coluna).number_format = _FORMATO_DE_VALOR
    for coluna in percentuais:
        aba.cell(row=aba.max_row, column=coluna).number_format = _FORMATO_DE_PERCENTUAL


def _reais(centavos: int) -> Decimal:
    return Decimal(centavos) / 100


def _fracao(percentual: Fraction | None) -> float | None:
    return float(percentual) / 100 if percentual is not None else None


def _adesao(adesao: Decimal) -> str:
    return f"{adesao:f}".replace(".", ",") + "%"


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
        help="armazenamento da conciliação diária, cujas decisões confirmadas da Analista dizem qual Título cada "
        "Crédito paga; só é lido",
    )
    opcoes = parser.parse_args(argumentos)

    if not opcoes.pasta.is_dir():
        print(f"Pasta base não encontrada: {opcoes.pasta}", file=sys.stderr)
        return 2
    if opcoes.estado is not None and not opcoes.estado.is_file():
        print(f"Armazenamento não encontrado: {opcoes.estado}", file=sys.stderr)
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
            opcoes.pasta, configuracao, parecerista_da_configuracao(configuracao.ia), estado=opcoes.estado
        )
    except ConferenciaDeSomaFalhou as erro:
        print(str(erro), file=sys.stderr)
        return 1
    gerar_workbook_do_impacto(analise, opcoes.saida)
    print(f"Análise de impacto gerada em {opcoes.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
