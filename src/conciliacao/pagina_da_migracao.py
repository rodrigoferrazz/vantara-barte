from collections.abc import Callable, Sequence
from decimal import Decimal
from fractions import Fraction
from html import escape

from conciliacao.dominio import (
    GrupoDaCausaRaiz,
    MotivoDeNaoIdentificacao,
    NumerosDoCenario,
    PorQueFicaSolto,
    RankingDeMigracao,
    RelatorioDeImpacto,
    TotalDoDestino,
    ValorDaPremissa,
)
from conciliacao.impacto import EXPLICACAO_DAS_ONDAS, EXPLICACAO_DO_SEM_FRANQUEADO, RAZOES_DO_RESUMO
from conciliacao.normalizacao import formatar_adesao, formatar_percentual, formatar_reais
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

_RANKING_VISIVEL = 10


def renderizar_migracao(relatorio: RelatorioDeImpacto | None) -> str:
    titulo = "Migração"
    subtitulo = f"Análise de impacto de {relatorio.momento:%d/%m/%Y %H:%M}" if relatorio is not None else ""
    return documento(titulo, cabecalho_da_pagina(titulo, subtitulo) + _impacto(relatorio), Visao.MIGRACAO)


def _impacto(relatorio: RelatorioDeImpacto | None) -> str:
    if relatorio is None:
        return secao(
            "Antes e depois",
            "secao-antes-e-depois",
            vazia(
                "Não há análise de impacto registrada. Rode o comando analisar-impacto sobre uma pasta base.",
                "sem-analise",
            ),
        )
    cenarios = (relatorio.antes, *relatorio.todos_migrados)
    return (
        _antes_e_depois(relatorio, cenarios)
        + _ondas(relatorio)
        + _ranking(relatorio.ranking)
        + secao(
            "Premissas",
            "secao-premissas",
            detalhes("Ver as premissas da análise", _premissas(relatorio)),
        )
    )


def _antes_e_depois(relatorio: RelatorioDeImpacto, cenarios: Sequence[NumerosDoCenario]) -> str:
    antes = relatorio.antes.fila_de_excecoes
    automatico_antes = _percentual_de(relatorio.antes.parte_automatica.percentual_da_quantidade)
    destaques = numeros(
        Numero(
            "Fila antes",
            str(antes.quantidade),
            f"{formatar_reais(antes.valor_centavos)} · {automatico_antes} sozinho",
            Estado.PENDENTE,
            "fila-antes",
        ),
        *(
            Numero(
                f"Com {c.nome.lower()}",
                str(c.fila_de_excecoes.quantidade),
                f"{_queda(antes.quantidade, c.fila_de_excecoes.quantidade)} · "
                f"{_percentual_de(c.parte_automatica.percentual_da_quantidade)} sozinho",
                Estado.OK,
                f"fila-adesao-{posicao}",
            )
            for posicao, c in enumerate(relatorio.todos_migrados)
        ),
    )
    grafico = _grafico_da_fila("grafico-fila-por-adesao", [(_nome_do_cenario(c), c) for c in cenarios])
    completo = (
        _tabela_antes_e_depois(cenarios)
        + "<h3>Créditos do antes que ficam soltos no depois, por razão</h3>"
        + _soltos_por_razao(relatorio.todos_migrados)
        + "<h3>Fila por Motivo de não identificação</h3>"
        + _fila_por_motivo(cenarios)
    )
    return secao(
        "Antes e depois",
        "secao-antes-e-depois",
        destaques
        + f'<div class="cartao com-folga espaco"><h3 class="sem-margem">Créditos na Fila por Adesão</h3>{grafico}</div>'
        + detalhes("Ver os números completos", completo),
        nota=(
            "Com todos os franqueados migrados, quanto a Fila cai se esta parte dos pagamentos chegar com Pix ou "
            "boleto identificado (Adesão). O dinheiro é o mesmo do antes."
        ),
    )


def _queda(antes: int, depois: int) -> str:
    if not antes:
        return "sem Fila no antes"
    return f"{formatar_percentual(Fraction(100 * (antes - depois), antes))} a menos"


def _nome_do_cenario(numeros_do_cenario: NumerosDoCenario) -> str:
    return "Antes" if numeros_do_cenario.adesao is None else numeros_do_cenario.nome


