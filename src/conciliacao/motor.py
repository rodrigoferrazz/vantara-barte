from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from conciliacao.dominio import (
    Classificacao,
    Destino,
    Franqueado,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    PossivelDuplicidade,
    TipoDeEvidencia,
    Titulo,
)
from conciliacao.encargo import Pagamento, ParametrosDeEncargo, enquadrar
from conciliacao.normalizacao import cnpjs_no_texto, formatar_reais, nome_normalizado, raiz_do_cnpj

type NomeDoPagador = Callable[[Lancamento], str | None]


@dataclass(frozen=True)
class _NomeDoFranqueado:
    raiz: str
    sistema_de_origem: str
    nome: str
    normalizado: str


@dataclass(frozen=True)
class _Titulos:
    todos: list[Titulo]
    por_nosso_numero: dict[str, list[Titulo]]
    por_franqueado: dict[str, list[Titulo]]
    nomes: list[_NomeDoFranqueado]
    encargo: ParametrosDeEncargo
    nome_do_pagador: NomeDoPagador

    @property
    def franqueados(self) -> set[str]:
        return {nome.raiz for nome in self.nomes}

    def que_fecham(self, titulos: list[Titulo], lancamento: Lancamento) -> list[tuple[Titulo, Pagamento]]:
        return [
            (titulo, pagamento)
            for titulo in titulos
            if (pagamento := enquadrar(titulo, lancamento.valor_centavos, lancamento.data, self.encargo)).fecha
        ]


def conciliar(
    titulos: Iterable[Titulo],
    lancamentos: Iterable[Lancamento],
    franqueados: Iterable[Franqueado],
    encargo: ParametrosDeEncargo,
    nome_do_pagador: NomeDoPagador,
) -> list[Classificacao]:
    todos = list(titulos)
    por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
    por_franqueado: dict[str, list[Titulo]] = defaultdict(list)
    for titulo in todos:
        if titulo.nosso_numero:
            por_nosso_numero[titulo.nosso_numero].append(titulo)
        por_franqueado[titulo.franqueado].append(titulo)
    abertos = _Titulos(
        todos, por_nosso_numero, por_franqueado, _nomes_dos_franqueados(franqueados, todos), encargo, nome_do_pagador
    )
    return [_classificar(lancamento, abertos) for lancamento in lancamentos]


def _nomes_dos_franqueados(franqueados: Iterable[Franqueado], titulos: list[Titulo]) -> list[_NomeDoFranqueado]:
    nomes = {
        (franqueado.raiz, sistema, nome)
        for franqueado in franqueados
        for sistema, nomes_no_sistema in franqueado.nomes.items()
        for nome in nomes_no_sistema
    } | {(titulo.franqueado, titulo.sistema_de_origem, titulo.cliente) for titulo in titulos}
    return [_NomeDoFranqueado(raiz, sistema, nome, nome_normalizado(nome)) for raiz, sistema, nome in sorted(nomes)]


def possiveis_duplicidades(titulos: Iterable[Titulo]) -> list[PossivelDuplicidade]:
    grupos: dict[tuple[str, date, int], list[Titulo]] = defaultdict(list)
    for titulo in titulos:
        grupos[(titulo.franqueado, titulo.vencimento, titulo.valor_centavos)].append(titulo)
    return [
        _possivel_duplicidade(franqueado, vencimento, valor, grupo)
        for (franqueado, vencimento, valor), grupo in sorted(grupos.items())
        if len({titulo.sistema_de_origem for titulo in grupo}) > 1
    ]


def _possivel_duplicidade(franqueado: str, vencimento: date, valor: int, grupo: list[Titulo]) -> PossivelDuplicidade:
    titulos = sorted(grupo, key=lambda titulo: (titulo.sistema_de_origem, titulo.documento))
    return PossivelDuplicidade(
        titulos=tuple(titulos),
        explicacao=(
            f"Títulos do Franqueado de raiz {franqueado} com o mesmo valor {formatar_reais(valor)} e vencimento "
            f"{vencimento:%d/%m/%Y} em Sistemas de origem diferentes: {_documentos(titulos)}. "
            "Podem ser a mesma dívida."
        ),
    )


