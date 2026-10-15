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
        Visao.EMISSAO: "Emissão",
        Visao.MIGRACAO: "Migração",
        Visao.DEMONSTRACAO: "Demonstração",
    },
}

_ESTILO = """
:root { color-scheme: light;
  --plano: #f5f5f2; --superficie: #ffffff; --superficie-2: #fafaf8;
  --tinta: #111110; --tinta-2: #52514e; --tinta-3: #77766f;
  --borda: #e4e3dc; --borda-forte: #cfcec6;
  --acento: #2a78d6; --acento-tinta: #1c5cab; --acento-fundo: #eaf2fc;
  --ok: #17701a; --ok-fundo: #e8f4e6; --ok-borda: #b7dbb3;
  --pendente: #8a5a00; --pendente-fundo: #fff5dc; --pendente-borda: #efd38c;
  --problema: #b42323; --problema-fundo: #fdeded; --problema-borda: #f0bdbd;
  --ia: #4f3fc0; --ia-fundo: #f1effd; --ia-borda: #cfc8f5;
  --barra: #2a78d6; --grade: #e1e0d9;
  --sombra: 0 1px 2px rgba(17, 17, 16, .05); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { color-scheme: dark;
    --plano: #0f0f0e; --superficie: #1a1a19; --superficie-2: #212120;
    --tinta: #f0efec; --tinta-2: #c3c2b7; --tinta-3: #9a998f;
    --borda: #2e2e2c; --borda-forte: #44443f;
    --acento: #5598e7; --acento-tinta: #86b6ef; --acento-fundo: #18273a;
    --ok: #6fcf6f; --ok-fundo: #15291a; --ok-borda: #2c5530;
    --pendente: #f2c45a; --pendente-fundo: #2e2410; --pendente-borda: #5b4718;
    --problema: #f19a9a; --problema-fundo: #341616; --problema-borda: #6a2c2c;
    --ia: #b3a9f2; --ia-fundo: #221f3a; --ia-borda: #433b78;
    --barra: #3987e5; --grade: #2c2c2a; --sombra: none; }
}
:root[data-theme="dark"] { color-scheme: dark;
  --plano: #0f0f0e; --superficie: #1a1a19; --superficie-2: #212120;
  --tinta: #f0efec; --tinta-2: #c3c2b7; --tinta-3: #9a998f;
  --borda: #2e2e2c; --borda-forte: #44443f;
  --acento: #5598e7; --acento-tinta: #86b6ef; --acento-fundo: #18273a;
  --ok: #6fcf6f; --ok-fundo: #15291a; --ok-borda: #2c5530;
  --pendente: #f2c45a; --pendente-fundo: #2e2410; --pendente-borda: #5b4718;
  --problema: #f19a9a; --problema-fundo: #341616; --problema-borda: #6a2c2c;
  --ia: #b3a9f2; --ia-fundo: #221f3a; --ia-borda: #433b78;
  --barra: #3987e5; --grade: #2c2c2a; --sombra: none; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--plano); color: var(--tinta);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; -webkit-font-smoothing: antialiased; }
header.topo { background: var(--superficie); border-bottom: 1px solid var(--borda); }
.topo-dentro { max-width: 1120px; margin: 0 auto; padding: 0 24px; display: flex; align-items: center; gap: 32px; }
.marca { font-weight: 700; letter-spacing: -.01em; padding: 14px 0; white-space: nowrap; }
.marca span { color: var(--tinta-3); font-weight: 500; }
nav { display: flex; gap: 4px; flex-wrap: wrap; }
nav a { color: var(--tinta-2); text-decoration: none; padding: 15px 12px 13px; border-bottom: 2px solid transparent;
  font-weight: 500; }
nav a:hover { color: var(--tinta); }
nav a[aria-current="page"] { color: var(--tinta); border-bottom-color: var(--acento); }
.personas { background: var(--superficie-2); border-bottom: 1px solid var(--borda); }
.personas nav a { padding: 9px 12px 7px; font-size: 13px; }
main { max-width: 1120px; margin: 0 auto; padding: 28px 24px 64px; }
h1 { font-size: 24px; line-height: 1.25; letter-spacing: -.015em; margin: 0; }
.subtitulo { color: var(--tinta-2); margin: 4px 0 0; }
h2 { font-size: 17px; letter-spacing: -.01em; margin: 0; }
h3 { font-size: 14px; margin: 20px 0 8px; color: var(--tinta-2); font-weight: 600; }
section { margin-top: 32px; }
.cabecalho-da-secao { display: flex; align-items: baseline; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; margin-bottom: 12px; }
.cabecalho-da-secao .acoes { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.nota { color: var(--tinta-2); margin: 4px 0 12px; }
.cartao { background: var(--superficie); border: 1px solid var(--borda); border-radius: 10px; box-shadow: var(--sombra); }
.cartao.com-folga { padding: 16px 20px; }
.numeros { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.numero { background: var(--superficie); border: 1px solid var(--borda); border-radius: 10px; padding: 16px 18px;
  box-shadow: var(--sombra); border-top: 3px solid var(--borda-forte); }
.numero.ok { border-top-color: var(--ok); }
.numero.pendente { border-top-color: var(--pendente-borda); }
.numero.problema { border-top-color: var(--problema); }
.numero .rotulo { color: var(--tinta-2); font-size: 13px; font-weight: 500; }
.numero .valor { font-size: 32px; font-weight: 650; letter-spacing: -.02em; line-height: 1.15; margin-top: 4px; }
.numero .valor small { font-size: 14px; font-weight: 500; letter-spacing: 0; color: var(--tinta-2); }
.numero .detalhe { color: var(--tinta-2); font-size: 13px; margin-top: 4px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 999px; font-size: 12px;
  font-weight: 600; border: 1px solid var(--borda); background: var(--superficie-2); color: var(--tinta-2);
  white-space: nowrap; }
.chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.chip.ok { color: var(--ok); background: var(--ok-fundo); border-color: var(--ok-borda); }
.chip.pendente { color: var(--pendente); background: var(--pendente-fundo); border-color: var(--pendente-borda); }
.chip.problema { color: var(--problema); background: var(--problema-fundo); border-color: var(--problema-borda); }
.aviso { border-radius: 10px; padding: 12px 16px; border: 1px solid var(--borda); background: var(--superficie);
  margin-top: 12px; }
.aviso.problema { background: var(--problema-fundo); border-color: var(--problema-borda); color: var(--problema); }
.aviso.pendente { background: var(--pendente-fundo); border-color: var(--pendente-borda); color: var(--pendente); }
.aviso.ok { background: var(--ok-fundo); border-color: var(--ok-borda); color: var(--ok); }
.aviso strong { display: block; margin-bottom: 2px; }
.aviso ul { margin: 6px 0 0; padding-left: 18px; }
.vazia { color: var(--tinta-2); background: var(--superficie); border: 1px dashed var(--borda-forte);
  border-radius: 10px; padding: 18px 20px; margin: 0; }
details > summary { cursor: pointer; color: var(--acento-tinta); font-weight: 500; list-style: none;
  display: inline-flex; align-items: center; gap: 6px; }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "▸"; font-size: 11px; transition: transform .15s; }
details[open] > summary::before { transform: rotate(90deg); }
details.bloco { margin-top: 16px; }
details.bloco > .dentro { margin-top: 12px; }
.tabela { width: 100%; overflow: hidden; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 9px 12px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--borda);
  overflow-wrap: anywhere; }
thead th { font-size: 12px; font-weight: 600; color: var(--tinta-2); background: var(--superficie-2);
  overflow-wrap: normal; }
tbody tr:last-child td { border-bottom: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.compacta th, table.compacta td { padding: 6px 10px; font-size: 13px; }
.forte { font-weight: 600; }
.suave { color: var(--tinta-2); }
button, .botao { font: inherit; font-weight: 600; font-size: 13px; border-radius: 8px; padding: 7px 14px;
  border: 1px solid var(--borda-forte); background: var(--superficie); color: var(--tinta); cursor: pointer;
  text-decoration: none; display: inline-flex; align-items: center; gap: 6px; line-height: 1.3;
  white-space: nowrap; }
button:hover, .botao:hover { background: var(--superficie-2); border-color: var(--tinta-3); }
button.primario, .botao.primario { background: var(--acento); border-color: var(--acento); color: #fff; }
button.primario:hover, .botao.primario:hover { background: var(--acento-tinta); border-color: var(--acento-tinta); }
button.confirmar { color: var(--ok); border-color: var(--ok-borda); background: var(--ok-fundo); }
button.discreto { border-color: transparent; background: transparent; color: var(--tinta-2); padding: 7px 8px; }
button.discreto:hover { color: var(--problema); background: var(--problema-fundo); }
button:disabled { opacity: .5; cursor: not-allowed; }
input[type="text"], input:not([type]) { font: inherit; padding: 6px 10px; border-radius: 8px;
  border: 1px solid var(--borda-forte); background: var(--superficie); color: var(--tinta); min-width: 0; }
input:focus-visible, button:focus-visible, summary:focus-visible, a:focus-visible {
  outline: 2px solid var(--acento); outline-offset: 2px; }
form { margin: 0; }
form.em-linha { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.botoes { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.identificador { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
form.em-linha label { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--tinta-2); }
a { color: var(--acento-tinta); }
.grafico { overflow: hidden; }
svg { max-width: 100%; height: auto; display: block; }
svg text { fill: var(--tinta); font-size: 12px; font-family: inherit; }
svg text.valor { fill: var(--tinta-2); font-variant-numeric: tabular-nums; }
svg .marca-da-barra { fill: var(--barra); }
svg line.base { stroke: var(--borda-forte); stroke-width: 1; }
svg g.barra:hover .marca-da-barra { opacity: .8; }
.duas-colunas { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
#recusa { color: var(--problema); font-weight: 600; }
.espaco { margin-top: 14px; }
h3.sem-margem { margin-top: 0; }
details.linha { margin-top: 6px; font-size: 13px; }
details.linha > .dentro { margin-top: 8px; }
dl.explicacao { display: grid; grid-template-columns: 110px 1fr; gap: 4px 12px; margin: 0; padding: 12px 14px;
  background: var(--superficie-2); border: 1px solid var(--borda); border-radius: 8px; font-size: 13px; }
dl.explicacao dt { color: var(--tinta-2); font-weight: 600; }
dl.explicacao dd { margin: 0; overflow-wrap: anywhere; }
.decisao-registrada { display: flex; flex-direction: column; gap: 4px; align-items: flex-start; font-size: 13px; }
.cartoes { display: flex; flex-direction: column; gap: 12px; }
.item-da-fila { padding: 16px 20px; border-left: 4px solid var(--pendente-borda); }
.item-da-fila.decidido { border-left-color: var(--ok); }
.cabeca-do-item { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.pagador { font-weight: 650; font-size: 15px; overflow-wrap: anywhere; }
.valor-do-item { font-size: 20px; font-weight: 650; letter-spacing: -.01em; white-space: nowrap;
  font-variant-numeric: tabular-nums; }
.motivo { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-top: 10px; }
.sugerido { margin-top: 8px; }
.parecer { margin-top: 12px; padding: 10px 14px; border-radius: 8px; background: var(--ia-fundo);
  border: 1px solid var(--ia-borda); }
.parecer ul { margin: 6px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
.parecer.indisponivel { background: var(--problema-fundo); border-color: var(--problema-borda); }
.acoes-da-linha { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.rotulo-da-ia { color: var(--ia); font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.ia-indisponivel { color: var(--problema); font-weight: 700; font-size: 12px; text-transform: uppercase;
  letter-spacing: .04em; }
.decisoes { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--borda); }
.mais-decisoes { display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start; }
.item-da-fila .decisao-registrada { margin-bottom: 4px; }
.encargos { display: flex; gap: 4px; justify-content: flex-end; flex-wrap: wrap; margin-top: 4px; }
.etiqueta { font-size: 12px; font-weight: 600; padding: 1px 8px; border-radius: 6px; white-space: nowrap;
  color: var(--pendente); background: var(--pendente-fundo); border: 1px solid var(--pendente-borda); }
.alerta-de-duplicidade { margin-top: 6px; padding: 6px 10px; border-radius: 8px; font-size: 13px;
  color: var(--problema); background: var(--problema-fundo); border: 1px solid var(--problema-borda); }
.alerta-de-duplicidade a { color: inherit; font-weight: 600; }
tr.destacada td { background: var(--ok-fundo); }
tr.destacada td:first-child { box-shadow: inset 4px 0 0 var(--ok); }
.sem-quebra { white-space: nowrap; }
.enderecado { display: inline-block; margin-bottom: 4px; padding: 2px 10px;
  border-radius: 8px; font-size: 12px; font-weight: 700; color: var(--ok); background: var(--superficie);
  border: 1px solid var(--ok-borda); }
.simulacao { border: 2px dashed var(--pendente); background: var(--pendente-fundo); color: var(--pendente);
  border-radius: 10px; padding: 12px 16px; margin-top: 16px; }
.simulacao strong { text-transform: uppercase; letter-spacing: .06em; margin-right: 6px; }
.passos { display: flex; flex-direction: column; gap: 12px; }
.passo { padding: 16px 20px; display: grid; grid-template-columns: 36px 1fr; gap: 4px 14px; align-items: start; }
.passo .ordem { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; font-weight: 700;
  background: var(--acento-fundo); color: var(--acento-tinta); }
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
        f'<body><header class="topo"><div class="topo-dentro"><div class="marca">Vantara <span>Contas a receber'
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
