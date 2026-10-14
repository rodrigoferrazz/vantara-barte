from collections.abc import Callable, Iterable, Mapping, Sequence
from fractions import Fraction
from html import escape

from conciliacao.calendario import vencimento_efetivo
from conciliacao.decisoes import DECISOES_DE_CREDITO_DA_FILA, DECISOES_DE_DUPLICIDADE
from conciliacao.dominio import (
    CausaRaiz,
    DecisaoDaTela,
    GrupoDaCausaRaiz,
    Item,
    ItemDeTitulo,
    Lancamento,
    Resultado,
    TipoDeDecisao,
    TituloNaCobranca,
)
from conciliacao.normalizacao import formatar_percentual, formatar_reais
from conciliacao.saidas import (
    ABA_DA_FILA_DE_EXCECOES,
    ABA_DA_LISTA_DE_BAIXA,
    descrever_titulos,
    linhas_do_resumo,
    total_da_cobranca,
)

_ESTILO = """
:root { --fundo: #ffffff; --texto: #1d1d1f; --suave: #6b6b70; --borda: #d9d9de; --cabecalho: #f3f3f6;
  --barra: #2f6db5; --parecer: #fff6d6; --parecer-borda: #c99a06; --alerta: #b3261e; }
@media (prefers-color-scheme: dark) {
  :root { --fundo: #18181b; --texto: #ececf1; --suave: #a1a1aa; --borda: #3f3f46; --cabecalho: #27272a;
    --barra: #6aa3e8; --parecer: #3a3115; --parecer-borda: #e0b528; --alerta: #f2b8b5; }
}
body { margin: 0; padding: 16px; background: var(--fundo); color: var(--texto);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1200px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 16px; }
h2 { font-size: 18px; margin: 32px 0 8px; }
h3 { font-size: 15px; margin: 20px 0 8px; }
p.total, p.vazia { color: var(--suave); margin: 4px 0 8px; }
.rolagem { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--borda); padding: 4px 8px; text-align: left; vertical-align: top; }
thead th, #resumo th { background: var(--cabecalho); }
#resumo th { width: 32%; font-weight: 600; }
.parecer { margin-top: 6px; padding: 4px 8px; background: var(--parecer); border-left: 4px solid var(--parecer-borda); }
.ia-indisponivel { font-weight: 700; color: var(--alerta); }
#conflitos { border-left: 4px solid var(--alerta); padding: 4px 12px; }
#conflitos h2 { color: var(--alerta); margin-top: 8px; }
#recusa { color: var(--alerta); font-weight: 600; }
form.decisao { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; margin: 2px 0; }
form.decisao label { display: flex; flex-direction: column; font-size: 12px; color: var(--suave); }
input, select, button { font: inherit; }
svg { max-width: 100%; height: auto; }
svg text { fill: var(--texto); font-size: 12px; }
svg rect { fill: var(--barra); }
"""


def renderizar(resultado: Resultado | None, decididos_na_tela: Mapping[str, DecisaoDaTela] | None = None) -> str:
    if resultado is None:
        corpo = (
            '<p id="sem-execucao">Não há execução registrada no armazenamento. '
            "Rode a conciliação sobre uma pasta de arquivos para gerar a primeira.</p>"
        )
        titulo = "Conciliação"
    else:
        corpo = _corpo(resultado, decididos_na_tela or {})
        titulo = f"Conciliação - execução {resultado.resumo.execucao}"
    return _documento(titulo, corpo)


def renderizar_recusa(mensagem: str) -> str:
    return _documento(
        "Decisão não registrada",
        f'<p id="recusa">{escape(mensagem)}</p><p><a href="/">Voltar à tela</a></p>',
    )


def _documento(titulo: str, corpo: str) -> str:
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(titulo)}</title><style>{_ESTILO}</style></head>"
        f"<body><main><h1>{escape(titulo)}</h1>{corpo}</main></body></html>"
    )


