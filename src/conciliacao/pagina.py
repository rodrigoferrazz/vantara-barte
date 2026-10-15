from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from html import escape

from conciliacao.dominio import GrupoDaCausaRaiz


class Estado(StrEnum):
    OK = "ok"
    PENDENTE = "pendente"
    PROBLEMA = "problema"
    NEUTRO = "neutro"


class Produto(StrEnum):
    CONCILIACAO_ASSISTIDA = "Conciliação Assistida"
    COBRANCA_ENDERECADA = "Cobrança Endereçada"


class Visao(StrEnum):
    ANALISTA = "/"
    COBRANCA = "/cobranca"
    GESTAO = "/gestao"
    EMISSAO = "/enderecada/emissao"
    MIGRACAO = "/enderecada/migracao"
    DEMONSTRACAO = "/enderecada/demonstracao"


_VISOES_DOS_PRODUTOS = {
    Produto.CONCILIACAO_ASSISTIDA: {
        Visao.ANALISTA: "Analista",
        Visao.COBRANCA: "Cobrança",
        Visao.GESTAO: "Gestão",
    },
    Produto.COBRANCA_ENDERECADA: {
        Visao.DEMONSTRACAO: "Demonstração",
        Visao.EMISSAO: "Emissão",
        Visao.MIGRACAO: "Migração",
    },
}

