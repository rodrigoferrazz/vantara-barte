import json
import shutil
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
from fnmatch import fnmatch
from pathlib import Path

from conciliacao.adaptadores import EXTRATOS
from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao, ConfiguracaoDeMigracao, ContaDeExtrato, FaixaDeNossoNumero
from conciliacao.dominio import ChaveDoIdentificador, TipoDeIdentificador, VinculoDeCobranca
from conciliacao.emissao import emitir, titulos_em_aberto_fora_de_duplicidade
from conciliacao.execucao import calcular_data_de_referencia
from conciliacao.identificadores import FaixaDeNossoNumeroEsgotada
from conciliacao.porta import CobrancaIdentificada, PortaSimulada, arquivo_de_pix_recebidos, arquivo_de_retorno_cnab
from conciliacao.simulador import (
    ConfiguracaoDoSimulador,
    ConfiguracaoDoSimuladorInvalida,
    ProporcoesDoSimulador,
    plano_por_proporcoes,
)

_FAIXA_DE_NOSSO_NUMERO = ("0000700001", "0000799999")
_PADRAO_DO_PIX = "*pix_recebidos*.json"
_PADRAO_DO_RETORNO = "*retorno_cnab*.ret"
_SEMENTE = 1
_TODOS_PAGAM_EM_DIA = ProporcoesDoSimulador(
    em_dia=1, atraso_com_multa=0, atraso_sem_encargo=0, parcial=0, credito_solto=0
)
_ESTADO = "estado.sqlite"
_ENTRADA = "entrada"
_SAIDA = "saida.xlsx"
_PAGAMENTOS = "pagamentos-simulados.json"


class DemonstracaoRecusada(Exception):
    pass


@dataclass(frozen=True)
class CobrancaEmitida:
    sistema_de_origem: str
    documento: str
    franqueado: str
    valor_centavos: int
    vencimento: date
    txid: str | None
    nosso_numero: str | None
    paga_em: date | None


@dataclass(frozen=True)
class PagamentosSimulados:
    arquivos: tuple[str, ...]
    sem_pagamento: tuple[str, ...]


@dataclass(frozen=True)
class SituacaoDaDemonstracao:
    ativa: bool
    cobrancas: tuple[CobrancaEmitida, ...]
    pagamentos: PagamentosSimulados | None


def configuracao_da_demonstracao(base: Configuracao, migrados: frozenset[str] = frozenset()) -> Configuracao:
    faixa = base.migracao.boleto if base.migracao is not None else None
    if faixa is None:
        bancos_com_extrato = {extrato.banco for extrato in EXTRATOS}
        conta = next((c for c in base.contas if c.banco in bancos_com_extrato), None)
        if conta is None:
            raise DemonstracaoRecusada("Nenhuma conta da configuração tem Extrato que a plataforma leia.")
        faixa = FaixaDeNossoNumero(conta.banco, conta.conta, *_FAIXA_DE_NOSSO_NUMERO)
    hoje = date.today()
    da_porta = {
        _PADRAO_DO_PIX: arquivo_de_pix_recebidos(hoje, hoje),
        _PADRAO_DO_RETORNO: arquivo_de_retorno_cnab(faixa.banco, hoje, hoje),
    }
    novas = tuple(
        ContaDeExtrato(padrao=padrao, banco=faixa.banco, conta=faixa.conta)
        for padrao, nome in da_porta.items()
        if not any(fnmatch(nome, conta.padrao) for conta in base.contas)
    )
    return replace(
        base,
        contas=(*base.contas, *novas),
        migracao=ConfiguracaoDeMigracao(franqueados=migrados, boleto=faixa),
    )


