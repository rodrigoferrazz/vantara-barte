from pathlib import Path

from conciliacao.adaptadores import ler_pasta
from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao
from conciliacao.conferencia import conferir_soma
from conciliacao.dominio import Lancamento, Natureza, Resultado
from conciliacao.motor import conciliar


def executar_conciliacao(pasta: Path, armazenamento: Armazenamento, configuracao: Configuracao) -> Resultado:
    leitura = ler_pasta(pasta, configuracao)
    with armazenamento.transacao():
        identificadores, novos = armazenamento.guardar_lancamentos(leitura.lancamentos)
        lancamentos: dict[int, Lancamento] = {}
        for lancamento in leitura.lancamentos:
            if lancamento.natureza is Natureza.DEBITO:
                lancamentos[identificadores[lancamento.chave_natural]] = lancamento
        lancamentos.update(armazenamento.creditos_guardados())
        classificacoes = conciliar(leitura.titulos, lancamentos.values(), armazenamento.franqueados_conhecidos())
        conferir_soma(list(lancamentos.values()), classificacoes)
        id_por_chave = {lancamento.chave_natural: id_ for id_, lancamento in lancamentos.items()}
        execucao = armazenamento.registrar_execucao(
            lancamentos_novos=novos,
            arquivos_lidos=leitura.arquivos_lidos,
            arquivos_recusados=leitura.arquivos_recusados,
            titulos=leitura.titulos,
            classificacoes=[(id_por_chave[c.lancamento.chave_natural], c) for c in classificacoes],
        )
    return armazenamento.carregar_resultado(execucao)
