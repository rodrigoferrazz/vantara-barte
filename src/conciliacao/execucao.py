from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from conciliacao.acompanhamento import acompanhar_o_erp, chave_do_titulo
from conciliacao.adaptadores import canal_do_credito, ler_pasta, nome_do_pagador
from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao
from conciliacao.conferencia import conferir_soma
from conciliacao.decisoes import aplicar_decisoes
from conciliacao.dominio import (
    ChaveDoIdentificador,
    ChaveNatural,
    Classificacao,
    DataDeReferencia,
    Lancamento,
    Natureza,
    Resultado,
    RetornoDeCobranca,
    TipoDeDecisao,
    Titulo,
    UltimaDataDaConta,
    VinculoDeCobranca,
)
from conciliacao.enriquecimento import enriquecer
from conciliacao.motor import Motor, conciliar, lista_de_cobranca, possiveis_duplicidades
from conciliacao.parecerista import PareceristaDeNome


def executar_conciliacao(
    pasta: Path,
    armazenamento: Armazenamento,
    configuracao: Configuracao,
    parecerista: PareceristaDeNome,
    workbook_anterior: Path | None = None,
    motor: Motor = conciliar,
) -> Resultado:
    leitura = ler_pasta(pasta, configuracao)
    with armazenamento.transacao():
        decisoes = aplicar_decisoes(armazenamento, configuracao.encargo, datetime.now(), workbook_anterior)
        cancelados = armazenamento.titulos_cancelados_na_origem()
        acompanhamento = acompanhar_o_erp(
            atuais=leitura.titulos,
            anteriores=armazenamento.fotografia_anterior(leitura.sistemas_exportados),
            confirmacoes=armazenamento.confirmacoes_em_vigor(),
            revertidas=armazenamento.confirmacoes_revertidas(),
            propostos=armazenamento.titulos_propostos_na_ultima_execucao(),
            cancelados=cancelados,
        )
        for divergencia in acompanhamento.divergencias:
            armazenamento.registrar_divergencia(divergencia.confirmacao.decisao, divergencia.baixado, divergencia.explicacao)
        na_exportacao = [t for t in leitura.titulos if chave_do_titulo(t) not in cancelados]
        originais = {chave_do_titulo(t): t for t in na_exportacao}
        titulos = [
            replace(t, valor_centavos=saldo)
            for t in na_exportacao
            if (saldo := acompanhamento.saldos[chave_do_titulo(t)]) > 0
        ]
        identificadores, novos = armazenamento.guardar_lancamentos(leitura.lancamentos)
        lancamentos: dict[int, Lancamento] = {}
        for lancamento in leitura.lancamentos:
            if lancamento.natureza is Natureza.DEBITO:
                lancamentos[identificadores[lancamento.chave_natural]] = lancamento
        lancamentos.update(armazenamento.creditos_vivos())
        retornos, vinculos = _cobranca_identificada(armazenamento, configuracao, leitura.retornos, lancamentos)
        pelo_saldo = motor(
            titulos,
            lancamentos.values(),
            armazenamento.franqueados().values(),
            configuracao.encargo,
            nome_do_pagador,
            canal_do_credito,
            configuracao.limite_de_combinacoes,
            parecerista,
            armazenamento.pares_rejeitados(),
            armazenamento.pagadores_conhecidos(),
            antecipacoes=armazenamento.classificados_como(TipoDeDecisao.ANTECIPACAO),
            fontes_nao_integradas=armazenamento.classificados_como(TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA),
            divergencias=armazenamento.divergencias(),
            retornos=retornos,
            vinculos=vinculos,
        )
        classificacoes = [_com_titulos_da_exportacao(c, originais) for c in pelo_saldo]
        conferir_soma(list(lancamentos.values()), classificacoes)
        id_por_chave = {lancamento.chave_natural: id_ for id_, lancamento in lancamentos.items()}
        data_de_referencia = calcular_data_de_referencia(armazenamento, configuracao)
        decididas = armazenamento.duplicidades_decididas()
        duplicidades = [d for d in possiveis_duplicidades(na_exportacao) if d.chave not in decididas]
        cobranca = [
            replace(na_cobranca, titulo=originais[chave_do_titulo(na_cobranca.titulo)])
            for na_cobranca in lista_de_cobranca(titulos, pelo_saldo, duplicidades, data_de_referencia.data)
        ]
        execucao = armazenamento.registrar_execucao(
            lancamentos_novos=novos,
            arquivos_lidos=leitura.arquivos_lidos,
            arquivos_recusados=leitura.arquivos_recusados,
            titulos=leitura.titulos,
            classificacoes=[(id_por_chave[c.lancamento.chave_natural], c) for c in classificacoes],
            duplicidades=duplicidades,
            data_de_referencia=data_de_referencia,
            cobranca=[
                (titulo, tuple(id_por_chave[c.chave_natural] for c in titulo.creditos_candidatos)) for titulo in cobranca
            ],
            decisoes_aplicadas=decisoes.registradas,
            avisos_das_decisoes=decisoes.lidas.nao_aplicadas,
            limite_de_queda=configuracao.limite_de_queda,
            decisoes_de_duplicidade_aplicadas=decisoes.duplicidades,
            sistemas_exportados=leitura.sistemas_exportados,
            acompanhamento_do_erp=acompanhamento.situacoes,
            decisoes_da_tela_lidas=decisoes.da_tela,
            conflitos_das_decisoes=decisoes.lidas.conflitos,
        )
    return armazenamento.carregar_resultado(execucao)


def calcular_data_de_referencia(armazenamento: Armazenamento, configuracao: Configuracao) -> DataDeReferencia:
    ultimas_datas = armazenamento.ultimas_datas()
    return DataDeReferencia(
        tuple(
            UltimaDataDaConta(banco, conta, ultimas_datas.get((banco, conta)))
            for banco, conta in dict.fromkeys((c.banco, c.conta) for c in configuracao.contas)
        )
    )


def _cobranca_identificada(
    armazenamento: Armazenamento,
    configuracao: Configuracao,
    lidos: Iterable[RetornoDeCobranca],
    lancamentos: Mapping[int, Lancamento],
) -> tuple[dict[ChaveNatural, RetornoDeCobranca], dict[ChaveDoIdentificador, VinculoDeCobranca]]:
    if configuracao.migracao is None:
        return {}, {}
    armazenamento.guardar_retornos(lidos)
    enriquecidos = armazenamento.retornos_dos_creditos()
    id_por_chave = {lancamento.chave_natural: id_ for id_, lancamento in lancamentos.items()}
    livres = [lancamento for lancamento in lancamentos.values() if lancamento.chave_natural not in enriquecidos]
    for retorno, credito in enriquecer(armazenamento.retornos_sem_credito(), livres):
        armazenamento.registrar_enriquecimento(retorno, id_por_chave[credito.chave_natural])
    vinculos = {vinculo.chave: vinculo for vinculo in armazenamento.vinculos_de_cobranca()}
    return armazenamento.retornos_dos_creditos(), vinculos


def _com_titulos_da_exportacao(
    classificacao: Classificacao, originais: Mapping[tuple[str, str], Titulo]
) -> Classificacao:
    return replace(
        classificacao,
        titulos=tuple(originais[chave_do_titulo(t)] for t in classificacao.titulos),
        citados=tuple(originais[chave_do_titulo(t)] for t in classificacao.citados),
    )
