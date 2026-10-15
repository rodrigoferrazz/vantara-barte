from collections.abc import Mapping, Sequence
from datetime import date
from html import escape

from conciliacao.dominio import (
    BaixaManual,
    Canal,
    DecisaoDaTela,
    Item,
    ItemDeTitulo,
    MotivoDeNaoIdentificacao,
    RegraDaProposta,
    Resposta,
    Resultado,
    Resumo,
    TipoDeDecisao,
    TipoDeEvidencia,
    Titulo,
)
from conciliacao.encargo import ParametrosDeEncargo, multa_e_juros
from conciliacao.normalizacao import formatar_percentual, formatar_reais
from conciliacao.pagina import (
    Estado,
    Numero,
    Visao,
    aviso,
    cabecalho_da_pagina,
    campo_oculto,
    chip,
    detalhes,
    documento,
    numeros,
    secao,
    tabela,
    vazia,
)
from conciliacao.saidas import ABA_DA_FILA_DE_EXCECOES, ABA_DA_LISTA_DE_BAIXA, descrever_titulos, linhas_do_resumo

POR_QUE_DA_REGRA = {
    RegraDaProposta.NOSSO_NUMERO_E_VALOR: "O nosso número do boleto aponta o título e o valor bate.",
    RegraDaProposta.DOCUMENTO_E_VALOR_UNICO: "O CNPJ do pagador é do franqueado e o valor bate com um único título.",
    RegraDaProposta.DOCUMENTO_E_SOMA_EXATA: "O CNPJ do pagador é do franqueado e a soma dos títulos fecha o valor.",
    RegraDaProposta.PAGADOR_CONHECIDO_E_VALOR_UNICO: (
        "Pagador já confirmado antes e o valor bate com um único título."
    ),
    RegraDaProposta.PAGADOR_CONHECIDO_E_SOMA_EXATA: "Pagador já confirmado antes e a soma dos títulos fecha o valor.",
    RegraDaProposta.IDENTIFICADOR_E_VALOR: "O Pix ou boleto da plataforma aponta o título e o valor bate.",
}

MOTIVO_EM_LINGUAGEM_SIMPLES = {
    MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR: (
        "Não dá pra saber quem pagou: o extrato não traz CNPJ nem um nome que bata com algum franqueado."
    ),
    MotivoDeNaoIdentificacao.NOME_AMBIGUO: "O nome do pagador serve pra mais de um franqueado.",
    MotivoDeNaoIdentificacao.VALOR_NAO_FECHA: "Sabemos quem pagou, mas o valor não bate com o título.",
    MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO: (
        "Sabemos quem pagou, mas o franqueado não tem título em aberto pra esse pagamento."
    ),
    MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO: "Mais de um título, ou soma de títulos, fecha esse valor.",
    MotivoDeNaoIdentificacao.POSSIVEL_DUPLICIDADE: "O mesmo título parece estar lançado em dois sistemas.",
    MotivoDeNaoIdentificacao.POSSIVEL_FONTE_NAO_INTEGRADA: (
        "Parece pagar um título de fora da plataforma, como as planilhas da terceira unidade."
    ),
    MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ: (
        "O nome bate com o franqueado, mas é a primeira vez que esse pagador aparece."
    ),
}

_ROTULOS_DAS_DECISOES = {
    TipoDeDecisao.CONFIRMAR: "Confirmado",
    TipoDeDecisao.REJEITAR: "Rejeitado",
    TipoDeDecisao.ANTECIPACAO: "Antecipação",
    TipoDeDecisao.DEVOLUCAO: "Devolução",
    TipoDeDecisao.ERRO: "Erro",
    TipoDeDecisao.CONCILIADO_FORA: "Conciliado fora",
    TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA: "Fonte não integrada",
    TipoDeDecisao.MESMA_DIVIDA: "Mesma dívida",
    TipoDeDecisao.DIVIDAS_DISTINTAS: "Dívidas distintas",
}

_BOTOES_DA_FILA = {
    TipoDeDecisao.ANTECIPACAO: "Antecipação",
    TipoDeDecisao.DEVOLUCAO: "Devolução",
    TipoDeDecisao.ERRO: "Erro",
    TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA: "Fonte não integrada",
}


_MEIO_DO_PAGAMENTO_ENDERECADO: Mapping[Canal | None, str] = {Canal.PIX: "o Pix", Canal.BOLETO: "o boleto"}


