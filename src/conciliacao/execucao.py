from collections.abc import Mapping
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
    ChaveNatural,
    Classificacao,
    DataDeReferencia,
    Destino,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    Resultado,
    TipoDeDecisao,
    Titulo,
    UltimaDataDaConta,
)
from conciliacao.motor import conciliar, lista_de_cobranca, possiveis_duplicidades
from conciliacao.parecerista import PareceristaDeNome


def executar_conciliacao(
    pasta: Path,
    armazenamento: Armazenamento,
    configuracao: Configuracao,
    parecerista: PareceristaDeNome,
    workbook_anterior: Path | None = None,
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
        pelo_saldo = _com_divergencias(
            _com_classificacoes_da_analista(
                conciliar(
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
                ),
                armazenamento.classificados_como(TipoDeDecisao.ANTECIPACAO),
                armazenamento.classificados_como(TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA),
            ),
            armazenamento.divergencias(),
        )
        classificacoes = [_com_titulos_da_exportacao(c, originais) for c in pelo_saldo]
        conferir_soma(list(lancamentos.values()), classificacoes)
        id_por_chave = {lancamento.chave_natural: id_ for id_, lancamento in lancamentos.items()}
        ultimas_datas = armazenamento.ultimas_datas()
        data_de_referencia = DataDeReferencia(
            tuple(
                UltimaDataDaConta(banco, conta, ultimas_datas.get((banco, conta)))
                for banco, conta in dict.fromkeys((c.banco, c.conta) for c in configuracao.contas)
            )
        )
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


def _com_classificacoes_da_analista(
    classificacoes: list[Classificacao],
    antecipacoes: Mapping[ChaveNatural, datetime],
    fontes_nao_integradas: Mapping[ChaveNatural, datetime],
) -> list[Classificacao]:
    return [
        _como_fonte_nao_integrada(_como_antecipacao(c, antecipacoes), fontes_nao_integradas) for c in classificacoes
    ]


def _como_antecipacao(c: Classificacao, antecipacoes: Mapping[ChaveNatural, datetime]) -> Classificacao:
    momento = antecipacoes.get(c.lancamento.chave_natural)
    if momento is None:
        return c
    return replace(
        c,
        explicacao=f"{c.explicacao} Classificado pela Analista como {TipoDeDecisao.ANTECIPACAO.value} "
        f"em {momento:%d/%m/%Y}; o Crédito continua vivo e é retentado a cada nova importação.",
    )


def _como_fonte_nao_integrada(c: Classificacao, fontes: Mapping[ChaveNatural, datetime]) -> Classificacao:
    momento = fontes.get(c.lancamento.chave_natural)
    if momento is None or c.destino is not Destino.FILA_DE_EXCECOES:
        return c
    fonte = MotivoDeNaoIdentificacao.POSSIVEL_FONTE_NAO_INTEGRADA
    return replace(
        c,
        motivo=fonte,
        explicacao=f"{c.explicacao} Classificado pela Analista como {fonte.value} em {momento:%d/%m/%Y} "
        f"(o motor apontava '{c.motivo}'); o Crédito continua vivo e é retentado a cada nova importação.",
    )


def _com_divergencias(
    classificacoes: list[Classificacao], divergencias: Mapping[ChaveNatural, list[str]]
) -> list[Classificacao]:
    com_divergencia = []
    for c in classificacoes:
        explicacoes = divergencias.get(c.lancamento.chave_natural)
        if not explicacoes:
            com_divergencia.append(c)
            continue
        explicacao = " ".join((c.explicacao, *explicacoes))
        if c.destino is Destino.LISTA_DE_BAIXA:
            com_divergencia.append(
                replace(
                    c,
                    destino=Destino.FILA_DE_EXCECOES,
                    explicacao=explicacao,
                    motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
                    regra=None,
                )
            )
        else:
            com_divergencia.append(replace(c, explicacao=explicacao))
    return com_divergencia


def _com_titulos_da_exportacao(
    classificacao: Classificacao, originais: Mapping[tuple[str, str], Titulo]
) -> Classificacao:
    return replace(
        classificacao,
        titulos=tuple(originais[chave_do_titulo(t)] for t in classificacao.titulos),
        citados=tuple(originais[chave_do_titulo(t)] for t in classificacao.citados),
    )