@dataclass(frozen=True)
class Demonstracao:
    estado: Path
    entrada: Path
    saida: Path

    @property
    def _copia(self) -> Path:
        return self.estado.with_name(f"{self.estado.name}.demonstracao")

    @property
    def ativa(self) -> bool:
        return self._copia.is_dir()

    def ajustar(self, configuracao: Configuracao) -> Configuracao:
        return configuracao_da_demonstracao(configuracao) if self.ativa else configuracao

    def emitir(self, base: Configuracao) -> None:
        with self._armazenamento() as armazenamento:
            if armazenamento.ultima_execucao() is None:
                raise DemonstracaoRecusada("Concilie antes de emitir: a emissão parte dos títulos da última execução.")
        comecou_agora = not self.ativa
        if comecou_agora:
            self._guardar_o_estado_inicial()
        with self._armazenamento() as armazenamento:
            referencia = calcular_data_de_referencia(armazenamento, configuracao_da_demonstracao(base)).data
            if referencia is not None:
                titulos = titulos_em_aberto_fora_de_duplicidade(armazenamento)
                configuracao = configuracao_da_demonstracao(base, frozenset(t.franqueado for t in titulos))
                assert configuracao.migracao is not None
                try:
                    emitir(titulos, armazenamento, configuracao.migracao, PortaSimulada(configuracao.encargo))
                except FaixaDeNossoNumeroEsgotada as erro:
                    raise DemonstracaoRecusada(f"Nenhuma cobrança emitida: {erro}.") from None
            ha_cobrancas = bool(armazenamento.vinculos_enviados())
        if not ha_cobrancas and comecou_agora:
            shutil.rmtree(self._copia)
        if referencia is None:
            raise DemonstracaoRecusada("Sem Data de referência: há conta configurada sem Extrato.")
        if not ha_cobrancas:
            raise DemonstracaoRecusada("Nenhum título em aberto na última execução: não há o que cobrar.")

    def simular_pagamentos(self, base: Configuracao) -> PagamentosSimulados:
        if not self.ativa:
            raise DemonstracaoRecusada("Emita as cobranças antes de simular os pagamentos.")
        if (self._copia / _PAGAMENTOS).is_file():
            raise DemonstracaoRecusada("Os pagamentos já foram simulados. Zere a demonstração para simular de novo.")
        configuracao = configuracao_da_demonstracao(base)
        with self._armazenamento() as armazenamento:
            cobrancas = _cobrancas_emitidas(armazenamento)
            titulos = titulos_em_aberto_fora_de_duplicidade(armazenamento)
            com_credito = armazenamento.titulos_propostos_na_ultima_execucao()
        a_pagar = [c for c in cobrancas if (c.sistema_de_origem, c.documento) not in com_credito]
        if not a_pagar:
            raise DemonstracaoRecusada(
                "Todas as cobranças emitidas são de títulos que já têm um crédito do extrato na última conciliação."
            )
        porta = PortaSimulada(configuracao.encargo)
        for cobranca in cobrancas:
            porta.emitir(cobranca)
        try:
            plano = plano_por_proporcoes(
                a_pagar, titulos, configuracao, ConfiguracaoDoSimulador(_SEMENTE, date.min, _TODOS_PAGAM_EM_DIA)
            )
        except ConfiguracaoDoSimuladorInvalida as erro:
            raise DemonstracaoRecusada(f"O simulador recusou a configuração: {erro}.") from None
        for pagamento in plano.pagamentos_de_cobranca:
            porta.pagar(pagamento)
        self.entrada.mkdir(parents=True, exist_ok=True)
        retornos = porta.trazer_retornos(self.entrada, min(e.data for e in plano.gabarito), plano.ultimo_dia)
        extratos = []
        for conta in sorted({esperado.conta for esperado in plano.gabarito}):
            extrato = self.entrada / _nome_do_extrato(configuracao, conta, {r.name for r in retornos})
            extrato.write_text(plano.extrato(conta), encoding="utf-8")
            extratos.append(extrato)
        pagos = {(p.cobranca.sistema_de_origem, p.cobranca.documento) for p in plano.pagamentos_de_cobranca}
        simulados = PagamentosSimulados(
            arquivos=tuple(caminho.name for caminho in [*extratos, *retornos]),
            sem_pagamento=tuple(c.documento for c in cobrancas if (c.sistema_de_origem, c.documento) not in pagos),
        )
        (self._copia / _PAGAMENTOS).write_text(
            json.dumps({"arquivos": simulados.arquivos, "sem_pagamento": simulados.sem_pagamento}), encoding="utf-8"
        )
        return simulados

    def zerar(self) -> None:
        if not self.ativa:
            return
        _restaurar_arquivo(self._copia / _ESTADO, self.estado)
        _restaurar_pasta(self._copia / _ENTRADA, self.entrada)
        _restaurar_arquivo(self._copia / _SAIDA, self.saida)
        shutil.rmtree(self._copia)

    def situacao(self) -> SituacaoDaDemonstracao:
        if not self.ativa:
            return SituacaoDaDemonstracao(False, (), None)
        with self._armazenamento() as armazenamento:
            cobrancas = cobrancas_emitidas(armazenamento)
        pagamentos = self._copia / _PAGAMENTOS
        if not pagamentos.is_file():
            return SituacaoDaDemonstracao(True, cobrancas, None)
        lidos = json.loads(pagamentos.read_text(encoding="utf-8"))
        return SituacaoDaDemonstracao(
            True, cobrancas, PagamentosSimulados(tuple(lidos["arquivos"]), tuple(lidos["sem_pagamento"]))
        )

    @contextmanager
    def _armazenamento(self) -> Iterator[Armazenamento]:
        if not self.estado.exists():
            raise DemonstracaoRecusada("Concilie antes de emitir: a emissão parte dos títulos da última execução.")
        armazenamento = Armazenamento(self.estado)
        try:
            yield armazenamento
        finally:
            armazenamento.fechar()

    def _guardar_o_estado_inicial(self) -> None:
        self._copia.mkdir()
        shutil.copy2(self.estado, self._copia / _ESTADO)
        if self.entrada.is_dir():
            shutil.copytree(self.entrada, self._copia / _ENTRADA)
        if self.saida.is_file():
            shutil.copy2(self.saida, self._copia / _SAIDA)