type _Duplicidades = Mapping[tuple[str, str], ItemDeTitulo]


def renderizar_analista(
    resultado: Resultado | None,
    decididos_na_tela: Mapping[str, DecisaoDaTela],
    arquivos_na_entrada: Sequence[str],
    excel_disponivel: bool,
    encargo: ParametrosDeEncargo | None,
) -> str:
    titulo = "Conciliação"
    if resultado is None:
        corpo = (
            cabecalho_da_pagina(titulo, "Ainda não houve conciliação.")
            + _arquivos(None, arquivos_na_entrada, 0)
            + secao(
                "Resumo",
                "secao-resumo",
                vazia(
                    "Não há execução registrada. Envie os extratos e as exportações e clique em Conciliar.",
                    "sem-execucao",
                ),
            )
        )
        return documento(titulo, corpo, Visao.ANALISTA)
    resumo = resultado.resumo
    duplicidades = {
        (titulo.sistema_de_origem, titulo.documento): item for item in resultado.itens_de_titulo for titulo in item.titulos
    }
    return documento(
        f"{titulo} - execução {resumo.execucao}",
        cabecalho_da_pagina(titulo, _subtitulo(resumo))
        + _arquivos(resultado, arquivos_na_entrada, len(decididos_na_tela))
        + _resumo(resultado, decididos_na_tela)
        + _lista_de_baixa(resultado.lista_de_baixa, decididos_na_tela, duplicidades, encargo)
        + _fila(resultado.fila_de_excecoes, resultado.itens_de_titulo, decididos_na_tela, duplicidades)
        + _baixa_manual(resultado.baixa_manual, excel_disponivel),
        Visao.ANALISTA,
    )


def _subtitulo(resumo: Resumo) -> str:
    referencia = resumo.data_de_referencia.data
    partes = [f"Execução {resumo.execucao}"]
    if referencia is not None:
        partes.append(f"extrato até {referencia:%d/%m/%Y}")
    return " · ".join(partes)


def _arquivos(resultado: Resultado | None, nomes: Sequence[str], decisoes_pendentes: int) -> str:
    lidos = set(resultado.resumo.arquivos_lidos) if resultado else set()
    recusados = {r.nome: r.motivo for r in resultado.resumo.arquivos_recusados} if resultado else {}
    envio = (
        '<form method="post" action="/enviar" enctype="multipart/form-data" class="em-linha" id="enviar-arquivos">'
        '<input type="file" name="arquivos" multiple required aria-label="Arquivos">'
        '<button type="submit">Enviar arquivos</button></form>'
    )
    linhas = [
        (
            f'<span class="forte">{escape(nome)}</span>'
            + (f'<div class="suave">{escape(recusados[nome])}</div>' if nome in recusados else ""),
            _situacao_do_arquivo(nome, lidos, recusados),
            '<form method="post" action="/remover-arquivo">'
            f'{campo_oculto("nome", nome)}<button class="discreto" type="submit">Remover</button></form>',
        )
        for nome in nomes
    ]
    lista = (
        tabela(("Arquivo", "Situação", ""), linhas, "arquivos-na-entrada", compacta=True)
        if linhas
        else vazia("Nenhum arquivo enviado ainda.", "sem-arquivos")
    )
    if decisoes_pendentes:
        efeito = f"Aplica as {decisoes_pendentes} decisão(ões) feitas na tela e gera o Excel."
    else:
        efeito = "Concilia os arquivos acima e gera o Excel."
    desabilitado = "" if nomes else " disabled"
    conciliar = (
        '<form method="post" action="/conciliar" class="em-linha" id="conciliar">'
        f'<button class="primario" type="submit"{desabilitado}>Conciliar</button>'
        f'<span class="suave">{escape(efeito)}</span></form>'
    )
    conteudo = (
        f'<div class="cartao com-folga">{envio}<div class="espaco">{lista}</div>'
        f'<div class="espaco">{conciliar}</div></div>'
    )
    return secao(
        "Arquivos",
        "arquivos",
        conteudo,
        nota="Extratos do banco e exportações do Protheus e do Omie. Arquivo com o mesmo nome substitui o anterior.",
    )


def _situacao_do_arquivo(nome: str, lidos: set[str], recusados: Mapping[str, str]) -> str:
    if nome in recusados:
        return chip("Não reconhecido", Estado.PROBLEMA)
    if nome in lidos:
        return chip("Lido na última conciliação", Estado.OK)
    return chip("Novo", Estado.PENDENTE)


