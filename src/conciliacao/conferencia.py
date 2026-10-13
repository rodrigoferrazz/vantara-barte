from collections import Counter
from collections.abc import Sequence

from conciliacao.dominio import Classificacao, Destino, Lancamento
from conciliacao.normalizacao import formatar_reais


class ConferenciaDeSomaFalhou(Exception):
    pass


def conferir_soma(lancamentos: Sequence[Lancamento], classificacoes: Sequence[Classificacao]) -> None:
    do_extrato = Counter(lancamento.chave_natural for lancamento in lancamentos)
    classificados = Counter(classificacao.lancamento.chave_natural for classificacao in classificacoes)
    soma_do_extrato = sum(lancamento.valor_centavos for lancamento in lancamentos)
    soma_por_destino = {
        destino: sum(c.lancamento.valor_centavos for c in classificacoes if c.destino is destino) for destino in Destino
    }
    soma_classificada = sum(soma_por_destino.values())
    if do_extrato == classificados and soma_do_extrato == soma_classificada:
        return
    sem_destino = (do_extrato - classificados).total()
    a_mais = (classificados - do_extrato).total()
    partes = " + ".join(f"{destino} {formatar_reais(soma)}" for destino, soma in soma_por_destino.items())
    raise ConferenciaDeSomaFalhou(
        f"Conferência de soma não fechou: os lançamentos do Extrato somam {formatar_reais(soma_do_extrato)}, "
        f"mas {partes} = {formatar_reais(soma_classificada)}; "
        f"{sem_destino} lançamento(s) sem destino e {a_mais} classificado(s) a mais. "
        "A execução parou sem gerar saídas."
    )