def _corpo(resultado: Resultado, decididos_na_tela: Mapping[str, DecisaoDaTela]) -> str:
    return "".join(
        (
            _secao("Resumo da execução", "secao-resumo", _tabela_do_resumo(resultado)),
            _conflitos(resultado.resumo.decisoes.conflitos),
            _secao("Lista de baixa", "lista-de-baixa", _itens(resultado.lista_de_baixa)),
            _secao(
                "Decidir a Lista de baixa",
                "decidir-lista-de-baixa",
                _decidir_a_lista(resultado.lista_de_baixa, decididos_na_tela),
            ),
            _secao("Fila de exceções", "fila-de-excecoes", _itens(resultado.fila_de_excecoes, resultado.itens_de_titulo)),
            _secao(
                "Resolver a Fila de exceções",
                "resolver-fila",
                _resolver_a_fila(resultado.fila_de_excecoes, resultado.itens_de_titulo, decididos_na_tela),
            ),
            _secao(
                "Lista de cobrança",
                "lista-de-cobranca",
                _total(total_da_cobranca(resultado.lista_de_cobranca)) + _cobranca(resultado.lista_de_cobranca),
            ),
            _secao(
                "Títulos em análise",
                "em-analise",
                _total(
                    f"{total_da_cobranca(resultado.em_analise)}. Há Crédito candidato na Fila de exceções: "
                    "não cobrar ainda."
                )
                + _cobranca(resultado.em_analise, resultado),
            ),
            _secao("Causa raiz", "causa-raiz", _causa_raiz(resultado.causa_raiz)),
            _secao("Fora do escopo", "fora-do-escopo", _fora_do_escopo(resultado.fora_do_escopo)),
        )
    )


_AVISO_DAS_DECISOES = (
    "As decisões da tela valem na próxima execução, junto com as do Excel. Item decidido no Excel e na tela "
    "desde a última execução vira conflito e nenhuma das duas decisões é aplicada."
)


def _conflitos(conflitos: Sequence[str]) -> str:
    if not conflitos:
        return ""
    itens = "".join(f"<li>{escape(conflito)}</li>" for conflito in conflitos)
    return _secao(
        "Conflitos entre Excel e tela",
        "conflitos",
        _total("Nenhuma das decisões destes itens foi aplicada; decida de novo por uma só origem.") + f"<ul>{itens}</ul>",
    )


def _decidir_a_lista(itens: Sequence[Item], decididos_na_tela: Mapping[str, DecisaoDaTela]) -> str:
    if not itens:
        return '<p class="vazia">Lista vazia.</p>'
    lote = (
        '<form method="post" action="/confirmar-lote" class="decisao">'
        "<button>Confirmar o lote</button> <span>confirma os itens ainda sem decisão na tela</span></form>"
    )
    linhas = [
        (
            "",
            (
                escape(item.identificador),
                _decidido_na_tela(decididos_na_tela.get(item.identificador)),
                _formulario(ABA_DA_LISTA_DE_BAIXA, item.identificador, _campo_oculto("decisao", "confirmar"), "Confirmar")
                + _formulario(
                    ABA_DA_LISTA_DE_BAIXA,
                    item.identificador,
                    _campo_oculto("decisao", TipoDeDecisao.REJEITAR.value)
                    + '<label>Motivo da rejeição<input name="motivo" required></label>',
                    "Rejeitar",
                ),
            ),
        )
        for item in itens
    ]
    return _total(_AVISO_DAS_DECISOES) + lote + _tabela(("Item", "Decisão na tela", "Decidir"), linhas)


def _resolver_a_fila(
    itens: Sequence[Item], itens_de_titulo: Sequence[ItemDeTitulo], decididos_na_tela: Mapping[str, DecisaoDaTela]
) -> str:
    de_credito = (
        _escolha(DECISOES_DE_CREDITO_DA_FILA)
        + '<label>Título(s) escolhido(s)<input name="titulos"></label>'
        + '<label>CNPJ do Franqueado (Conciliado fora)<input name="franqueado"></label>'
        + '<label>Referência (Conciliado fora)<input name="referencia"></label>'
    )
    de_titulo = _escolha(DECISOES_DE_DUPLICIDADE) + '<label>Título oficial (mesma dívida)<input name="titulos"></label>'
    linhas = [
        (
            "",
            (
                escape(identificador),
                _decidido_na_tela(decididos_na_tela.get(identificador)),
                _formulario(ABA_DA_FILA_DE_EXCECOES, identificador, campos, "Resolver"),
            ),
        )
        for identificador, campos in (
            *((item.identificador, de_credito) for item in itens),
            *((item.identificador, de_titulo) for item in itens_de_titulo),
        )
    ]
    if not linhas:
        return '<p class="vazia">Lista vazia.</p>'
    return _total(_AVISO_DAS_DECISOES) + _tabela(("Item", "Decisão na tela", "Resolver"), linhas)


def _formulario(aba: str, item: str, campos: str, botao: str) -> str:
    return (
        '<form method="post" action="/decidir" class="decisao">'
        f'{_campo_oculto("aba", aba)}{_campo_oculto("item", item)}{campos}<button>{escape(botao)}</button></form>'
    )


def _campo_oculto(nome: str, valor: str) -> str:
    return f'<input type="hidden" name="{nome}" value="{escape(valor)}">'


def _escolha(tipos: Iterable[TipoDeDecisao]) -> str:
    opcoes = "".join(f'<option value="{escape(tipo.value)}">{escape(tipo.value)}</option>' for tipo in tipos)
    return f'<label>Decisão<select name="decisao" required><option value=""></option>{opcoes}</select></label>'