def _resumo(resultado: Resultado, decididos: Mapping[str, DecisaoDaTela]) -> str:
    resumo = resultado.resumo
    pra_confirmar = [item for item in resultado.lista_de_baixa if item.identificador not in decididos]
    pra_resolver = [item for item in resultado.fila_de_excecoes if item.identificador not in decididos]
    duplicidades_pra_resolver = [item for item in resultado.itens_de_titulo if item.identificador not in decididos]
    parte = resumo.parte_automatica
    automatico = (
        f"{formatar_percentual(parte.percentual_da_quantidade)} resolvido sozinho"
        if parte.percentual_da_quantidade is not None
        else "nenhum Crédito para conciliar"
    )
    blocos = numeros(
        Numero(
            "Pra confirmar",
            str(len(pra_confirmar)),
            f"{formatar_reais(sum(i.lancamento.valor_centavos for i in pra_confirmar))} · {automatico}",
            Estado.PENDENTE if pra_confirmar else Estado.OK,
            "pra-confirmar",
        ),
        Numero(
            "Pra resolver",
            str(len(pra_resolver)),
            f"{formatar_reais(sum(i.lancamento.valor_centavos for i in pra_resolver))} em pagamentos",
            Estado.PENDENTE if pra_resolver or duplicidades_pra_resolver else Estado.OK,
            "pra-resolver",
            _quantos_resolver(len(pra_resolver), len(duplicidades_pra_resolver)),
        ),
        Numero(
            "Pra baixar no ERP",
            str(len(resultado.baixa_manual)),
            "confirmados nesta conciliação",
            Estado.PENDENTE if resultado.baixa_manual else Estado.NEUTRO,
            "pra-baixar",
        ),
    )
    alertas = ""
    if resumo.itens_ia_indisponivel:
        alertas += aviso(
            "IA indisponível",
            f"{_plural(resumo.itens_ia_indisponivel, 'item ficou', 'itens ficaram')} sem parecer da IA. "
            "Vale chamar o TI.",
            Estado.PROBLEMA,
            "situacao-da-ia",
        )
    if resumo.alerta_de_queda is not None:
        alertas += aviso("Queda da parte automática", resumo.alerta_de_queda, Estado.PROBLEMA, "alerta-de-queda")
    if resumo.decisoes.conflitos:
        alertas += aviso(
            "Conflitos entre Excel e tela",
            "Nenhuma das decisões destes itens foi aplicada; decida de novo por uma só origem.",
            Estado.PROBLEMA,
            "conflitos",
            resumo.decisoes.conflitos,
        )
    if resumo.decisoes.nao_aplicadas:
        alertas += aviso(
            "Decisões não aplicadas na última conciliação",
            "",
            Estado.PENDENTE,
            "nao-aplicadas",
            resumo.decisoes.nao_aplicadas,
        )
    completo = "".join(
        f"<tr><th>{escape(rotulo)}</th><td>{escape(str(valor))}</td></tr>" for rotulo, valor in linhas_do_resumo(resultado)
    )
    resumo_completo = detalhes(
        "Ver o resumo completo",
        f'<div class="cartao tabela"><table id="resumo" class="compacta"><tbody>{completo}</tbody></table></div>',
    )
    return secao("Resumo", "secao-resumo", alertas + blocos + _situacao_da_ia(resumo) + resumo_completo)


def _quantos_resolver(pagamentos: int, duplicidades: int) -> str:
    texto = "pagamento" if pagamentos == 1 else "pagamentos"
    if duplicidades:
        texto += f" + {_plural(duplicidades, 'duplicidade', 'duplicidades')}"
    return texto


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _situacao_da_ia(resumo: Resumo) -> str:
    if resumo.itens_ia_indisponivel:
        return ""
    if resumo.itens_com_parecer:
        situacao = chip("IA funcionando", Estado.OK)
        detalhe = f"{_plural(resumo.itens_com_parecer, 'item', 'itens')} com parecer"
    else:
        situacao = chip("IA não precisou", Estado.NEUTRO)
        detalhe = "nenhum nome pra analisar"
    return f'<p class="situacao-da-ia" id="situacao-da-ia">{situacao}<span>{escape(detalhe)}</span></p>'