_ESTILO = """
:root { color-scheme: light;
  --plano: #ffffff; --superficie: #ffffff; --superficie-2: #efefef;
  --escuro: #030202; --escuro-2: #2a2828; --sobre-cor: #ffffff;
  --tinta: #111111; --tinta-2: #6b6b6b; --tinta-3: #9a9a9a;
  --borda: #e5e5e5; --borda-forte: #d4d4d4;
  --acento: #df285d; --acento-tinta: #c11f4e; --acento-fundo: rgba(223, 40, 93, .12);
  --ok: #1f7a43; --ok-fundo: rgba(31, 122, 67, .1); --ok-borda: rgba(31, 122, 67, .25);
  --pendente: #a15c07; --pendente-fundo: rgba(217, 140, 20, .14); --pendente-borda: #e0a33a;
  --problema: #b42318; --problema-fundo: rgba(180, 35, 24, .08); --problema-borda: rgba(180, 35, 24, .25);
  --ia: #5b4bc4; --ia-fundo: rgba(91, 75, 196, .07); --ia-borda: rgba(91, 75, 196, .2);
  --barra: #df285d; --grade: #e5e5e5;
  --raio: 4px; --raio-pequeno: 2px; --sombra: none;
  --fonte: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --fonte-mono: ui-monospace, SFMono-Regular, Menlo, monospace; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--plano); color: var(--tinta);
  font: 14px/1.55 var(--fonte); -webkit-font-smoothing: antialiased; }
header.topo { background: var(--superficie); border-bottom: 1px solid var(--borda); }
.topo-dentro { max-width: 1120px; margin: 0 auto; padding: 0 24px; display: flex; align-items: center; gap: 40px; }
.marca { font-weight: 600; font-size: 17px; letter-spacing: -.02em; padding: 16px 0; white-space: nowrap;
  display: flex; align-items: center; gap: 10px; color: var(--escuro); }
.marca span { color: var(--tinta-2); font-weight: 400; font-size: 13px; letter-spacing: 0;
  padding-left: 10px; border-left: 1px solid var(--borda); }
nav { display: flex; gap: 8px; flex-wrap: wrap; }
nav a { color: var(--tinta-2); text-decoration: none; padding: 18px 4px 16px; border-bottom: 2px solid transparent;
  font-weight: 500; }
nav a:hover { color: var(--tinta); }
nav a[aria-current="page"] { color: var(--escuro); border-bottom-color: var(--acento); }
.personas { background: var(--superficie); border-top: 1px solid var(--borda); }
.personas nav { gap: 4px; padding: 10px 0; }
.personas nav a { padding: 5px 12px; font-size: 13px; border: 1px solid var(--borda); border-radius: var(--raio); }
.personas nav a:hover { background: var(--superficie-2); }
.personas nav a[aria-current="page"] { background: var(--escuro); border-color: var(--escuro); color: var(--sobre-cor); }
main { max-width: 1120px; margin: 0 auto; padding: 40px 24px 80px; }
h1 { font-size: 32px; line-height: 1.2; letter-spacing: -.02em; font-weight: 300; margin: 0; }
.subtitulo { color: var(--tinta-2); margin: 6px 0 0; }
h2 { font-size: 20px; letter-spacing: -.01em; font-weight: 400; margin: 0; }
h3 { font-size: 11px; margin: 24px 0 8px; color: var(--tinta-2); font-weight: 500; text-transform: uppercase;
  letter-spacing: .08em; }
section { margin-top: 48px; }
.cabecalho-da-secao { display: flex; align-items: baseline; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; margin-bottom: 12px; }
.cabecalho-da-secao .acoes { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.nota { color: var(--tinta-2); margin: 4px 0 16px; }
.cartao { background: var(--superficie-2); border: 1px solid var(--borda); border-radius: var(--raio); }
.cartao.tabela { background: var(--superficie); }
.cartao.com-folga { padding: 20px 24px; }
.numeros { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.numero { background: var(--superficie-2); border: 1px solid var(--borda); border-radius: var(--raio);
  padding: 20px 24px; border-top: 2px solid var(--borda-forte); }
.numero.ok { border-top-color: var(--ok); }
.numero.pendente { border-top-color: var(--pendente-borda); }
.numero.problema { border-top-color: var(--problema); }
#total-a-cobrar { border-top-color: var(--acento); }
#total-em-analise { border-top-color: var(--pendente-borda); }
.numero .rotulo { color: var(--tinta-2); font-size: 11px; font-weight: 500; text-transform: uppercase;
  letter-spacing: .08em; }
.numero .valor { font-size: 36px; font-weight: 300; letter-spacing: -.02em; line-height: 1.15; margin-top: 8px;
  font-variant-numeric: tabular-nums; }
.numero .valor small { font-size: 14px; font-weight: 400; letter-spacing: 0; color: var(--tinta-2); }
.numero .detalhe { color: var(--tinta-2); font-size: 13px; margin-top: 6px; font-variant-numeric: tabular-nums; }
.chip { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: var(--raio-pequeno);
  font-size: 12px; font-weight: 500; background: var(--superficie-2); color: var(--tinta-2); white-space: nowrap; }
.chip.ok { color: var(--ok); background: var(--ok-fundo); }
.chip.pendente { color: var(--pendente); background: var(--pendente-fundo); }
.chip.problema { color: var(--problema); background: var(--problema-fundo); }
.aviso { border-radius: var(--raio); padding: 12px 16px; border: 1px solid var(--borda); background: var(--superficie);
  margin-top: 12px; }
.aviso.problema { background: var(--problema-fundo); border-color: var(--problema-borda); color: var(--problema); }
.aviso.pendente { background: var(--pendente-fundo); border-color: transparent; color: var(--pendente); }
.aviso.ok { background: var(--ok-fundo); border-color: var(--ok-borda); color: var(--ok); }
.aviso strong { display: block; margin-bottom: 2px; font-weight: 600; }
.aviso ul { margin: 6px 0 0; padding-left: 18px; }
.vazia { color: var(--tinta-2); background: var(--superficie); border: 1px dashed var(--borda-forte);
  border-radius: var(--raio); padding: 20px 24px; margin: 0; }
details > summary { cursor: pointer; color: var(--acento); font-weight: 500; list-style: none;
  display: inline-flex; align-items: center; gap: 6px; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "▸"; font-size: 11px; transition: transform .15s; }
details[open] > summary::before { transform: rotate(90deg); }
details.bloco { margin-top: 16px; }
details.bloco > .dentro { margin-top: 12px; }
.tabela { width: 100%; overflow: hidden; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 12px 16px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--borda);
  overflow-wrap: anywhere; }
td { font-variant-numeric: tabular-nums; }
thead th { font-size: 11px; font-weight: 500; color: var(--tinta-2); background: var(--superficie-2);
  text-transform: uppercase; letter-spacing: .06em; overflow-wrap: normal; padding-top: 10px; padding-bottom: 10px; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.compacta th, table.compacta td { padding: 7px 12px; font-size: 13px; }
.forte { font-weight: 500; }
.suave { color: var(--tinta-2); }
button, .botao { font: inherit; font-weight: 500; font-size: 13px; border-radius: var(--raio); padding: 8px 16px;
  border: 1px solid var(--borda-forte); background: var(--superficie); color: var(--tinta); cursor: pointer;
  text-decoration: none; display: inline-flex; align-items: center; gap: 6px; line-height: 1.3;
  white-space: nowrap; }
button:hover, .botao:hover { background: var(--superficie-2); border-color: var(--tinta-3); }
button.primario, .botao.primario { background: var(--acento); border-color: var(--acento); color: var(--sobre-cor); }
button.primario:hover, .botao.primario:hover { background: var(--acento-tinta); border-color: var(--acento-tinta); }
button.confirmar { background: var(--escuro); border-color: var(--escuro); color: var(--sobre-cor); }
button.confirmar:hover { background: var(--escuro-2); border-color: var(--escuro-2); }
button.discreto { border-color: transparent; background: transparent; color: var(--tinta-2); padding: 8px; }
button.discreto:hover { color: var(--problema); background: var(--problema-fundo); }
button:disabled { opacity: .5; cursor: not-allowed; }
input[type="text"], input:not([type]) { font: inherit; padding: 7px 10px; border-radius: var(--raio);
  border: 1px solid var(--borda-forte); background: var(--superficie); color: var(--tinta); min-width: 0; }
input:focus-visible, button:focus-visible, summary:focus-visible, a:focus-visible {
  outline: 2px solid var(--acento); outline-offset: 2px; }
form { margin: 0; }
form.em-linha { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.botoes { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.identificador { font-family: var(--fonte-mono); font-size: 12px; }
form.em-linha label { display: flex; flex-direction: column; gap: 2px; font-size: 11px; color: var(--tinta-2);
  text-transform: uppercase; letter-spacing: .06em; }
a { color: var(--acento); }
.grafico { overflow: hidden; }
svg { max-width: 100%; height: auto; display: block; }
svg text { fill: var(--tinta); font-size: 12px; font-family: inherit; }
svg text.valor { fill: var(--tinta-2); font-variant-numeric: tabular-nums; }
svg .marca-da-barra { fill: var(--barra); }
svg line.base { stroke: var(--borda-forte); stroke-width: 1; }
svg g.barra:hover .marca-da-barra { opacity: .8; }
.duas-colunas { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
#recusa { color: var(--problema); font-weight: 500; }
.espaco { margin-top: 24px; }
h3.sem-margem { margin-top: 0; }
details.linha { margin-top: 6px; font-size: 13px; }
details.linha > .dentro { margin-top: 8px; }
dl.explicacao { display: grid; grid-template-columns: 110px 1fr; gap: 4px 12px; margin: 0; padding: 12px 14px;
  background: var(--superficie); border: 1px solid var(--borda); border-radius: var(--raio); font-size: 13px; }
dl.explicacao dt { color: var(--tinta-2); font-weight: 500; }
dl.explicacao dd { margin: 0; overflow-wrap: anywhere; }
.decisao-registrada { display: flex; flex-direction: column; gap: 4px; align-items: flex-start; font-size: 13px; }
.cartoes { display: flex; flex-direction: column; gap: 12px; }
.item-da-fila { padding: 20px 24px; border-left: 2px solid var(--pendente-borda); }
.item-da-fila.decidido { border-left-color: var(--ok); }
.cabeca-do-item { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.pagador { font-weight: 500; font-size: 15px; overflow-wrap: anywhere; }
.valor-do-item { font-size: 22px; font-weight: 300; letter-spacing: -.01em; white-space: nowrap;
  font-variant-numeric: tabular-nums; }
.motivo { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-top: 10px; }
.sugerido { margin-top: 8px; }
.parecer { margin-top: 12px; padding: 10px 14px; border-radius: var(--raio); background: var(--ia-fundo);
  border: 1px solid var(--ia-borda); }
.parecer ul { margin: 6px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
.parecer.indisponivel { background: var(--problema-fundo); border-color: var(--problema-borda); }
.acoes-da-linha { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.rotulo-da-ia { color: var(--ia); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
.ia-indisponivel { color: var(--problema); font-weight: 500; font-size: 11px; text-transform: uppercase;
  letter-spacing: .08em; }
.decisoes { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--borda); }
.mais-decisoes { display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start; }
.item-da-fila .decisao-registrada { margin-bottom: 4px; }
.encargos { display: flex; gap: 4px; justify-content: flex-end; flex-wrap: wrap; margin-top: 4px; }
.etiqueta { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: var(--raio-pequeno); white-space: nowrap;
  color: var(--pendente); background: var(--pendente-fundo); }
.alerta-de-duplicidade { margin-top: 6px; padding: 6px 10px; border-radius: var(--raio); font-size: 13px;
  color: var(--problema); background: var(--problema-fundo); border: 1px solid var(--problema-borda); }
.alerta-de-duplicidade a { color: inherit; font-weight: 500; }
tr.destacada td { background: var(--ok-fundo); }
tr.destacada td:first-child { box-shadow: inset 2px 0 0 var(--ok); }
.sem-quebra { white-space: nowrap; }
.enderecado { display: inline-block; margin-bottom: 4px; padding: 2px 8px;
  border-radius: var(--raio-pequeno); font-size: 12px; font-weight: 500; color: var(--acento);
  background: var(--acento-fundo); }
.simulacao { border: 1px dashed var(--pendente-borda); background: var(--pendente-fundo); color: var(--pendente);
  border-radius: var(--raio); padding: 12px 16px; margin-top: 16px; }
.simulacao strong { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-right: 6px; }
.passos { display: flex; flex-direction: column; gap: 12px; }
.passo { padding: 20px 24px; display: grid; grid-template-columns: 40px 1fr; gap: 4px 16px; align-items: start; }
.passo .ordem { width: 28px; height: 28px; border-radius: var(--raio); display: grid; place-items: center;
  font-weight: 500; background: var(--acento); color: var(--sobre-cor); font-variant-numeric: tabular-nums; }
.passo.feito .ordem { background: var(--ok-fundo); color: var(--ok); }
.passo h2 { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.passo .explicacao-do-passo { color: var(--tinta-2); margin: 4px 0 10px; }
.passo > div { grid-column: 2; }
.situacao-da-ia { margin: 10px 0 0; font-size: 13px; color: var(--tinta-2); display: flex; gap: 8px;
  align-items: center; }
"""


