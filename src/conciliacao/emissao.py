import argparse
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from conciliacao.acompanhamento import chave_do_titulo, saldos
from conciliacao.armazenamento import Armazenamento
from conciliacao.calendario import vencimento_efetivo
from conciliacao.configuracao import Configuracao, ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import OrigemDoIdentificador, TipoDeIdentificador, Titulo, VinculoDeCobranca
from conciliacao.execucao import calcular_data_de_referencia, possiveis_duplicidades_nao_decididas
from conciliacao.identificadores import gerar_txid
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
    with armazenamento.transacao():
        vinculos = {
            (v.sistema_de_origem, v.documento): v
            for v in armazenamento.vinculos_de_cobranca()
            if v.tipo is TipoDeIdentificador.TXID
        }
        enviados = armazenamento.vinculos_enviados()
        gerados = armazenamento.identificadores_gerados(TipoDeIdentificador.TXID)
        a_enviar = []
        for titulo in _titulos_em_aberto_fora_de_duplicidade(armazenamento):
            if titulo.franqueado not in migracao.franqueados or vencimento_efetivo(titulo.vencimento) < referencia:
                continue
            vinculo = vinculos.get(chave_do_titulo(titulo))
            if vinculo is None:
                gerados += 1
                vinculo = _vinculo(titulo, gerar_txid(gerados))
                armazenamento.registrar_vinculo(vinculo)
            if vinculo.chave not in enviados:
                a_enviar.append(vinculo)
    emitidas = []
    for vinculo in a_enviar:
        cobranca = CobrancaIdentificada(
            sistema_de_origem=vinculo.sistema_de_origem,
            documento=vinculo.documento,
            valor_centavos=vinculo.valor_centavos,
            vencimento=vinculo.vencimento,
            cnpj=vinculo.cnpj,
            txid=vinculo.identificador,
        )
        porta.emitir(cobranca)
        with armazenamento.transacao():
            armazenamento.registrar_envio(vinculo)
        emitidas.append(cobranca)
    return Emissao(referencia, tuple(emitidas))


def _titulos_em_aberto_fora_de_duplicidade(armazenamento: Armazenamento) -> list[Titulo]:
    cancelados = armazenamento.titulos_cancelados_na_origem()
    na_exportacao = [t for t in armazenamento.ultima_fotografia() if chave_do_titulo(t) not in cancelados]
    em_duplicidade = chaves_em_duplicidade(possiveis_duplicidades_nao_decididas(armazenamento, na_exportacao))
    saldo = saldos(na_exportacao, armazenamento.confirmacoes_em_vigor())
    return [
        replace(t, valor_centavos=em_aberto)
        for t in na_exportacao
        if chave_do_titulo(t) not in em_duplicidade and (em_aberto := saldo[chave_do_titulo(t)]) > 0
    ]


def _vinculo(titulo: Titulo, txid: str) -> VinculoDeCobranca:
    return VinculoDeCobranca(
        tipo=TipoDeIdentificador.TXID,
        identificador=txid,
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

    armazenamento = Armazenamento(opcoes.estado)
    try:
        emissao = emitir_cobrancas(armazenamento, configuracao, PortaSimulada())
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
