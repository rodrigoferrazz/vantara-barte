from html import escape

from conciliacao.demonstracao import SituacaoDaDemonstracao
from conciliacao.pagina import Estado, Visao, aviso, cabecalho_da_pagina, chip, documento


def renderizar_demonstracao(situacao: SituacaoDaDemonstracao, ha_execucao: bool) -> str:
    titulo = "Demonstração"
    pagamentos = situacao.pagamentos
    emitidas = len(situacao.cobrancas)
    emitir = _passo(
        1,
        "Emitir cobranças",
        "Considera todos os franqueados da última conciliação como migrados e emite, pela porta simulada, um Pix "
        "com txid para cada título em aberto, e um boleto com nosso número quando o título não tem. Títulos já "
        "vencidos também entram, como se a cobrança tivesse saído antes do vencimento. As cobranças aparecem na "
        "aba Emissão.",
        _botao("/demonstracao/emitir", "Emitir cobranças", "emitir-cobrancas", ha_execucao and pagamentos is None),
        feito=bool(emitidas),
        resultado=(
            f'<p class="suave">{emitidas} cobrança(s) emitida(s). '
            f'<a href="{Visao.EMISSAO.value}">Ver na Emissão</a></p>'
            if emitidas
            else ""
        ),
    )
    simular = _passo(
        2,
        "Simular pagamentos",
        "Gera o extrato do banco e os retornos de cobrança como se os franqueados pagassem em dia pelo Pix ou "
        "boleto emitido, e grava os arquivos na entrada da Analista. Título que já tem um crédito do extrato na "
        "última conciliação não é pago de novo.",
        _botao("/demonstracao/simular", "Simular pagamentos", "simular-pagamentos", bool(emitidas) and pagamentos is None),
        feito=pagamentos is not None,
        resultado=_depois_dos_pagamentos(pagamentos.arquivos, pagamentos.sem_pagamento) if pagamentos else "",
    )
    zerar = _passo(
        3,
        "Zerar demonstração",
        "Volta o estado, os arquivos enviados e o Excel ao que eram antes da primeira emissão.",
        _botao("/demonstracao/zerar", "Zerar demonstração", "zerar-demonstracao", situacao.ativa),
    )
    corpo = (
        cabecalho_da_pagina(titulo, "A Cobrança Endereçada de ponta a ponta, sobre a última conciliação.")
        + '<div class="simulacao" id="marca-de-simulacao"><strong>Simulação</strong>'
        "Nenhuma cobrança real é emitida e nenhum pagamento real acontece. A emissão, a porta de cobrança e os "
        "pagamentos são simulados; as regras da conciliação são as de sempre.</div>"
        + f'<section id="demonstracao"><div class="passos">{emitir}{simular}{zerar}</div></section>'
    )
    return documento(titulo, corpo, Visao.DEMONSTRACAO)


def _passo(ordem: int, titulo: str, explicacao: str, botao: str, feito: bool = False, resultado: str = "") -> str:
    situacao = chip("Feito", Estado.OK) if feito else ""
    return (
        f'<article class="cartao passo{" feito" if feito else ""}"><span class="ordem">{ordem}</span>'
        f"<div><h2>{escape(titulo)}{situacao}</h2>"
        f'<p class="explicacao-do-passo">{escape(explicacao)}</p>{botao}{resultado}</div></article>'
    )


def _botao(acao: str, rotulo: str, identificador: str, habilitado: bool) -> str:
    desabilitado = "" if habilitado else " disabled"
    return (
        f'<form method="post" action="{acao}" id="{identificador}">'
        f'<button class="primario" type="submit"{desabilitado}>{escape(rotulo)}</button></form>'
    )


def _depois_dos_pagamentos(arquivos: tuple[str, ...], sem_pagamento: tuple[str, ...]) -> str:
    texto = "Extrato e retornos de cobrança gravados na entrada da Analista."
    if sem_pagamento:
        texto += (
            f" {len(sem_pagamento)} cobrança(s) não foram pagas porque o título já tem um crédito do extrato "
            f"na última conciliação: {', '.join(sem_pagamento)}."
        )
    ver = (
        f'<div class="espaco botoes"><a class="botao primario" href="{Visao.ANALISTA.value}#arquivos" '
        'id="ver-na-conciliacao">Ver na Conciliação Assistida</a>'
        '<span class="suave">Lá, Conciliar leva os pagamentos à Lista de baixa já resolvidos.</span></div>'
    )
    return '<div class="espaco">' + aviso("Pagamentos simulados", texto, Estado.OK, "pagamentos-simulados", arquivos) + "</div>" + ver