def _decidido_na_tela(decisao: DecisaoDaTela | None) -> str:
    if decisao is None:
        return ""
    linha = decisao.linha
    detalhes = [
        f"{rotulo}: {valor}"
        for rotulo, valor in (
            ("motivo", linha.motivo),
            ("Título(s)", linha.titulos),
            ("Franqueado", linha.franqueado),
            ("referência", linha.referencia),
        )
        if valor
    ]
    texto = linha.decisao + (f" ({'; '.join(detalhes)})" if detalhes else "")
    return escape(f"{texto}, por {decisao.autor} em {decisao.momento:%d/%m/%Y %H:%M}")


def _secao(titulo: str, identificador: str, conteudo: str) -> str:
    return f'<section id="{identificador}"><h2>{escape(titulo)}</h2>{conteudo}</section>'


def _total(texto: str) -> str:
    return f'<p class="total">{escape(texto)}</p>'


def _tabela_do_resumo(resultado: Resultado) -> str:
    linhas = "".join(
        f"<tr><th>{escape(rotulo)}</th><td>{escape(str(valor))}</td></tr>" for rotulo, valor in linhas_do_resumo(resultado)
    )
    return f'<div class="rolagem"><table id="resumo"><tbody>{linhas}</tbody></table></div>'


def _tabela(cabecalho: Sequence[str], linhas: Iterable[tuple[str, Sequence[str]]], identificador: str = "") -> str:
    corpo = "".join(
        (f'<tr class="{classe}">' if classe else "<tr>") + "".join(f"<td>{celula}</td>" for celula in celulas) + "</tr>"
        for classe, celulas in linhas
    )
    if not corpo:
        return '<p class="vazia">Lista vazia.</p>'
    atributo = f' id="{identificador}"' if identificador else ""
    colunas = "".join(f"<th>{escape(coluna)}</th>" for coluna in cabecalho)
    return f'<div class="rolagem"><table{atributo}><thead><tr>{colunas}</tr></thead><tbody>{corpo}</tbody></table></div>'


def _credito(lancamento: Lancamento) -> str:
    partes = [f"{lancamento.banco} {lancamento.conta}", f"{lancamento.data:%d/%m/%Y}", lancamento.historico]
    if lancamento.documento:
        partes.append(f"documento {lancamento.documento}")
    partes.append(formatar_reais(lancamento.valor_centavos))
    return escape(", ".join(partes))


def _explicacao(item: Item) -> str:
    if not item.pareceres:
        return escape(item.explicacao)
    marcacao = '<span class="ia-indisponivel">IA indisponível</span> ' if item.ia_indisponivel else ""
    pareceres = "; ".join(parecer.descrever() for parecer in item.pareceres)
    return f'{escape(item.explicacao)}<div class="parecer">{marcacao}Parecer da IA: {escape(pareceres)}</div>'


def _itens(itens: Sequence[Item], itens_de_titulo: Sequence[ItemDeTitulo] = ()) -> str:
    linhas = [
        (
            "com-parecer" if item.pareceres else "",
            (
                escape(item.identificador),
                _credito(item.lancamento),
                escape(descrever_titulos(item.titulos)),
                escape("; ".join(tipo.value for tipo in item.evidencia)),
                escape(item.motivo.value if item.motivo else ""),
                _explicacao(item),
            ),
        )
        for item in itens
    ] + [
        (
            "",
            (
                escape(item.identificador),
                "",
                escape(descrever_titulos(item.titulos)),
                "",
                escape(item.motivo.value),
                escape(item.explicacao),
            ),
        )
        for item in itens_de_titulo
    ]
    return _tabela(("Item", "Crédito", "Título(s)", "Evidência", "Motivo", "Explicação"), linhas)


def _cobranca(titulos: Sequence[TituloNaCobranca], candidatos_de: Resultado | None = None) -> str:
    cabecalho = ["Título", "Sistema de origem", "Franqueado", "CNPJ", "Vencimento", "Vencimento efetivo", "Valor", "Saldo"]
    if candidatos_de is not None:
        cabecalho.append("Créditos candidatos")
    linhas = []
    for na_cobranca in titulos:
        titulo = na_cobranca.titulo
        celulas = [
            titulo.documento,
            titulo.sistema_de_origem,
            titulo.nome_do_franqueado,
            titulo.cnpj,
            f"{titulo.vencimento:%d/%m/%Y}",
            f"{vencimento_efetivo(titulo.vencimento):%d/%m/%Y}",
            formatar_reais(titulo.valor_centavos),
            formatar_reais(na_cobranca.saldo_centavos),
        ]
        if candidatos_de is not None:
            celulas.append(
                "; ".join(candidatos_de.item_do_lancamento(c).identificador for c in na_cobranca.creditos_candidatos)
            )
        linhas.append(("", [escape(celula) for celula in celulas]))
    return _tabela(cabecalho, linhas)


