from datetime import datetime
from pathlib import Path

from conciliacao.adaptadores import canal_do_credito, ler_pasta, nome_do_pagador
from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao
from conciliacao.conferencia import conferir_soma
from conciliacao.decisoes import DecisoesAplicadas, aplicar_decisoes_do_excel
from conciliacao.dominio import DataDeReferencia, DecisoesLidas, Lancamento, Natureza, Resultado, UltimaDataDaConta
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
        decisoes = (
            aplicar_decisoes_do_excel(workbook_anterior, armazenamento, configuracao.encargo, datetime.now())
            if workbook_anterior is not None and workbook_anterior.exists()
            else DecisoesAplicadas(DecisoesLidas(), ())
        )
        baixados = armazenamento.titulos_com_baixa_confirmada()
        titulos = [t for t in leitura.titulos if (t.sistema_de_origem, t.documento) not in baixados]
        identificadores, novos = armazenamento.guardar_lancamentos(leitura.lancamentos)
        lancamentos: dict[int, Lancamento] = {}
        for lancamento in leitura.lancamentos:
            if lancamento.natureza is Natureza.DEBITO:
                lancamentos[identificadores[lancamento.chave_natural]] = lancamento
        lancamentos.update(armazenamento.creditos_vivos())
        classificacoes = conciliar(
            titulos,
            lancamentos.values(),
            armazenamento.franqueados().values(),
            configuracao.encargo,
            nome_do_pagador,
            canal_do_credito,
            configuracao.limite_de_combinacoes,
            parecerista,
            armazenamento.pares_rejeitados(),
        )
        conferir_soma(list(lancamentos.values()), classificacoes)
        id_por_chave = {lancamento.chave_natural: id_ for id_, lancamento in lancamentos.items()}
        ultimas_datas = armazenamento.ultimas_datas()
        data_de_referencia = DataDeReferencia(
            tuple(
                UltimaDataDaConta(banco, conta, ultimas_datas.get((banco, conta)))
                for banco, conta in dict.fromkeys((c.banco, c.conta) for c in configuracao.contas)
            )
        )
        duplicidades = possiveis_duplicidades(leitura.titulos)
        cobranca = lista_de_cobranca(titulos, classificacoes, duplicidades, data_de_referencia.data)
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
        )
    return armazenamento.carregar_resultado(execucao)