def _classificar(lancamento: Lancamento, abertos: _Titulos) -> Classificacao:
    if lancamento.natureza is Natureza.DEBITO:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FORA_DO_ESCOPO,
            titulos=(),
            explicacao="Débito do Extrato; não é Crédito de Franqueado.",
        )
    candidatos = abertos.por_nosso_numero.get(lancamento.documento, []) if lancamento.documento else []
    if len(candidatos) == 1:
        return _por_nosso_numero(lancamento, candidatos[0], abertos.encargo)
    if candidatos:
        return _sem_identificacao(
            lancamento,
            f"O documento {lancamento.documento} é nosso número de mais de um Título em aberto: "
            f"{_documentos(candidatos)}.",
            (TipoDeEvidencia.NOSSO_NUMERO,),
        )
    documentos = [c for c in cnpjs_no_texto(lancamento.historico) if raiz_do_cnpj(c) in abertos.franqueados]
    raizes = {raiz_do_cnpj(c) for c in documentos}
    if len(raizes) == 1:
        franqueado = raiz_do_cnpj(documentos[0])
        return _por_documento(lancamento, documentos[0], abertos.por_franqueado.get(franqueado, []), abertos.encargo)
    if raizes:
        return _sem_identificacao(
            lancamento,
            f"Os CNPJs do histórico são de mais de um Franqueado: raízes {', '.join(sorted(raizes))}.",
            (TipoDeEvidencia.CNPJ_CPF,),
        )
    nome = abertos.nome_do_pagador(lancamento)
    normalizado = nome_normalizado(nome) if nome else ""
    por_prefixo = [n for n in abertos.nomes if normalizado and n.normalizado.startswith(normalizado)]
    if nome and por_prefixo:
        return _por_nome(lancamento, nome, por_prefixo, abertos)
    return _so_valor(lancamento, nome if normalizado else None, abertos)


def _sem_identificacao(
    lancamento: Lancamento,
    explicacao: str,
    evidencia: tuple[TipoDeEvidencia, ...],
    titulos: tuple[Titulo, ...] = (),
) -> Classificacao:
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=titulos,
        explicacao=explicacao,
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
        evidencia=evidencia,
    )


def _por_nome(
    lancamento: Lancamento, nome: str, por_prefixo: list[_NomeDoFranqueado], abertos: _Titulos
) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    nomes = ", ".join(f"{n.nome} ({n.sistema_de_origem}, raiz {n.raiz})" for n in por_prefixo)
    identificacao = f"Nome '{nome}' do Extrato é Nome por prefixo de {nomes}"
    franqueados = sorted({n.raiz for n in por_prefixo})
    titulos = [titulo for raiz in franqueados for titulo in abertos.por_franqueado.get(raiz, [])]
    que_fecham = {
        raiz: fecham
        for raiz in franqueados
        if (fecham := abertos.que_fecham(abertos.por_franqueado.get(raiz, []), lancamento))
    }

    def fila(motivo: MotivoDeNaoIdentificacao, explicacao: str, sugeridos: list[Titulo]) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=tuple(sugeridos),
            explicacao=f"{identificacao}; {explicacao}.",
            motivo=motivo,
            evidencia=(TipoDeEvidencia.NOME_POR_PREFIXO,),
        )

    if not titulos:
        return fila(MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO, "nenhum Título em aberto", [])
    if not que_fecham:
        detalhe = (
            f"; {enquadrar(titulos[0], lancamento.valor_centavos, lancamento.data, abertos.encargo).descrever()}"
            if len(titulos) == 1
            else ""
        )
        return fila(
            MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
            f"o valor {valor} não fecha com nenhum Título em aberto, considerando o Encargo: "
            f"{_documentos(titulos)}{detalhe}",
            titulos if len(titulos) == 1 else [],
        )
    if len(que_fecham) > 1:
        return fila(
            MotivoDeNaoIdentificacao.NOME_AMBIGUO,
            f"o valor {valor} fecha com Títulos de mais de um Franqueado: "
            f"{_documentos([titulo for fecham in que_fecham.values() for titulo, _ in fecham])}",
            [],
        )
    [fecham] = que_fecham.values()
    if len(fecham) > 1:
        return fila(
            MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
            f"o valor {valor} fecha com mais de um Título em aberto, considerando o Encargo: "
            f"{_documentos([titulo for titulo, _ in fecham])}",
            [],
        )
    [(titulo, pagamento)] = fecham
    return fila(
        MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
        f"o valor {valor} é Valor único: Título {titulo.documento} ({titulo.sistema_de_origem}), "
        f"{pagamento.descrever()}; o nome ainda não é Pagador conhecido",
        [titulo],
    )