def _tabela_antes_e_depois(cenarios: Sequence[NumerosDoCenario]) -> str:
    medidas: tuple[tuple[str, Callable[[NumerosDoCenario], str]], ...] = (
        ("Créditos identificados", lambda c: str(c.identificados.quantidade)),
        ("Valor identificado", lambda c: formatar_reais(c.identificados.valor_centavos)),
        ("Créditos soltos", lambda c: str(c.soltos.quantidade)),
        ("Valor solto", lambda c: formatar_reais(c.soltos.valor_centavos)),
        ("Não identificáveis pelo valor", lambda c: _nao_identificaveis(c, lambda t: str(t.quantidade))),
        (
            "Valor não identificável pelo valor",
            lambda c: _nao_identificaveis(c, lambda t: formatar_reais(t.valor_centavos)),
        ),
        ("Créditos na Fila", lambda c: str(c.fila_de_excecoes.quantidade)),
        ("Valor na Fila", lambda c: formatar_reais(c.fila_de_excecoes.valor_centavos)),
        ("% resolvido sozinho (quantidade)", lambda c: _percentual_de(c.parte_automatica.percentual_da_quantidade)),
        ("% resolvido sozinho (valor)", lambda c: _percentual_de(c.parte_automatica.percentual_do_valor)),
    )
    linhas = [[escape(rotulo), *(escape(medida(c)) for c in cenarios)] for rotulo, medida in medidas]
    return tabela(
        ("Medida", *(_nome_do_cenario(c) for c in cenarios)),
        linhas,
        "antes-e-depois",
        range(1, len(cenarios) + 1),
        compacta=True,
    )


def _nao_identificaveis(numeros_do_cenario: NumerosDoCenario, medida: Callable[[TotalDoDestino], str]) -> str:
    total = numeros_do_cenario.soltos_por_razao.get(PorQueFicaSolto.NAO_IDENTIFICAVEL_PELO_VALOR)
    return medida(total) if total is not None else ""


def _soltos_por_razao(cenarios: Sequence[NumerosDoCenario]) -> str:
    linhas = [
        [escape(razao.value), *(escape(_creditos_e_valor(c.soltos_por_razao[razao])) for c in cenarios)]
        for razao in RAZOES_DO_RESUMO
    ]
    return tabela(("Razão", *(c.nome for c in cenarios)), linhas, "soltos-por-razao", compacta=True)


def _creditos_e_valor(total: TotalDoDestino) -> str:
    return f"{total.quantidade} Crédito(s), {formatar_reais(total.valor_centavos)}"


def _grafico_da_fila(identificador: str, cenarios: Sequence[tuple[str, NumerosDoCenario]]) -> str:
    grupos = [
        GrupoDaCausaRaiz(nome, c.fila_de_excecoes.quantidade, c.fila_de_excecoes.valor_centavos) for nome, c in cenarios
    ]
    return grafico_de_barras(
        identificador,
        grupos,
        lambda grupo: grupo.quantidade,
        lambda grupo: _creditos_e_valor(TotalDoDestino(grupo.quantidade, grupo.valor_centavos)),
    )


def _ondas(relatorio: RelatorioDeImpacto) -> str:
    adesoes = relatorio.todos_migrados
    etapas: list[tuple[str, Sequence[NumerosDoCenario]]] = [
        ("Antes", [relatorio.antes] * len(adesoes)),
        *((f"Onda {onda.onda}", onda.cenarios) for onda in relatorio.ondas),
        ("Todos os franqueados", adesoes),
    ]
    matriz = tabela(
        ("Até a onda", "Franqueados migrados", *(f"Fila com {c.nome.lower()}" for c in adesoes)),
        [
            [
                escape(nome),
                str(cenarios[0].franqueados_migrados),
                *(escape(_creditos_e_valor(c.fila_de_excecoes)) for c in cenarios),
            ]
            for nome, cenarios in etapas
        ],
        "fila-por-onda",
        range(1, len(adesoes) + 2),
    )
    graficos = "".join(
        f"<h3>Fila a cada onda acumulada, {escape(todos.nome)}</h3>"
        + _grafico_da_fila(
            f"grafico-fila-por-onda-{posicao}",
            [
                ("Antes", relatorio.antes),
                *(_na_onda(onda.onda, onda.cenarios[posicao]) for onda in relatorio.ondas),
                (f"Todos os Franqueados ({todos.franqueados_migrados})", todos),
            ],
        )
        for posicao, todos in enumerate(adesoes)
    )
    return secao(
        "Ondas de migração",
        "secao-ondas",
        matriz
        + detalhes(
            "Ver os gráficos e a tabela completa das ondas",
            graficos + "<h3>Ondas acumuladas</h3>" + _tabela_das_ondas(relatorio),
        ),
        nota=EXPLICACAO_DAS_ONDAS,
    )