def documento(titulo: str, corpo: str, visao: Visao | None = None) -> str:
    produto = next((p for p, visoes in _VISOES_DOS_PRODUTOS.items() if visao in visoes), None)
    personas = (
        f'<div class="personas"><div class="topo-dentro">{_navegacao(_VISOES_DOS_PRODUTOS[produto], visao)}</div></div>'
        if produto is not None
        else ""
    )
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(titulo)}</title><style>{_ESTILO}</style></head>"
        f'<body><header class="topo"><div class="topo-dentro"><div class="marca">Vantara <span>'
        f"</span></div>{_produtos(produto)}</div>{personas}</header><main>{corpo}</main></body></html>"
    )


def _produtos(ativo: Produto | None) -> str:
    links = "".join(
        f'<a href="{next(iter(visoes)).value}"{' aria-current="page"' if produto is ativo else ""}>{escape(produto)}</a>'
        for produto, visoes in _VISOES_DOS_PRODUTOS.items()
    )
    return f'<nav id="produtos">{links}</nav>'


def _navegacao(visoes: Mapping[Visao, str], ativa: Visao | None) -> str:
    links = "".join(
        f'<a href="{visao.value}"{' aria-current="page"' if visao is ativa else ""}>{escape(nome)}</a>'
        for visao, nome in visoes.items()
    )
    return f'<nav id="navegacao">{links}</nav>'