def _lista_de_baixa(
    itens: Sequence[Item],
    decididos: Mapping[str, DecisaoDaTela],
    duplicidades: _Duplicidades,
    encargo: ParametrosDeEncargo | None,
) -> str:
    if not itens:
        return secao("Lista de baixa", "lista-de-baixa", vazia("Nada pra confirmar."))
    faltam = sum(1 for item in itens if item.identificador not in decididos)
    acoes = (
        '<form method="post" action="/confirmar-lote" id="confirmar-todos">'
        f'<button class="primario" type="submit"{"" if faltam else " disabled"}>Confirmar todos ({faltam})</button>'
        "</form>"
    )
    linhas = [
        (
            f'<span class="forte">{escape(_franqueados(item.titulos))}</span>',
            escape(_documentos(item.titulos)) + _aviso_de_duplicidade(item.titulos, duplicidades),
            f'{item.lancamento.data:%d/%m/%Y}<div class="suave">{escape(item.lancamento.historico)}</div>',
            _valor_da_lista(item, encargo),
            _marca_de_enderecado(item)
            + escape(_por_que(item))
            + detalhes("ver detalhes", _detalhes_do_item(item), "linha"),
            _decisao_da_lista(item, decididos.get(item.identificador)),
        )
        for item in itens
    ]
    return secao(
        "Lista de baixa",
        "lista-de-baixa",
        tabela(
            ("Franqueado", "Título", "Crédito", "Valor", "Por quê", "Decisão"),
            linhas,
            "itens-da-lista",
            numericas=(3,),
            destacadas=[posicao for posicao, item in enumerate(itens) if _enderecado(item)],
        ),
        acoes,
        "Propostas que fecharam pelas regras. Confirmar todos confirma as que ainda não têm decisão; "
        "as decisões valem na próxima conciliação.",
    )


def _enderecado(item: Item) -> bool:
    return TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA in item.evidencia


def _marca_de_enderecado(item: Item) -> str:
    if not _enderecado(item):
        return ""
    meio = _MEIO_DO_PAGAMENTO_ENDERECADO.get(item.canal, "o Pix ou o boleto")
    return f'<div class="enderecado">Pagamento endereçado: {escape(meio)} já dizia a fatura</div>'


def _valor_da_lista(item: Item, parametros: ParametrosDeEncargo | None) -> str:
    credito = item.lancamento
    principal = sum(titulo.valor_centavos for titulo in item.titulos)
    encargo = credito.valor_centavos - principal
    if len(item.titulos) != 1 or encargo <= 0:
        return formatar_reais(credito.valor_centavos)
    etiquetas = "".join(
        f'<span class="etiqueta">+ {rotulo} {formatar_reais(valor)}</span>'
        for rotulo, valor in _partes_do_encargo(item.titulos[0], credito.data, encargo, parametros)
        if valor
    )
    return (
        f'{formatar_reais(principal)}<div class="encargos">{etiquetas}</div>'
        f'<div class="suave">crédito {formatar_reais(credito.valor_centavos)}</div>'
    )


def _partes_do_encargo(
    titulo: Titulo, data: date, encargo: int, parametros: ParametrosDeEncargo | None
) -> tuple[tuple[str, int], ...]:
    """Multa primeiro, até a prevista; o resto do Encargo pago é juros."""
    if parametros is None:
        return (("encargo", encargo),)
    multa_prevista, _ = multa_e_juros(titulo.valor_centavos, titulo.vencimento, data, parametros)
    multa = min(multa_prevista, encargo)
    return (("multa", multa), ("juros", encargo - multa))


def _aviso_de_duplicidade(titulos: Sequence[Titulo], duplicidades: _Duplicidades) -> str:
    avisos = []
    for titulo in titulos:
        duplicidade = duplicidades.get((titulo.sistema_de_origem, titulo.documento))
        if duplicidade is None:
            continue
        outros = descrever_titulos(tuple(t for t in duplicidade.titulos if t != titulo))
        avisos.append(
            f'<div class="alerta-de-duplicidade">{escape(descrever_titulos((titulo,)))} pode ser a mesma dívida que '
            f'<a href="#item-{escape(duplicidade.identificador)}">{escape(outros)}</a>, '
            "em possível duplicidade na fila. Resolva as duas.</div>"
        )
    return "".join(avisos)


def _franqueados(titulos: Sequence[Titulo]) -> str:
    return ", ".join(dict.fromkeys(titulo.nome_do_franqueado for titulo in titulos)) or "-"


def _documentos(titulos: Sequence[Titulo]) -> str:
    return descrever_titulos(tuple(titulos)) or "-"