def cobrancas_emitidas(armazenamento: Armazenamento) -> tuple[CobrancaEmitida, ...]:
    """Paga quando um Retorno de cobrança com o txid ou o nosso número já foi ligado a um Crédito."""
    nomes = {(t.sistema_de_origem, t.documento): t.nome_do_franqueado for t in armazenamento.ultima_fotografia()}
    pagas = {r.chave_do_identificador: r.data for r in armazenamento.retornos_dos_creditos().values()}
    return tuple(
        CobrancaEmitida(
            sistema_de_origem=c.sistema_de_origem,
            documento=c.documento,
            franqueado=nomes.get((c.sistema_de_origem, c.documento), ""),
            valor_centavos=c.valor_centavos,
            vencimento=c.vencimento,
            txid=c.txid,
            nosso_numero=c.nosso_numero,
            paga_em=min(
                (pagas[chave] for chave in _chaves_da_cobranca(c) if chave in pagas),
                default=None,
            ),
        )
        for c in _cobrancas_emitidas(armazenamento)
    )


def _chaves_da_cobranca(cobranca: CobrancaIdentificada) -> list[ChaveDoIdentificador]:
    return [
        (tipo, identificador)
        for tipo, identificador in (
            (TipoDeIdentificador.TXID, cobranca.txid),
            (TipoDeIdentificador.NOSSO_NUMERO, cobranca.nosso_numero),
        )
        if identificador is not None
    ]


def _cobrancas_emitidas(armazenamento: Armazenamento) -> list[CobrancaIdentificada]:
    enviados = armazenamento.vinculos_enviados()
    por_titulo: dict[tuple[str, str], dict[TipoDeIdentificador, str]] = defaultdict(dict)
    primeiro: dict[tuple[str, str], VinculoDeCobranca] = {}
    for vinculo in armazenamento.vinculos_de_cobranca():
        if vinculo.chave not in enviados:
            continue
        chave = (vinculo.sistema_de_origem, vinculo.documento)
        por_titulo[chave][vinculo.tipo] = vinculo.identificador
        primeiro.setdefault(chave, vinculo)
    return [
        CobrancaIdentificada(
            sistema_de_origem=vinculo.sistema_de_origem,
            documento=vinculo.documento,
            valor_centavos=vinculo.valor_centavos,
            vencimento=vinculo.vencimento,
            cnpj=vinculo.cnpj,
            txid=por_titulo[chave].get(TipoDeIdentificador.TXID),
            nosso_numero=por_titulo[chave].get(TipoDeIdentificador.NOSSO_NUMERO),
        )
        for chave, vinculo in primeiro.items()
    ]


def _nome_do_extrato(configuracao: Configuracao, conta: str, da_porta: set[str]) -> str:
    for candidata in configuracao.contas:
        if candidata.conta != conta or any(fnmatch(nome, candidata.padrao) for nome in da_porta):
            continue
        if any(caractere in candidata.padrao for caractere in "?["):
            continue
        nome = _preencher(candidata.padrao)
        if [c for c in configuracao.contas if fnmatch(nome, c.padrao)] == [candidata]:
            return nome
    raise DemonstracaoRecusada(f"Nenhum padrão de [[contas]] da conta {conta} dá um nome de Extrato só dela.")


def _preencher(padrao: str) -> str:
    if "*" not in padrao:
        return padrao
    antes, depois = padrao.split("*", 1)
    marca = "demonstracao_" if not antes else "_demonstracao"
    return f"{antes}{marca}{depois.replace('*', '')}"


def _restaurar_arquivo(copia: Path, destino: Path) -> None:
    if copia.is_file():
        shutil.copy2(copia, destino)
    else:
        destino.unlink(missing_ok=True)


def _restaurar_pasta(copia: Path, destino: Path) -> None:
    shutil.rmtree(destino, ignore_errors=True)
    if copia.is_dir():
        shutil.copytree(copia, destino)