def _causa_raiz(causa_raiz: CausaRaiz) -> str:
    agregacoes = (
        ("Por Motivo de não identificação", "causa-raiz-por-motivo", causa_raiz.por_motivo),
        ("Por Franqueado", "causa-raiz-por-franqueado", causa_raiz.por_franqueado),
        ("Por banco", "causa-raiz-por-banco", causa_raiz.por_banco),
        ("Por canal", "causa-raiz-por-canal", causa_raiz.por_canal),
    )
    graficos = (
        "<h3>Quantidade por Motivo</h3>"
        + _grafico_de_barras(
            "grafico-quantidade-por-motivo", causa_raiz.por_motivo, lambda g: g.quantidade, lambda g: str(g.quantidade)
        )
        + "<h3>Valor por Motivo</h3>"
        + _grafico_de_barras(
            "grafico-valor-por-motivo",
            causa_raiz.por_motivo,
            lambda g: g.valor_centavos,
            lambda g: formatar_reais(g.valor_centavos),
        )
    )
    tabelas = "".join(
        f"<h3>{escape(titulo)}</h3>" + _agregacao(identificador, causa_raiz, grupos)
        for titulo, identificador, grupos in agregacoes
    )
    total = _total(
        f"{causa_raiz.quantidade} Crédito(s) na Fila de exceções e Conciliados fora, "
        f"{formatar_reais(causa_raiz.valor_centavos)}"
    )
    return total + graficos + tabelas


def _agregacao(identificador: str, causa_raiz: CausaRaiz, grupos: Sequence[GrupoDaCausaRaiz]) -> str:
    total = GrupoDaCausaRaiz("Total", causa_raiz.quantidade, causa_raiz.valor_centavos)
    linhas = [
        (
            "",
            [
                escape(celula)
                for celula in (
                    grupo.nome,
                    str(grupo.quantidade),
                    _percentual(causa_raiz.fracao_da_quantidade(grupo)),
                    formatar_reais(grupo.valor_centavos),
                    _percentual(causa_raiz.fracao_do_valor(grupo)),
                )
            ],
        )
        for grupo in (*grupos, total)
    ]
    return _tabela(("Grupo", "Quantidade", "% quantidade", "Valor", "% valor"), linhas, identificador)


def _percentual(fracao: Fraction | None) -> str:
    return formatar_percentual(fracao * 100) if fracao is not None else ""


_LARGURA_DO_ROTULO = 270
_LARGURA_DAS_BARRAS = 300
_LARGURA_DO_VALOR = 110
_ALTURA_DA_LINHA = 24
_ALTURA_DA_BARRA = 14


def _grafico_de_barras(
    identificador: str,
    grupos: Sequence[GrupoDaCausaRaiz],
    medida: Callable[[GrupoDaCausaRaiz], int],
    rotulo_da_medida: Callable[[GrupoDaCausaRaiz], str],
) -> str:
    maior = max((medida(grupo) for grupo in grupos), default=0)
    largura = _LARGURA_DO_ROTULO + _LARGURA_DAS_BARRAS + _LARGURA_DO_VALOR
    altura = _ALTURA_DA_LINHA * len(grupos)
    barras = []
    for posicao, grupo in enumerate(grupos):
        topo = posicao * _ALTURA_DA_LINHA
        base_do_texto = topo + _ALTURA_DA_LINHA // 2 + 4
        comprimento = _LARGURA_DAS_BARRAS * medida(grupo) / maior if maior else 0.0
        barras.append(
            '<g class="barra">'
            f'<text x="0" y="{base_do_texto}">{escape(grupo.nome)}</text>'
            f'<rect x="{_LARGURA_DO_ROTULO}" y="{topo + (_ALTURA_DA_LINHA - _ALTURA_DA_BARRA) // 2}" '
            f'width="{comprimento:.1f}" height="{_ALTURA_DA_BARRA}"></rect>'
            f'<text x="{_LARGURA_DO_ROTULO + comprimento + 6:.1f}" y="{base_do_texto}">'
            f"{escape(rotulo_da_medida(grupo))}</text>"
            "</g>"
        )
    return (
        f'<div class="rolagem"><svg id="{identificador}" role="img" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}">{"".join(barras)}</svg></div>'
    )


def _fora_do_escopo(itens: Sequence[Item]) -> str:
    linhas = [
        ("", (escape(item.identificador), _credito(item.lancamento), escape(item.explicacao))) for item in itens
    ]
    return _tabela(("Item", "Crédito", "Explicação"), linhas)