def cabecalho_da_pagina(titulo: str, subtitulo: str = "") -> str:
    complemento = f'<p class="subtitulo">{escape(subtitulo)}</p>' if subtitulo else ""
    return f"<div><h1>{escape(titulo)}</h1>{complemento}</div>"


def secao(titulo: str, identificador: str, conteudo: str, acoes: str = "", nota: str = "") -> str:
    lado = f'<div class="acoes">{acoes}</div>' if acoes else ""
    texto = f'<p class="nota">{escape(nota)}</p>' if nota else ""
    return (
        f'<section id="{identificador}"><div class="cabecalho-da-secao"><h2>{escape(titulo)}</h2>{lado}</div>'
        f"{texto}{conteudo}</section>"
    )


@dataclass(frozen=True)
class Numero:
    rotulo: str
    valor: str
    detalhe: str = ""
    estado: Estado = Estado.NEUTRO
    identificador: str = ""
    complemento: str = ""


def numeros(*itens: Numero) -> str:
    return '<div class="numeros">' + "".join(_numero(item) for item in itens) + "</div>"


def _numero(numero: Numero) -> str:
    atributo = f' id="{numero.identificador}"' if numero.identificador else ""
    detalhe = f'<div class="detalhe">{escape(numero.detalhe)}</div>' if numero.detalhe else ""
    complemento = f" <small>{escape(numero.complemento)}</small>" if numero.complemento else ""
    return (
        f'<div class="numero {numero.estado.value}"{atributo}><div class="rotulo">{escape(numero.rotulo)}</div>'
        f'<div class="valor">{escape(numero.valor)}{complemento}</div>{detalhe}</div>'
    )


def chip(texto: str, estado: Estado) -> str:
    return f'<span class="chip {estado.value}">{escape(texto)}</span>'


def aviso(titulo: str, texto: str, estado: Estado, identificador: str = "", itens: Sequence[str] = ()) -> str:
    atributo = f' id="{identificador}"' if identificador else ""
    lista = "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in itens) + "</ul>" if itens else ""
    corpo = f"<span>{escape(texto)}</span>" if texto else ""
    return f'<div class="aviso {estado.value}"{atributo}><strong>{escape(titulo)}</strong>{corpo}{lista}</div>'


