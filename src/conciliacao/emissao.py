import argparse
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import date
from itertools import count
from pathlib import Path

from conciliacao.acompanhamento import chave_do_titulo, saldos
from conciliacao.armazenamento import Armazenamento
from conciliacao.calendario import vencimento_efetivo
from conciliacao.configuracao import (
    Configuracao,
    ConfiguracaoDeMigracao,
    ConfiguracaoInvalida,
    carregar_configuracao,
)
from conciliacao.dominio import OrigemDoIdentificador, TipoDeIdentificador, Titulo, VinculoDeCobranca
from conciliacao.execucao import calcular_data_de_referencia, possiveis_duplicidades_nao_decididas
from conciliacao.identificadores import FaixaDeNossoNumeroEsgotada, gerar_txid, nossos_numeros_livres
from conciliacao.motor import chaves_em_duplicidade
from conciliacao.porta import CobrancaIdentificada, PortaDeCobranca, PortaSimulada


@dataclass(frozen=True)
class Emissao:
    data_de_referencia: date | None
    emitidas: tuple[CobrancaIdentificada, ...]


def emitir_cobrancas(armazenamento: Armazenamento, configuracao: Configuracao, porta: PortaDeCobranca) -> Emissao:
    migracao = configuracao.migracao
    referencia = calcular_data_de_referencia(armazenamento, configuracao).data
    if migracao is None or referencia is None:
        return Emissao(referencia, ())
    elegiveis = [
        titulo
        for titulo in titulos_em_aberto_fora_de_duplicidade(armazenamento)
        if titulo.franqueado in migracao.franqueados and vencimento_efetivo(titulo.vencimento) >= referencia
    ]
    return Emissao(referencia, emitir(elegiveis, armazenamento, migracao, porta))


def emitir(
    titulos: Iterable[Titulo], armazenamento: Armazenamento, migracao: ConfiguracaoDeMigracao, porta: PortaDeCobranca
) -> tuple[CobrancaIdentificada, ...]:
    with armazenamento.transacao():
        existentes = armazenamento.vinculos_de_cobranca()
        vinculos = {(v.tipo, v.sistema_de_origem, v.documento): v for v in existentes}
        enviados = armazenamento.vinculos_enviados()
        geradores: dict[TipoDeIdentificador, Iterator[str]] = {
            TipoDeIdentificador.TXID: map(
                gerar_txid, count(armazenamento.identificadores_gerados(TipoDeIdentificador.TXID) + 1)
            )
        }
        if migracao.boleto is not None:
            usados = {v.identificador for v in existentes if v.tipo is TipoDeIdentificador.NOSSO_NUMERO}
            geradores[TipoDeIdentificador.NOSSO_NUMERO] = nossos_numeros_livres(migracao.boleto, usados)
        a_enviar: dict[tuple[str, str, int, date], list[VinculoDeCobranca]] = defaultdict(list)
        for titulo in titulos:
            for tipo, gerador in geradores.items():
                if tipo is TipoDeIdentificador.NOSSO_NUMERO and titulo.nosso_numero is not None:
                    continue
                vinculo = vinculos.get((tipo, *chave_do_titulo(titulo)))
                if vinculo is None:
                    vinculo = _vinculo(titulo, tipo, next(gerador))
                    armazenamento.registrar_vinculo(vinculo)
                if vinculo.chave not in enviados:
                    a_enviar[(*chave_do_titulo(titulo), vinculo.valor_centavos, vinculo.vencimento)].append(vinculo)
    emitidas = []
    for do_titulo in a_enviar.values():
        identificadores = {vinculo.tipo: vinculo.identificador for vinculo in do_titulo}
        primeiro = do_titulo[0]
        cobranca = CobrancaIdentificada(
            sistema_de_origem=primeiro.sistema_de_origem,
            documento=primeiro.documento,
            valor_centavos=primeiro.valor_centavos,
            vencimento=primeiro.vencimento,
            cnpj=primeiro.cnpj,
            txid=identificadores.get(TipoDeIdentificador.TXID),
            nosso_numero=identificadores.get(TipoDeIdentificador.NOSSO_NUMERO),
        )
        porta.emitir(cobranca)
        with armazenamento.transacao():
            for vinculo in do_titulo:
                armazenamento.registrar_envio(vinculo)
        emitidas.append(cobranca)
    return tuple(emitidas)


def titulos_em_aberto_fora_de_duplicidade(armazenamento: Armazenamento) -> list[Titulo]:
    cancelados = armazenamento.titulos_cancelados_na_origem()
    na_exportacao = [t for t in armazenamento.ultima_fotografia() if chave_do_titulo(t) not in cancelados]
    em_duplicidade = chaves_em_duplicidade(possiveis_duplicidades_nao_decididas(armazenamento, na_exportacao))
    saldo = saldos(na_exportacao, armazenamento.confirmacoes_em_vigor())
    return [
        replace(t, valor_centavos=em_aberto)
        for t in na_exportacao
        if chave_do_titulo(t) not in em_duplicidade and (em_aberto := saldo[chave_do_titulo(t)]) > 0
    ]


def _vinculo(titulo: Titulo, tipo: TipoDeIdentificador, identificador: str) -> VinculoDeCobranca:
    return VinculoDeCobranca(
        tipo=tipo,
        identificador=identificador,
        origem=OrigemDoIdentificador.PLATAFORMA,
        sistema_de_origem=titulo.sistema_de_origem,
        documento=titulo.documento,
        cnpj=titulo.cnpj,
        valor_centavos=titulo.valor_centavos,
        vencimento=titulo.vencimento,
    )


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="emitir-cobrancas",
        description="Emite Cobrança identificada para os Títulos em aberto dos Franqueados migrados.",
    )
    parser.add_argument("--configuracao", type=Path, default=Path("conciliacao.toml"))
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    opcoes = parser.parse_args(argumentos)

    try:
        configuracao = carregar_configuracao(opcoes.configuracao)
    except FileNotFoundError:
        print(f"Configuração não encontrada: {opcoes.configuracao}", file=sys.stderr)
        return 2
    except ConfiguracaoInvalida as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        return 2
    if configuracao.migracao is None:
        print("Sem a seção [migracao] na configuração, nenhum Franqueado é migrado; nenhuma cobrança emitida.")
        return 0

    if configuracao.migracao.boleto is None:
        print("Sem a seção [migracao.boleto], não há faixa de nosso número: os Títulos sem nosso número recebem só Pix.")
    armazenamento = Armazenamento(opcoes.estado)
    try:
        emissao = emitir_cobrancas(armazenamento, configuracao, PortaSimulada(configuracao.encargo))
    except FaixaDeNossoNumeroEsgotada as erro:
        print(f"Nenhuma cobrança emitida: {erro}.", file=sys.stderr)
        return 2
    finally:
        armazenamento.fechar()

    if emissao.data_de_referencia is None:
        print("Sem Data de referência: há conta configurada sem Extrato; nenhuma cobrança emitida.")
        return 0
    print(
        f"{len(emissao.emitidas)} Cobrança(s) identificada(s) emitida(s) pela porta simulada, "
        f"Data de referência {emissao.data_de_referencia:%d/%m/%Y}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
