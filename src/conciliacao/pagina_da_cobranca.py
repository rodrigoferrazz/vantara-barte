from datetime import date
from html import escape

from conciliacao.calendario import vencimento_efetivo
from conciliacao.dominio import Resultado, TituloNaCobranca
from conciliacao.normalizacao import formatar_reais
from conciliacao.pagina import Estado, Numero, Visao, cabecalho_da_pagina, documento, numeros, secao, tabela, vazia


def renderizar_cobranca(resultado: Resultado | None) -> str:
    titulo = "Cobrança"
    if resultado is None:
        return documento(
            titulo,
            cabecalho_da_pagina(titulo)
            + secao("Quem cobrar", "lista-de-cobranca", vazia("Não há execução registrada; a lista aparece depois da primeira conciliação.", "sem-execucao")),
            Visao.COBRANCA,
        )
    referencia = resultado.resumo.data_de_referencia.data
    if referencia is None:
        subtitulo = "Sem data de referência: falta o extrato de alguma conta, então ninguém entra na cobrança."
    else:
        subtitulo = f"Vencidos até {referencia:%d/%m/%Y}, a data do último extrato."
    a_cobrar = sorted(resultado.lista_de_cobranca, key=lambda t: (vencimento_efetivo(t.titulo.vencimento), t.titulo.documento))
    em_analise = resultado.em_analise
    corpo = (
        cabecalho_da_pagina(titulo, subtitulo)
        + '<div class="espaco">'
        + numeros(
            Numero(
                "A cobrar",
                str(len(a_cobrar)),
                f"{formatar_reais(sum(t.saldo_centavos for t in a_cobrar))} em aberto",
                Estado.PROBLEMA if a_cobrar else Estado.OK,
                "total-a-cobrar",
            ),
            Numero(
                "Não cobrar ainda",
                str(len(em_analise)),
                f"{formatar_reais(sum(t.saldo_centavos for t in em_analise))} com pagamento em análise",
                Estado.PENDENTE if em_analise else Estado.NEUTRO,
                "total-em-analise",
            ),
        )
        + "</div>"
        + secao(
            "Quem cobrar",
            "lista-de-cobranca",
            tabela(
                ("Franqueado", "Título", "Valor", "Vencimento", "Dias de atraso"),
                [_a_cobrar(t, referencia) for t in a_cobrar],
                "titulos-a-cobrar",
                numericas=(2, 4),
                vazia_com="Ninguém pra cobrar.",
            ),
            nota="Títulos vencidos, com saldo em aberto e sem nenhum pagamento que possa ser deles.",
        )
        + secao(
            "Não cobrar ainda",
            "em-analise",
            tabela(
                ("Franqueado", "Título", "Valor", "Vencimento", "Por quê"),
                [_em_analise(t, resultado) for t in em_analise],
                "titulos-em-analise",
                numericas=(2,),
                vazia_com="Nenhum título em análise.",
            ),
            nota="Há um pagamento que pode ser deste título e a conciliação ainda está analisando.",
        )
    )
    return documento(titulo, corpo, Visao.COBRANCA)


def _a_cobrar(na_cobranca: TituloNaCobranca, referencia: date | None) -> tuple[str, ...]:
    titulo = na_cobranca.titulo
    atraso = (referencia - vencimento_efetivo(titulo.vencimento)).days if referencia is not None else None
    return (
        f'<span class="forte">{escape(titulo.nome_do_franqueado)}</span>',
        f"{escape(titulo.documento)} <span class=\"suave\">({escape(titulo.sistema_de_origem)})</span>",
        formatar_reais(na_cobranca.saldo_centavos),
        f"{titulo.vencimento:%d/%m/%Y}",
        "" if atraso is None else str(atraso),
    )


def _em_analise(na_cobranca: TituloNaCobranca, resultado: Resultado) -> tuple[str, ...]:
    titulo = na_cobranca.titulo
    return (
        f'<span class="forte">{escape(titulo.nome_do_franqueado)}</span>',
        f"{escape(titulo.documento)} <span class=\"suave\">({escape(titulo.sistema_de_origem)})</span>",
        formatar_reais(na_cobranca.saldo_centavos),
        f"{titulo.vencimento:%d/%m/%Y}",
        escape(_por_que_nao_cobrar(na_cobranca, resultado)),
    )


def _por_que_nao_cobrar(na_cobranca: TituloNaCobranca, resultado: Resultado) -> str:
    return "; ".join(
        f"Pagamento de {formatar_reais(credito.valor_centavos)} em {credito.data:%d/%m} em análise"
        + (f" ({item.motivo.value})" if (item := resultado.item_do_lancamento(credito)).motivo else "")
        for credito in na_cobranca.creditos_candidatos
    )