def _por_que(item: Item) -> str:
    if item.regra is not None:
        return POR_QUE_DA_REGRA[item.regra]
    return "; ".join(tipo.value for tipo in item.evidencia)


def _decisao_da_lista(item: Item, decidida: DecisaoDaTela | None) -> str:
    confirmar = _formulario(
        ABA_DA_LISTA_DE_BAIXA,
        item.identificador,
        campo_oculto("decisao", TipoDeDecisao.CONFIRMAR.value),
        '<button class="confirmar" type="submit">Confirmar</button>',
    )
    rejeitar = detalhes(
        "Rejeitar",
        _formulario(
            ABA_DA_LISTA_DE_BAIXA,
            item.identificador,
            campo_oculto("decisao", TipoDeDecisao.REJEITAR.value)
            + '<input name="motivo" required placeholder="Motivo da rejeição" aria-label="Motivo da rejeição">',
            '<button type="submit">Rejeitar</button>',
        ),
        "linha",
    )
    if decidida is None:
        return f'<div class="acoes-da-linha">{confirmar}{rejeitar}</div>'
    return _decidido(decidida) + detalhes("Mudar", confirmar + rejeitar, "linha")


def _decidido(decisao: DecisaoDaTela) -> str:
    linha = decisao.linha
    tipo = next((t for t in TipoDeDecisao if t.value == linha.decisao), None)
    rotulo = _ROTULOS_DAS_DECISOES.get(tipo, linha.decisao) if tipo is not None else linha.decisao
    estado = Estado.PROBLEMA if tipo is TipoDeDecisao.REJEITAR else Estado.OK
    complementos = [
        texto
        for texto in (
            linha.motivo,
            f"Título(s): {linha.titulos}" if linha.titulos else "",
            f"Franqueado {linha.franqueado}" if linha.franqueado else "",
            f"referência {linha.referencia}" if linha.referencia else "",
        )
        if texto
    ]
    quem = f"por {decisao.autor} em {decisao.momento:%d/%m %H:%M}"
    texto = " · ".join((*complementos, quem))
    return f'<div class="decisao-registrada">{chip(rotulo, estado)}<div class="suave">{escape(texto)}</div></div>'


def _formulario(aba: str, item: str, campos: str, botoes: str) -> str:
    return (
        '<form method="post" action="/decidir" class="em-linha">'
        f"{campo_oculto('aba', aba)}{campo_oculto('item', item)}{campos}{botoes}</form>"
    )


def _detalhes_do_item(item: Item) -> str:
    lancamento = item.lancamento
    credito = [
        f"{lancamento.banco} {lancamento.conta}",
        f"{lancamento.data:%d/%m/%Y}",
        lancamento.historico,
    ]
    if lancamento.documento:
        credito.append(f"documento {lancamento.documento}")
    credito.append(formatar_reais(lancamento.valor_centavos))
    linhas = [
        ("Item", item.identificador),
        ("Crédito", ", ".join(credito)),
        ("Evidência", "; ".join(tipo.value for tipo in item.evidencia) or "-"),
    ]
    if item.motivo is not None:
        linhas.append(("Motivo", item.motivo.value))
        linhas.append(("O que falta", item.motivo.o_que_falta))
    linhas.append(("Explicação", item.explicacao))
    return '<dl class="explicacao">' + "".join(f"<dt>{escape(r)}</dt><dd>{escape(v)}</dd>" for r, v in linhas) + "</dl>"


def _fila(
    itens: Sequence[Item],
    itens_de_titulo: Sequence[ItemDeTitulo],
    decididos: Mapping[str, DecisaoDaTela],
    duplicidades: _Duplicidades,
) -> str:
    if not itens and not itens_de_titulo:
        return secao("Fila de exceções", "fila-de-excecoes", vazia("Nada pra resolver."))
    cartoes = "".join(
        _cartao_de_credito(item, decididos.get(item.identificador), duplicidades) for item in itens
    ) + "".join(
        _cartao_de_titulo(item, decididos.get(item.identificador)) for item in itens_de_titulo
    )
    return secao(
        "Fila de exceções",
        "fila-de-excecoes",
        f'<div class="cartoes">{cartoes}</div>',
        nota="Casos que precisam da sua decisão antes de qualquer baixa. As decisões valem na próxima conciliação.",
    )