def _tabela_das_ondas(relatorio: RelatorioDeImpacto) -> str:
    linhas: list[tuple[str, NumerosDoCenario]] = [
        ("Antes", relatorio.antes),
        *((str(onda.onda), cenario) for onda in relatorio.ondas for cenario in onda.cenarios),
        *(("Todos os Franqueados", cenario) for cenario in relatorio.todos_migrados),
    ]
    return tabela(
        (
            "Onda acumulada",
            "Franqueados migrados",
            "Adesão (%)",
            "Créditos identificados",
            "Créditos de Franqueados não migrados",
            "Créditos na Fila",
            "Valor na Fila",
            "% resolvido sozinho (quantidade)",
            "% resolvido sozinho (valor)",
        ),
        [
            [
                escape(celula)
                for celula in (
                    onda,
                    str(numeros_do_cenario.franqueados_migrados),
                    _adesao_de(numeros_do_cenario),
                    str(numeros_do_cenario.identificados.quantidade),
                    _quantidade_de(numeros_do_cenario.soltos_por_razao.get(PorQueFicaSolto.FRANQUEADO_NAO_MIGRADO)),
                    str(numeros_do_cenario.fila_de_excecoes.quantidade),
                    formatar_reais(numeros_do_cenario.fila_de_excecoes.valor_centavos),
                    _percentual_de(numeros_do_cenario.parte_automatica.percentual_da_quantidade),
                    _percentual_de(numeros_do_cenario.parte_automatica.percentual_do_valor),
                )
            ]
            for onda, numeros_do_cenario in linhas
        ],
        "ondas",
        range(1, 9),
        compacta=True,
    )


def _na_onda(onda: int, numeros_do_cenario: NumerosDoCenario) -> tuple[str, NumerosDoCenario]:
    return f"Onda {onda} ({numeros_do_cenario.franqueados_migrados} Franqueado(s))", numeros_do_cenario


def _adesao_de(numeros_do_cenario: NumerosDoCenario) -> str:
    return "" if numeros_do_cenario.adesao is None else formatar_adesao(numeros_do_cenario.adesao)


def _quantidade_de(total: TotalDoDestino | None) -> str:
    return "" if total is None else str(total.quantidade)


def _percentual_de(percentual: Fraction | None) -> str:
    return formatar_percentual(percentual) if percentual is not None else ""


def _fila_por_motivo(cenarios: Sequence[NumerosDoCenario]) -> str:
    linhas = [
        [
            escape("Total" if motivo is None else motivo.value),
            *(escape(celula) for c in cenarios for celula in _quantidade_e_valor(_da_fila(c, motivo))),
        ]
        for motivo in (*MotivoDeNaoIdentificacao, None)
    ]
    cabecalho = (
        "Motivo de não identificação",
        *(f"{c.nome} ({medida})" for c in cenarios for medida in ("Créditos", "valor")),
    )
    return tabela(cabecalho, linhas, "fila-por-motivo", range(1, 2 * len(cenarios) + 1), compacta=True)


def _quantidade_e_valor(total: TotalDoDestino) -> tuple[str, str]:
    return str(total.quantidade), formatar_reais(total.valor_centavos)


def _da_fila(numeros_do_cenario: NumerosDoCenario, motivo: MotivoDeNaoIdentificacao | None) -> TotalDoDestino:
    return numeros_do_cenario.fila_de_excecoes if motivo is None else numeros_do_cenario.fila_por_motivo[motivo]


def _ranking(ranking: RankingDeMigracao) -> str:
    cabecalho = ("Onda", "Posição", "Franqueado", "Raiz do CNPJ", "Créditos na Fila", "Valor")
    linhas = [
        [
            escape(celula)
            for celula in (
                str(franqueado.onda),
                str(franqueado.posicao),
                franqueado.nome,
                franqueado.raiz,
                str(franqueado.quantidade),
                formatar_reais(franqueado.valor_centavos),
            )
        ]
        for franqueado in ranking.franqueados
    ]
    sem = ranking.sem_franqueado
    sem_franqueado = (
        f'<p class="nota espaco">{escape(_creditos_e_valor(TotalDoDestino(sem.quantidade, sem.valor_centavos)))} '
        f"{escape(sem.nome)}. {escape(EXPLICACAO_DO_SEM_FRANQUEADO)}</p>"
    )
    if len(linhas) > _RANKING_VISIVEL:
        conteudo = tabela(cabecalho, linhas[:_RANKING_VISIVEL], "ranking-principal", (0, 1, 4, 5)) + detalhes(
            f"Ver o ranking completo ({len(linhas)} franqueados)",
            tabela(cabecalho, linhas, "ranking", (0, 1, 4, 5), compacta=True),
        )
    else:
        conteudo = tabela(cabecalho, linhas, "ranking", (0, 1, 4, 5))
    return secao(
        "Quem migrar primeiro",
        "secao-ranking",
        conteudo + sem_franqueado,
        nota="Franqueados com mais Créditos na Fila que a Cobrança Endereçada resolveria, na ordem das ondas.",
    )


def _premissas(relatorio: RelatorioDeImpacto) -> str:
    analise = (
        f'<p class="nota" id="analise">Pasta base {escape(relatorio.pasta_base)}, semente {relatorio.semente}. '
        "A análise roda pelo comando analisar-impacto; esta página só mostra a última gravada.</p>"
    )
    linhas = [[escape(nome), escape(_valor_da_premissa(valor))] for nome, valor in relatorio.premissas]
    return analise + tabela(("Premissa", "Valor"), linhas, "premissas", compacta=True)


def _valor_da_premissa(valor: ValorDaPremissa) -> str:
    if isinstance(valor, Decimal):
        return f"{valor:f}".replace(".", ",")
    return str(valor)
