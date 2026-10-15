from collections.abc import Sequence
from html import escape

from conciliacao.demonstracao import CobrancaEmitida
from conciliacao.normalizacao import formatar_reais
from conciliacao.pagina import Estado, Numero, Visao, cabecalho_da_pagina, chip, documento, numeros, secao, tabela, vazia


def renderizar_emissao(cobrancas: Sequence[CobrancaEmitida], simulacao: bool) -> str:
    titulo = "Emissão"
    corpo = cabecalho_da_pagina(
        titulo,
        "Cada fatura sai com um endereço próprio: o txid do Pix e, quando há boleto, o nosso número. "
        "O pagamento volta dizendo qual fatura paga, sem depender do nome no extrato.",
    )
    if simulacao:
        corpo += (
            '<div class="simulacao" id="marca-de-simulacao"><strong>Simulação</strong>'
            "Estas cobranças foram emitidas pela demonstração, numa porta de cobrança simulada.</div>"
        )
    if not cobrancas:
        return documento(
            titulo,
            corpo
            + secao(
                "Cobranças emitidas",
                "secao-cobrancas-emitidas",
                vazia(
                    "Nenhuma cobrança emitida. Na aba Demonstração, Emitir cobranças emite pela porta simulada.",
                    "sem-cobrancas-emitidas",
                ),
            ),
            Visao.EMISSAO,
        )
    pagas = [c for c in cobrancas if c.paga_em is not None]
    corpo += (
        '<div class="espaco">'
        + numeros(
            Numero(
                "Emitidas",
                str(len(cobrancas)),
                formatar_reais(sum(c.valor_centavos for c in cobrancas)),
                identificador="total-emitidas",
            ),
            Numero(
                "Pagas",
                str(len(pagas)),
                f"{formatar_reais(sum(c.valor_centavos for c in pagas))} com retorno ligado",
                Estado.OK if pagas else Estado.NEUTRO,
                "total-pagas",
            ),
        )
        + "</div>"
        + secao(
            "Cobranças emitidas",
            "secao-cobrancas-emitidas",
            tabela(
                ("Franqueado", "Título", "Valor", "Vencimento", "txid", "Nosso número", "Situação"),
                [_linha(cobranca) for cobranca in cobrancas],
                "cobrancas-emitidas",
                numericas=(2,),
            ),
            nota="Paga quando o retorno do Pix ou do boleto já foi ligado a um crédito do extrato na conciliação.",
        )
    )
    return documento(titulo, corpo, Visao.EMISSAO)


def _linha(cobranca: CobrancaEmitida) -> tuple[str, ...]:
    situacao = (
        chip(f"Paga em {cobranca.paga_em:%d/%m/%Y}", Estado.OK)
        if cobranca.paga_em is not None
        else chip("Emitida", Estado.PENDENTE)
    )
    return (
        f'<span class="forte">{escape(cobranca.franqueado)}</span>',
        f'{escape(cobranca.documento)} <span class="suave">({escape(cobranca.sistema_de_origem)})</span>',
        formatar_reais(cobranca.valor_centavos),
        f'<span class="sem-quebra">{cobranca.vencimento:%d/%m/%Y}</span>',
        f'<span class="identificador">{escape(cobranca.txid or "-")}</span>',
        f'<span class="identificador sem-quebra">{escape(cobranca.nosso_numero or "-")}</span>',
        situacao,
    )