def _cartao_de_credito(item: Item, decidida: DecisaoDaTela | None, duplicidades: _Duplicidades) -> str:
    lancamento = item.lancamento
    classes = "cartao item-da-fila" + (" com-parecer" if item.pareceres else "") + (" decidido" if decidida else "")
    motivo = item.motivo
    cabeca = (
        '<div class="cabeca-do-item"><div>'
        f'<div class="pagador">{escape(lancamento.historico)}</div>'
        f'<div class="suave">{lancamento.data:%d/%m/%Y} · {escape(lancamento.banco)} {escape(lancamento.conta)}</div>'
        f'</div><div class="valor-do-item">{formatar_reais(lancamento.valor_centavos)}</div></div>'
    )
    por_que = (
        f'<div class="motivo">{chip(motivo.value, Estado.PENDENTE) if motivo else ""}'
        f"<span>{escape(MOTIVO_EM_LINGUAGEM_SIMPLES[motivo]) if motivo else ''}</span></div>"
    )
    sugerido = (
        f'<div class="sugerido"><span class="suave">Título sugerido</span> {_titulos_sugeridos(item.titulos)}</div>'
        + _aviso_de_duplicidade(item.titulos, duplicidades)
    )
    corpo = cabeca + por_que + sugerido + _parecer(item)
    decisao = _decidido(decidida) + detalhes("Mudar a decisão", _decisoes_do_credito(item), "linha") if decidida else (
        _decisoes_do_credito(item)
    )
    return (
        f'<article class="{classes}" id="item-{escape(item.identificador)}">{corpo}'
        f'<div class="decisoes">{decisao}</div>'
        f"{detalhes('ver detalhes', _detalhes_do_item(item), 'linha')}</article>"
    )


def _titulos_sugeridos(titulos: Sequence[Titulo]) -> str:
    if not titulos:
        return '<span class="suave">nenhum</span>'
    return "; ".join(
        f'<span class="forte">{escape(t.documento)}</span> ({escape(t.sistema_de_origem)}) · '
        f"{escape(t.nome_do_franqueado)} · {formatar_reais(t.valor_centavos)} · vence {t.vencimento:%d/%m/%Y}"
        for t in titulos
    )


def _parecer(item: Item) -> str:
    if not item.pareceres:
        return ""
    nomes = {titulo.franqueado: titulo.nome_do_franqueado for titulo in item.titulos}
    if item.ia_indisponivel:
        linhas = "".join(
            f"<li>{escape(nomes.get(p.franqueado, f'raiz {p.franqueado}'))}: {escape(p.parecer.explicacao)}</li>"
            for p in item.pareceres
        )
        return f'<div class="parecer indisponivel"><span class="ia-indisponivel">IA indisponível</span><ul>{linhas}</ul></div>'
    linhas = "".join(
        "<li>"
        + chip(parecer.parecer.resposta.value, Estado.OK if parecer.parecer.resposta is Resposta.SIM else Estado.PROBLEMA)
        + f" <span class=\"forte\">{escape(nomes.get(parecer.franqueado, f'raiz {parecer.franqueado}'))}</span>: "
        f"{escape(parecer.parecer.explicacao)}</li>"
        for parecer in item.pareceres
    )
    return f'<div class="parecer"><span class="rotulo-da-ia">Parecer da IA</span><ul>{linhas}</ul></div>'


def _decisoes_do_credito(item: Item) -> str:
    principais = ""
    if item.titulos:
        principais += (
            f'<button class="confirmar" type="submit" name="decisao" value="{TipoDeDecisao.CONFIRMAR.value}">'
            "Confirmar o sugerido</button>"
        )
    principais += "".join(
        f'<button type="submit" name="decisao" value="{escape(tipo.value)}">{escape(rotulo)}</button>'
        for tipo, rotulo in _BOTOES_DA_FILA.items()
    )
    outro_titulo = detalhes(
        "Confirmar outro título",
        _formulario(
            ABA_DA_FILA_DE_EXCECOES,
            item.identificador,
            campo_oculto("decisao", TipoDeDecisao.CONFIRMAR.value)
            + '<input name="titulos" required placeholder="NF 1 (Protheus); NF 2 (Protheus)" '
            'aria-label="Título(s) escolhido(s)">',
            '<button type="submit">Confirmar</button>',
        ),
        "linha",
    )
    conciliado_fora = detalhes(
        "Conciliado fora",
        _formulario(
            ABA_DA_FILA_DE_EXCECOES,
            item.identificador,
            campo_oculto("decisao", TipoDeDecisao.CONCILIADO_FORA.value)
            + '<input name="franqueado" required placeholder="CNPJ do franqueado" aria-label="CNPJ do Franqueado">'
            + '<input name="referencia" required placeholder="Referência" aria-label="Referência">',
            '<button type="submit">Registrar</button>',
        ),
        "linha",
    )
    return (
        _formulario(ABA_DA_FILA_DE_EXCECOES, item.identificador, "", principais)
        + f'<div class="mais-decisoes">{outro_titulo}{conciliado_fora}</div>'
    )