def vazia(texto: str, identificador: str = "") -> str:
    atributo = f' id="{identificador}"' if identificador else ""
    return f'<p class="vazia"{atributo}>{escape(texto)}</p>'


def detalhes(resumo: str, conteudo: str, classe: str = "bloco") -> str:
    return f'<details class="{classe}"><summary>{escape(resumo)}</summary><div class="dentro">{conteudo}</div></details>'


def tabela(
    cabecalho: Sequence[str],
    linhas: Iterable[Sequence[str]],
    identificador: str = "",
    numericas: Iterable[int] = (),
    compacta: bool = False,
    vazia_com: str = "Lista vazia.",
    destacadas: Iterable[int] = (),
) -> str:
    """As células de `linhas` já vêm escapadas; o cabeçalho é texto. `destacadas` são posições de linhas."""
    alinhadas = set(numericas)
    em_destaque = set(destacadas)
    corpo = "".join(
        ('<tr class="destacada">' if numero in em_destaque else "<tr>")
        + "".join(_celula("td", celula, posicao in alinhadas) for posicao, celula in enumerate(linha))
        + "</tr>"
        for numero, linha in enumerate(linhas)
    )
    if not corpo:
        return vazia(vazia_com)
    atributos = (f' id="{identificador}"' if identificador else "") + (' class="compacta"' if compacta else "")
    colunas = "".join(_celula("th", escape(coluna), posicao in alinhadas) for posicao, coluna in enumerate(cabecalho))
    return (
        f'<div class="cartao tabela"><table{atributos}><thead><tr>{colunas}</tr></thead>'
        f"<tbody>{corpo}</tbody></table></div>"
    )


def _celula(tag: str, conteudo: str, numerica: bool) -> str:
    return f'<{tag} class="num">{conteudo}</{tag}>' if numerica else f"<{tag}>{conteudo}</{tag}>"


def campo_oculto(nome: str, valor: str) -> str:
    return f'<input type="hidden" name="{nome}" value="{escape(valor)}">'


def renderizar_recusa(
    mensagem: str, titulo: str = "Decisão não registrada", volta: tuple[Visao, str] = (Visao.ANALISTA, "Voltar à conciliação")
) -> str:
    destino, texto = volta
    return documento(
        titulo,
        cabecalho_da_pagina(titulo)
        + f'<div class="aviso problema"><p id="recusa">{escape(mensagem)}</p></div>'
        + f'<p><a href="{destino.value}">{escape(texto)}</a></p>',
    )


_LARGURA_DO_ROTULO = 280
_LARGURA_DAS_BARRAS = 320
_LARGURA_DO_VALOR = 200
_ALTURA_DA_LINHA = 30
_ALTURA_DA_BARRA = 16
_RAIO = 4


def grafico_de_barras(
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
        rotulo = escape(rotulo_da_medida(grupo))
        barras.append(
            f'<g class="barra"><title>{escape(grupo.nome)}: {rotulo}</title>'
            f'<text x="0" y="{base_do_texto}">{escape(grupo.nome)}</text>'
            + _barra(_LARGURA_DO_ROTULO, topo + (_ALTURA_DA_LINHA - _ALTURA_DA_BARRA) / 2, comprimento)
            + f'<text class="valor" x="{_LARGURA_DO_ROTULO + comprimento + 8:.1f}" y="{base_do_texto}">{rotulo}</text>'
            "</g>"
        )
    base = f'<line class="base" x1="{_LARGURA_DO_ROTULO}" y1="0" x2="{_LARGURA_DO_ROTULO}" y2="{altura}"></line>'
    return (
        f'<div class="grafico"><svg id="{identificador}" role="img" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}">{"".join(barras)}{base}</svg></div>'
    )


def _barra(x: float, y: float, comprimento: float) -> str:
    """Barra horizontal com a ponta arredondada e a base reta, encostada no eixo."""
    raio = min(_RAIO, comprimento)
    fim = x + comprimento
    caminho = (
        f"M{x:.1f},{y:.1f} H{fim - raio:.1f} Q{fim:.1f},{y:.1f} {fim:.1f},{y + raio:.1f} "
        f"V{y + _ALTURA_DA_BARRA - raio:.1f} Q{fim:.1f},{y + _ALTURA_DA_BARRA:.1f} {fim - raio:.1f},"
        f"{y + _ALTURA_DA_BARRA:.1f} H{x:.1f} Z"
    )
    return f'<path class="marca-da-barra" d="{caminho}" data-comprimento="{comprimento:.1f}"></path>'
