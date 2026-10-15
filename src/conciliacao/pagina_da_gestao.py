from collections.abc import Sequence
from fractions import Fraction
from html import escape

from conciliacao.dominio import CausaRaiz, GrupoDaCausaRaiz, Resultado
from conciliacao.normalizacao import formatar_percentual, formatar_reais
from conciliacao.pagina import (
    Estado,
    Numero,
    Visao,
    cabecalho_da_pagina,
    detalhes,
    documento,
    grafico_de_barras,
    numeros,
    secao,
    tabela,
    vazia,
)

def renderizar_gestao(resultado: Resultado | None) -> str:
    titulo = "Gestão"
    corpo = cabecalho_da_pagina(titulo, _subtitulo(resultado)) + _hoje(resultado) + _causa_raiz(resultado)
    return documento(titulo, corpo, Visao.GESTAO)


def _subtitulo(resultado: Resultado | None) -> str:
    if resultado is None:
        return ""
    referencia = resultado.resumo.data_de_referencia.data
    return f"Conciliação da execução {resultado.resumo.execucao}" + (
        f", extrato até {referencia:%d/%m/%Y}" if referencia else ""
    )


def _hoje(resultado: Resultado | None) -> str:
    if resultado is None:
        return secao(
            "Resolvido sozinho",
            "resolvido-sozinho",
            vazia("Não há execução registrada. A analista concilia pela tela de Conciliação.", "sem-execucao"),
        )
    parte = resultado.resumo.parte_automatica
    fila = resultado.resumo.parte_automatica.creditos.quantidade - parte.resolvidos.quantidade
    valor_da_fila = parte.creditos.valor_centavos - parte.resolvidos.valor_centavos
    return secao(
        "Resolvido sozinho",
        "resolvido-sozinho",
        numeros(
            Numero(
                "Créditos resolvidos sozinhos",
                _percentual_de(parte.percentual_da_quantidade) or "-",
                f"{parte.resolvidos.quantidade} de {parte.creditos.quantidade} Créditos",
                Estado.OK,
                "resolvido-em-quantidade",
            ),
            Numero(
                "Valor resolvido sozinho",
                _percentual_de(parte.percentual_do_valor) or "-",
                f"{formatar_reais(parte.resolvidos.valor_centavos)} de {formatar_reais(parte.creditos.valor_centavos)}",
                Estado.OK,
                "resolvido-em-valor",
            ),
            Numero(
                "Precisaram da analista",
                str(fila),
                f"{formatar_reais(valor_da_fila)} na Fila de exceções",
                Estado.PENDENTE if fila else Estado.OK,
                "precisaram-da-analista",
            ),
        ),
        nota="Parte dos Créditos de franqueados que fechou pelas regras, sem investigação.",
    )


def _causa_raiz(resultado: Resultado | None) -> str:
    if resultado is None:
        return ""
    causa_raiz = resultado.causa_raiz
    com_credito = sorted((g for g in causa_raiz.por_motivo if g.quantidade), key=lambda g: -g.quantidade)
    grafico = (
        grafico_de_barras(
            "grafico-causa-raiz",
            com_credito,
            lambda g: g.quantidade,
            lambda g: f"{g.quantidade} Crédito(s), {formatar_reais(g.valor_centavos)}",
        )
        if com_credito
        else vazia("Nenhum Crédito ficou sem identificação.")
    )
    agregacoes = (
        ("Por Motivo de não identificação", "causa-raiz-por-motivo", causa_raiz.por_motivo),
        ("Por Franqueado", "causa-raiz-por-franqueado", causa_raiz.por_franqueado),
        ("Por banco", "causa-raiz-por-banco", causa_raiz.por_banco),
        ("Por canal", "causa-raiz-por-canal", causa_raiz.por_canal),
    )
    tabelas = "".join(
        f"<h3>{escape(titulo)}</h3>" + _agregacao(identificador, causa_raiz, grupos)
        for titulo, identificador, grupos in agregacoes
    )
    return secao(
        "Por que os Créditos não se identificam",
        "causa-raiz",
        f'<div class="cartao com-folga">{grafico}</div>' + detalhes("Ver por franqueado, banco e canal", tabelas),
        nota=(
            f"{causa_raiz.quantidade} Crédito(s), {formatar_reais(causa_raiz.valor_centavos)}, na Fila de exceções "
            "e Conciliados fora, por Motivo de não identificação."
        ),
    )


def _agregacao(identificador: str, causa_raiz: CausaRaiz, grupos: Sequence[GrupoDaCausaRaiz]) -> str:
    total = GrupoDaCausaRaiz("Total", causa_raiz.quantidade, causa_raiz.valor_centavos)
    linhas = [
        [
            escape(celula)
            for celula in (
                grupo.nome,
                str(grupo.quantidade),
                _percentual(causa_raiz.fracao_da_quantidade(grupo)),
                formatar_reais(grupo.valor_centavos),
                _percentual(causa_raiz.fracao_do_valor(grupo)),
            )
        ]
        for grupo in (*grupos, total)
    ]
    return tabela(
        ("Grupo", "Quantidade", "% quantidade", "Valor", "% valor"), linhas, identificador, (1, 2, 3, 4), compacta=True
    )


def _percentual(fracao: Fraction | None) -> str:
    return formatar_percentual(fracao * 100) if fracao is not None else ""


def _percentual_de(percentual: Fraction | None) -> str:
    return formatar_percentual(percentual) if percentual is not None else ""