def _cartao_de_titulo(item: ItemDeTitulo, decidida: DecisaoDaTela | None) -> str:
    oficiais = "".join(
        f'<button type="submit" name="titulos" value="{escape(descrever_titulos((titulo,)))}">'
        f"Mesma dívida, fica {escape(titulo.documento)} ({escape(titulo.sistema_de_origem)})</button>"
        for titulo in item.titulos
    )
    mesma = _formulario(
        ABA_DA_FILA_DE_EXCECOES, item.identificador, campo_oculto("decisao", TipoDeDecisao.MESMA_DIVIDA.value), oficiais
    )
    distintas = _formulario(
        ABA_DA_FILA_DE_EXCECOES,
        item.identificador,
        campo_oculto("decisao", TipoDeDecisao.DIVIDAS_DISTINTAS.value),
        '<button type="submit">Dívidas distintas</button>',
    )
    botoes = f'<div class="em-linha">{mesma}{distintas}</div>'
    primeiro = item.titulos[0] if item.titulos else None
    cabeca = (
        '<div class="cabeca-do-item"><div>'
        f'<div class="pagador">{escape(primeiro.nome_do_franqueado if primeiro else "")}</div>'
        f'<div class="suave">{len(item.titulos)} títulos com o mesmo valor e vencimento</div>'
        f'</div><div class="valor-do-item">{formatar_reais(primeiro.valor_centavos) if primeiro else ""}</div></div>'
    )
    por_que = (
        f'<div class="motivo">{chip(item.motivo.value, Estado.PENDENTE)}'
        f"<span>{escape(MOTIVO_EM_LINGUAGEM_SIMPLES[item.motivo])}</span></div>"
    )
    sugerido = f'<div class="sugerido"><span class="suave">Títulos</span> {_titulos_sugeridos(item.titulos)}</div>'
    decisao = _decidido(decidida) + detalhes("Mudar a decisão", botoes, "linha") if decidida else botoes
    explicacao = (
        f'<dl class="explicacao"><dt>Item</dt><dd>{escape(item.identificador)}</dd>'
        f"<dt>O que falta</dt><dd>{escape(item.motivo.o_que_falta)}</dd>"
        f"<dt>Explicação</dt><dd>{escape(item.explicacao)}</dd></dl>"
    )
    classes = "cartao item-da-fila" + (" decidido" if decidida else "")
    return (
        f'<article class="{classes}" id="item-{escape(item.identificador)}">{cabeca}{por_que}{sugerido}'
        f'<div class="decisoes">{decisao}</div>{detalhes("ver detalhes", explicacao, "linha")}</article>'
    )


def _baixa_manual(baixas: Sequence[BaixaManual], excel_disponivel: bool) -> str:
    acoes = '<a class="botao" href="/excel" id="baixar-excel">Baixar o Excel</a>' if excel_disponivel else ""
    linhas = [
        (
            f'<span class="forte">{escape(baixa.titulo.documento)}</span>',
            escape(baixa.titulo.sistema_de_origem),
            escape(baixa.titulo.nome_do_franqueado),
            formatar_reais(baixa.principal_centavos),
            formatar_reais(baixa.encargo_centavos),
            f"{baixa.credito.data:%d/%m/%Y}",
            escape(baixa.item),
        )
        for baixa in baixas
    ]
    return secao(
        "Baixar no ERP",
        "baixa-manual",
        tabela(
            ("Título", "Sistema", "Franqueado", "Principal", "Encargo", "Pago em", "Item"),
            linhas,
            "itens-da-baixa-manual",
            numericas=(3, 4),
            vazia_com="Nada pra baixar no ERP nesta conciliação.",
        ),
        acoes,
        "Títulos confirmados nesta conciliação. A plataforma não dá baixa: baixe cada um no sistema de origem.",
    )