def _so_valor(lancamento: Lancamento, nome: str | None, abertos: _Titulos) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    pagador = (
        f"Nome '{nome}' do Extrato não é Nome por prefixo de nenhum nome de Franqueado"
        if nome
        else "Crédito sem nome nem documento que identifique o pagador"
    )
    que_fecham = abertos.que_fecham(abertos.todos, lancamento)
    if not que_fecham:
        return _sem_identificacao(lancamento, f"{pagador}; o valor {valor} não fecha com nenhum Título em aberto.", ())
    if len(que_fecham) > 1:
        return _sem_identificacao(
            lancamento,
            f"{pagador}; só o valor {valor} aponta mais de um Título em aberto: "
            f"{_documentos([titulo for titulo, _ in que_fecham])}.",
            (TipoDeEvidencia.SO_VALOR,),
        )
    [(titulo, pagamento)] = que_fecham
    return _sem_identificacao(
        lancamento,
        f"{pagador}; só o valor {valor} aponta o Título {titulo.documento} ({titulo.sistema_de_origem}) "
        f"do Franqueado {titulo.cliente}, {pagamento.descrever()}.",
        (TipoDeEvidencia.SO_VALOR,),
        (titulo,),
    )


def _por_documento(
    lancamento: Lancamento, documento: str, titulos: list[Titulo], encargo: ParametrosDeEncargo
) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    pagador = f"CNPJ {documento} no histórico identifica o Franqueado de raiz {raiz_do_cnpj(documento)}"
    if not titulos:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(TipoDeEvidencia.CNPJ_CPF,),
            destino=Destino.FILA_DE_EXCECOES,
            titulos=(),
            explicacao=f"{pagador}, que não tem Título em aberto.",
            motivo=MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO,
        )
    que_fecham = [
        (titulo, pagamento)
        for titulo in titulos
        if (pagamento := enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo)).fecha
    ]
    if len(que_fecham) == 1:
        [(titulo, pagamento)] = que_fecham
        return Classificacao(
            lancamento=lancamento,
            evidencia=(TipoDeEvidencia.CNPJ_CPF,),
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=(
                f"{pagador}; o valor {valor} é Valor único entre os Títulos em aberto dele: "
                f"Título {titulo.documento} ({titulo.sistema_de_origem}), {pagamento.descrever()}."
            ),
        )
    mesmo_valor = [titulo for titulo, _ in que_fecham]
    if mesmo_valor:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(TipoDeEvidencia.CNPJ_CPF,),
            destino=Destino.FILA_DE_EXCECOES,
            titulos=(),
            explicacao=(
                f"{pagador}, mas o valor {valor} fecha com mais de um Título em aberto dele, considerando o Encargo: "
                f"{_documentos(mesmo_valor)}."
            ),
            motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        )
    detalhe = (
        f"; {enquadrar(titulos[0], lancamento.valor_centavos, lancamento.data, encargo).descrever()}"
        if len(titulos) == 1
        else ""
    )
    return Classificacao(
        lancamento=lancamento,
        evidencia=(TipoDeEvidencia.CNPJ_CPF,),
        destino=Destino.FILA_DE_EXCECOES,
        titulos=tuple(titulos) if len(titulos) == 1 else (),
        explicacao=(
            f"{pagador}, mas o valor {valor} não fecha com nenhum Título em aberto dele, considerando o Encargo: "
            f"{_documentos(titulos)}{detalhe}."
        ),
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
    )


def _documentos(titulos: list[Titulo]) -> str:
    return ", ".join(
        f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})" for titulo in titulos
    )


def _por_nosso_numero(lancamento: Lancamento, titulo: Titulo, encargo: ParametrosDeEncargo) -> Classificacao:
    pagamento = enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo)
    identificacao = (
        f"Nosso número {titulo.nosso_numero} é do Título {titulo.documento} ({titulo.sistema_de_origem}); "
        f"valor {formatar_reais(lancamento.valor_centavos)}: {pagamento.descrever()}."
    )
    if pagamento.fecha:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=identificacao,
            evidencia=(TipoDeEvidencia.NOSSO_NUMERO,),
        )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(titulo,),
        explicacao=identificacao,
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
        evidencia=(TipoDeEvidencia.NOSSO_NUMERO,),
    )
