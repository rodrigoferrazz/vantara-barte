from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime

from conciliacao.dominio import (
    Canal,
    ChaveNatural,
    Classificacao,
    Destino,
    Franqueado,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    PagadorConhecido,
    ParecerSobreFranqueado,
    ParRejeitado,
    RegraDaProposta,
    PossivelDuplicidade,
    Resposta,
    TipoDeDecisao,
    TipoDeEvidencia,
    Titulo,
    TituloNaCobranca,
)
from conciliacao.calendario import somar_dias_uteis, vencimento_efetivo
from conciliacao.encargo import CreditoEnquadrado, ParametrosDeEncargo, enquadrar
from conciliacao.normalizacao import cnpjs_no_texto, cpfs_no_texto, formatar_reais, nome_normalizado, raiz_do_cnpj
from conciliacao.parecerista import PareceristaDeNome

type NomeDoPagador = Callable[[Lancamento], str | None]
type CanalDoCredito = Callable[[Lancamento], Canal]
type Motor = Callable[..., list[Classificacao]]

_DIAS_UTEIS_DE_COMPENSACAO_DO_BOLETO = 2


@dataclass(frozen=True)
class _NomeDoFranqueado:
    raiz: str
    sistema_de_origem: str
    nome: str
    normalizado: str


@dataclass(frozen=True)
class _Opcao:
    titulos: tuple[tuple[Titulo, CreditoEnquadrado], ...]

    def descrever(self) -> str:
        if len(self.titulos) == 1:
            [(titulo, enquadrado)] = self.titulos
            return f"Título {titulo.documento} ({titulo.sistema_de_origem}), {enquadrado.descrever()}"
        parcelas = " + ".join(
            f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})"
            for titulo, _ in self.titulos
        )
        soma = formatar_reais(sum(titulo.valor_centavos for titulo, _ in self.titulos))
        enquadrados = "; ".join(f"{titulo.documento} {enquadrado.descrever()}" for titulo, enquadrado in self.titulos)
        return f"soma exata dos Títulos {parcelas} = {soma} ({enquadrados})"


@dataclass(frozen=True)
class _Busca:
    opcoes: tuple[_Opcao, ...]
    limite_atingido: bool
    limite: int

    @property
    def fecha(self) -> bool:
        return bool(self.opcoes) or self.limite_atingido

    @property
    def unica(self) -> _Opcao | None:
        return self.opcoes[0] if len(self.opcoes) == 1 and not self.limite_atingido else None

    @property
    def titulos(self) -> tuple[Titulo, ...]:
        return tuple(dict.fromkeys(titulo for opcao in self.opcoes for titulo, _ in opcao.titulos))

    def descrever_ambiguidade(self) -> str:
        opcoes = "; ".join(opcao.descrever() for opcao in self.opcoes)
        if self.limite_atingido:
            encontradas = f"; encontradas até o limite: {opcoes}" if opcoes else ""
            return (
                f"a busca de somas de Títulos atingiu o limite de {self.limite} combinações examinadas "
                f"sem garantir uma combinação única{encontradas}"
            )
        return f"fecha com mais de uma combinação de Títulos em aberto, considerando o Encargo: {opcoes}"


@dataclass(frozen=True)
class _Titulos:
    todos: list[Titulo]
    por_nosso_numero: dict[str, list[Titulo]]
    por_franqueado: dict[str, list[Titulo]]
    nomes: list[_NomeDoFranqueado]
    encargo: ParametrosDeEncargo
    nome_do_pagador: NomeDoPagador
    limite_de_combinacoes: int
    parecerista: PareceristaDeNome
    conhecidos: dict[str, PagadorConhecido]

    @property
    def franqueados(self) -> set[str]:
        return {nome.raiz for nome in self.nomes}

    def nomes_do_franqueado(self, raiz: str) -> list[str]:
        return sorted({nome.nome for nome in self.nomes if nome.raiz == raiz})

    def que_fecham(self, titulos: list[Titulo], lancamento: Lancamento) -> list[tuple[Titulo, CreditoEnquadrado]]:
        return [
            (titulo, enquadrado)
            for titulo in titulos
            if (enquadrado := enquadrar(titulo, lancamento.valor_centavos, lancamento.data, self.encargo)).fecha
        ]

    def buscar(self, titulos: list[Titulo], lancamento: Lancamento) -> _Busca:
        opcoes = [_Opcao(((titulo, enquadrado),)) for titulo, enquadrado in self.que_fecham(titulos, lancamento)]
        limite_atingido = False
        if len(opcoes) < 2:
            somas, limite_atingido = _somas_exatas(
                titulos, lancamento.valor_centavos, self.limite_de_combinacoes, bastam=2 - len(opcoes)
            )
            opcoes += [
                _Opcao(
                    tuple(
                        (titulo, enquadrar(titulo, titulo.valor_centavos, lancamento.data, self.encargo))
                        for titulo in sorted(soma, key=lambda t: (t.sistema_de_origem, t.documento))
                    )
                )
                for soma in somas
            ]
        return _Busca(tuple(opcoes), limite_atingido, self.limite_de_combinacoes)


def _somas_exatas(
    titulos: list[Titulo], alvo: int, limite: int, bastam: int
) -> tuple[list[tuple[Titulo, ...]], bool]:
    ordenados = sorted(titulos, key=lambda t: (t.valor_centavos, t.sistema_de_origem, t.documento))
    encontradas: list[tuple[Titulo, ...]] = []
    examinadas = 0

    def buscar(inicio: int, escolhidos: tuple[Titulo, ...], soma: int) -> bool:
        nonlocal examinadas
        for indice in range(inicio, len(ordenados)):
            titulo = ordenados[indice]
            nova = soma + titulo.valor_centavos
            if nova > alvo:
                return False
            examinadas += 1
            if examinadas > limite:
                return True
            combinacao = (*escolhidos, titulo)
            if nova == alvo:
                if len(combinacao) > 1:
                    encontradas.append(combinacao)
                    if len(encontradas) >= bastam:
                        return True
            elif buscar(indice + 1, combinacao, nova):
                return True
        return False

    buscar(0, (), 0)
    return encontradas, examinadas > limite


def conciliar(
    titulos: Iterable[Titulo],
    lancamentos: Iterable[Lancamento],
    franqueados: Iterable[Franqueado],
    encargo: ParametrosDeEncargo,
    nome_do_pagador: NomeDoPagador,
    canal_do_credito: CanalDoCredito,
    limite_de_combinacoes: int,
    parecerista: PareceristaDeNome,
    pares_rejeitados: Iterable[ParRejeitado] = (),
    pagadores_conhecidos: Iterable[PagadorConhecido] = (),
    *,
    antecipacoes: Mapping[ChaveNatural, datetime],
    fontes_nao_integradas: Mapping[ChaveNatural, datetime],
    divergencias: Mapping[ChaveNatural, list[str]],
) -> list[Classificacao]:
    todos = list(titulos)
    nomes = _nomes_dos_franqueados(franqueados, todos)
    conhecidos = {pagador.nome: pagador for pagador in pagadores_conhecidos}

    def abertos(titulos: list[Titulo]) -> _Titulos:
        por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
        por_franqueado: dict[str, list[Titulo]] = defaultdict(list)
        for titulo in titulos:
            if titulo.nosso_numero:
                por_nosso_numero[titulo.nosso_numero].append(titulo)
            por_franqueado[titulo.franqueado].append(titulo)
        return _Titulos(
            titulos,
            por_nosso_numero,
            por_franqueado,
            nomes,
            encargo,
            nome_do_pagador,
            limite_de_combinacoes,
            parecerista,
            conhecidos,
        )

    rejeitados: dict[ChaveNatural, list[ParRejeitado]] = defaultdict(list)
    for par in pares_rejeitados:
        rejeitados[par.credito].append(par)
    todos_abertos = abertos(todos)

    def classificar(lancamento: Lancamento) -> Classificacao:
        pares = rejeitados.get(lancamento.chave_natural)
        if not pares:
            return _classificar(lancamento, todos_abertos)
        restantes = [titulo for titulo in todos if not any(par.rejeita(titulo) for par in pares)]
        return _apos_rejeicao(_classificar(lancamento, abertos(restantes)), pares)

    classificacoes = _sem_titulo_disputado_na_lista(
        [_com_canal(classificar(lancamento), canal_do_credito) for lancamento in lancamentos]
    )
    return _com_divergencias(
        _com_classificacoes_da_analista(classificacoes, antecipacoes, fontes_nao_integradas), divergencias
    )


def _com_classificacoes_da_analista(
    classificacoes: list[Classificacao],
    antecipacoes: Mapping[ChaveNatural, datetime],
    fontes_nao_integradas: Mapping[ChaveNatural, datetime],
) -> list[Classificacao]:
    return [
        _como_fonte_nao_integrada(_como_antecipacao(c, antecipacoes), fontes_nao_integradas) for c in classificacoes
    ]


def _como_antecipacao(c: Classificacao, antecipacoes: Mapping[ChaveNatural, datetime]) -> Classificacao:
    momento = antecipacoes.get(c.lancamento.chave_natural)
    if momento is None:
        return c
    return replace(
        c,
        explicacao=f"{c.explicacao} Classificado pela Analista como {TipoDeDecisao.ANTECIPACAO.value} "
        f"em {momento:%d/%m/%Y}; o Crédito continua vivo e é retentado a cada nova importação.",
    )


def _como_fonte_nao_integrada(c: Classificacao, fontes: Mapping[ChaveNatural, datetime]) -> Classificacao:
    momento = fontes.get(c.lancamento.chave_natural)
    if momento is None or c.destino is not Destino.FILA_DE_EXCECOES:
        return c
    fonte = MotivoDeNaoIdentificacao.POSSIVEL_FONTE_NAO_INTEGRADA
    return replace(
        c,
        motivo=fonte,
        explicacao=f"{c.explicacao} Classificado pela Analista como {fonte.value} em {momento:%d/%m/%Y} "
        f"(o motor apontava '{c.motivo}'); o Crédito continua vivo e é retentado a cada nova importação.",
    )


def _com_divergencias(
    classificacoes: list[Classificacao], divergencias: Mapping[ChaveNatural, list[str]]
) -> list[Classificacao]:
    com_divergencia = []
    for c in classificacoes:
        explicacoes = divergencias.get(c.lancamento.chave_natural)
        if not explicacoes:
            com_divergencia.append(c)
            continue
        explicacao = " ".join((c.explicacao, *explicacoes))
        if c.destino is Destino.LISTA_DE_BAIXA:
            com_divergencia.append(
                replace(
                    c,
                    destino=Destino.FILA_DE_EXCECOES,
                    explicacao=explicacao,
                    motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
                    regra=None,
                )
            )
        else:
            com_divergencia.append(replace(c, explicacao=explicacao))
    return com_divergencia


def _apos_rejeicao(classificacao: Classificacao, pares: list[ParRejeitado]) -> Classificacao:
    rejeicoes = "; ".join(f"Título {par.documento} ({par.sistema_de_origem}), motivo: {par.motivo}" for par in pares)
    explicacao = f"{classificacao.explicacao} Proposta anterior rejeitada pela Analista: {rejeicoes}."
    if classificacao.destino is not Destino.LISTA_DE_BAIXA:
        return replace(classificacao, explicacao=explicacao)
    return replace(
        classificacao,
        destino=Destino.FILA_DE_EXCECOES,
        explicacao=explicacao,
        motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        regra=None,
    )


def _com_canal(classificacao: Classificacao, canal_do_credito: CanalDoCredito) -> Classificacao:
    lancamento = classificacao.lancamento
    if lancamento.natureza is Natureza.DEBITO:
        return classificacao
    return replace(classificacao, canal=canal_do_credito(lancamento))


def _sem_titulo_disputado_na_lista(classificacoes: list[Classificacao]) -> list[Classificacao]:
    na_lista: dict[Titulo, list[Lancamento]] = defaultdict(list)
    for classificacao in classificacoes:
        if classificacao.destino is Destino.LISTA_DE_BAIXA:
            for titulo in classificacao.titulos:
                na_lista[titulo].append(classificacao.lancamento)
    return [_disputada(c, na_lista) if c.destino is Destino.LISTA_DE_BAIXA else c for c in classificacoes]


def _disputada(classificacao: Classificacao, na_lista: dict[Titulo, list[Lancamento]]) -> Classificacao:
    outros = {
        outro
        for titulo in classificacao.titulos
        for outro in na_lista[titulo]
        if outro.chave_natural != classificacao.lancamento.chave_natural
    }
    if not outros:
        return classificacao
    creditos = ", ".join(
        f"{outro.data:%d/%m/%Y} {outro.historico} {formatar_reais(outro.valor_centavos)}"
        for outro in sorted(outros, key=lambda lancamento: lancamento.chave_natural)
    )
    return replace(
        classificacao,
        destino=Destino.FILA_DE_EXCECOES,
        explicacao=f"{classificacao.explicacao} Há Título desta proposta que também fecha com outro Crédito: {creditos}.",
        motivo=MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        regra=None,
    )


def _nomes_dos_franqueados(franqueados: Iterable[Franqueado], titulos: list[Titulo]) -> list[_NomeDoFranqueado]:
    nomes = {
        (franqueado.raiz, sistema, nome)
        for franqueado in franqueados
        for sistema, nomes_no_sistema in franqueado.nomes.items()
        for nome in nomes_no_sistema
    } | {(titulo.franqueado, titulo.sistema_de_origem, titulo.nome_do_franqueado) for titulo in titulos}
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


def lista_de_cobranca(
    titulos: Iterable[Titulo],
    classificacoes: Iterable[Classificacao],
    duplicidades: Iterable[PossivelDuplicidade],
    data_de_referencia: date | None,
) -> list[TituloNaCobranca]:
    if data_de_referencia is None:
        return []
    em_duplicidade = {titulo for duplicidade in duplicidades for titulo in duplicidade.titulos}
    propostos = {
        titulo
        for classificacao in classificacoes
        if classificacao.destino is Destino.LISTA_DE_BAIXA
        for titulo in classificacao.titulos_candidatos
    }
    na_fila: dict[Titulo, list[Lancamento]] = defaultdict(list)
    for classificacao in classificacoes:
        if classificacao.destino is Destino.FILA_DE_EXCECOES:
            for titulo in classificacao.titulos_candidatos:
                na_fila[titulo].append(classificacao.lancamento)
    return [
        TituloNaCobranca(titulo, titulo.valor_centavos, tuple(na_fila[titulo]))
        for titulo in sorted(titulos, key=lambda t: (t.vencimento, t.sistema_de_origem, t.documento))
        if titulo not in em_duplicidade
        and (titulo in na_fila or titulo not in propostos)
        and titulo.valor_centavos > 0
        and data_de_referencia > _cobravel_depois_de(titulo)
    ]


def _cobravel_depois_de(titulo: Titulo) -> date:
    efetivo = vencimento_efetivo(titulo.vencimento)
    return somar_dias_uteis(efetivo, _DIAS_UTEIS_DE_COMPENSACAO_DO_BOLETO) if titulo.nosso_numero else efetivo


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
            citados=tuple(candidatos),
            franqueado=_unico({titulo.franqueado for titulo in candidatos}),
        )
    cnpjs = cnpjs_no_texto(lancamento.historico)
    documentos = [c for c in cnpjs if raiz_do_cnpj(c) in abertos.franqueados]
    raizes = {raiz_do_cnpj(c) for c in documentos}
    if len(raizes) == 1:
        franqueado = raiz_do_cnpj(documentos[0])
        return _por_pagador_identificado(
            lancamento,
            franqueado,
            f"CNPJ {documentos[0]} no histórico identifica o Franqueado de raiz {franqueado}",
            TipoDeEvidencia.CNPJ_CPF,
            (RegraDaProposta.DOCUMENTO_E_VALOR_UNICO, RegraDaProposta.DOCUMENTO_E_SOMA_EXATA),
            abertos,
        )
    if raizes:
        return _sem_identificacao(
            lancamento,
            f"Os CNPJs do histórico são de mais de um Franqueado: raízes {', '.join(sorted(raizes))}.",
            (TipoDeEvidencia.CNPJ_CPF,),
        )
    desconhecidos = [*cnpjs, *cpfs_no_texto(lancamento.historico)]
    if desconhecidos:
        return _so_valor(
            lancamento,
            f"{', '.join(desconhecidos)} no histórico não é CNPJ de Franqueado conhecido nem de Pagador conhecido",
            abertos,
        )
    nome = abertos.nome_do_pagador(lancamento)
    normalizado = nome_normalizado(nome) if nome else ""
    conhecido = abertos.conhecidos.get(normalizado) if normalizado else None
    if nome and conhecido and (conhecido_de := conhecido.franqueado):
        return _por_pagador_identificado(
            lancamento,
            conhecido_de,
            f"Nome '{nome}' do Extrato é Pagador conhecido do Franqueado de raiz {conhecido_de}, confirmado pela Analista",
            TipoDeEvidencia.PAGADOR_CONHECIDO,
            (RegraDaProposta.PAGADOR_CONHECIDO_E_VALOR_UNICO, RegraDaProposta.PAGADOR_CONHECIDO_E_SOMA_EXATA),
            abertos,
        )
    if not (nome and normalizado):
        return _so_valor(lancamento, "Crédito sem nome nem documento que identifique o pagador", abertos)
    por_prefixo = [n for n in abertos.nomes if n.normalizado.startswith(normalizado)]
    prefixados = {n.raiz for n in por_prefixo}
    franqueados_candidatos = {
        raiz: busca
        for raiz, titulos in sorted(abertos.por_franqueado.items())
        if (busca := abertos.buscar(titulos, lancamento)).fecha
    }
    if any(raiz not in prefixados for raiz in franqueados_candidatos):
        classificacao = _por_parecer(lancamento, nome, por_prefixo, franqueados_candidatos, abertos)
    elif por_prefixo:
        classificacao = _por_nome(lancamento, nome, por_prefixo, abertos)
    else:
        classificacao = _so_valor(lancamento, _sem_prefixo(nome), abertos)
    return _confirmado_para_mais_de_um(classificacao, nome, conhecido) if conhecido else classificacao


def _confirmado_para_mais_de_um(
    classificacao: Classificacao, nome: str, conhecido: PagadorConhecido
) -> Classificacao:
    explicacao = (
        f"{classificacao.explicacao} O nome '{nome}' foi confirmado pela Analista para mais de um Franqueado "
        f"(raízes {', '.join(conhecido.franqueados)}) e não é Pagador conhecido."
    )
    if classificacao.motivo is MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ:
        return replace(
            classificacao, explicacao=explicacao, motivo=MotivoDeNaoIdentificacao.NOME_AMBIGUO, franqueado=None
        )
    return replace(classificacao, explicacao=explicacao)


def _sem_identificacao(
    lancamento: Lancamento,
    explicacao: str,
    evidencia: tuple[TipoDeEvidencia, ...],
    titulos: tuple[Titulo, ...] = (),
    citados: tuple[Titulo, ...] = (),
    franqueado: str | None = None,
) -> Classificacao:
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=titulos,
        explicacao=explicacao,
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
        evidencia=evidencia,
        citados=citados,
        franqueado=franqueado,
    )


def _unico(franqueados: set[str]) -> str | None:
    return next(iter(franqueados)) if len(franqueados) == 1 else None


def _por_nome(
    lancamento: Lancamento, nome: str, por_prefixo: list[_NomeDoFranqueado], abertos: _Titulos
) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    nomes = ", ".join(f"{n.nome} ({n.sistema_de_origem}, raiz {n.raiz})" for n in por_prefixo)
    identificacao = f"Nome '{nome}' do Extrato é Nome por prefixo de {nomes}"
    franqueados = sorted({n.raiz for n in por_prefixo})
    titulos = [titulo for raiz in franqueados for titulo in abertos.por_franqueado.get(raiz, [])]
    buscas = {
        raiz: busca for raiz in franqueados if (busca := abertos.buscar(abertos.por_franqueado.get(raiz, []), lancamento)).fecha
    }
    franqueado = _unico(set(franqueados)) or _unico(set(buscas))

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        titulos_candidatos: tuple[Titulo, ...],
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=titulos_candidatos,
            explicacao=f"{identificacao}; {explicacao}.",
            motivo=motivo,
            evidencia=(TipoDeEvidencia.NOME_POR_PREFIXO,),
            citados=citados,
            franqueado=franqueado,
        )

    if not buscas:
        unicos = [
            titulo for raiz in franqueados if (titulo := _unico_em_aberto(abertos.por_franqueado.get(raiz, [])))
        ]
        if not unicos:
            return fila(MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO, _sem_titulo_candidato(titulos, valor), ())
        if len(unicos) == 1:
            return fila(
                MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
                f"o valor {valor} {_nao_fecha(unicos[0], lancamento, abertos.encargo)}",
                tuple(unicos),
            )
        return fila(
            MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
            f"o valor {valor} não fecha, nem considerando o Encargo, com o único Título em aberto de cada "
            f"Franqueado: {_documentos(unicos)}",
            (),
            tuple(unicos),
        )
    if len(buscas) > 1:
        por_franqueado = "; ".join(
            f"raiz {raiz}: {'; '.join(opcao.descrever() for opcao in busca.opcoes) or 'limite da busca de somas atingido'}"
            for raiz, busca in buscas.items()
        )
        return fila(
            MotivoDeNaoIdentificacao.NOME_AMBIGUO,
            f"o valor {valor} fecha com Títulos de mais de um Franqueado: {por_franqueado}",
            (),
            tuple(titulo for busca in buscas.values() for titulo in busca.titulos),
        )
    [busca] = buscas.values()
    opcao = busca.unica
    if opcao is None:
        return fila(
            MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
            f"o valor {valor} {busca.descrever_ambiguidade()}",
            (),
            busca.titulos,
        )
    return fila(
        MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
        f"o valor {valor} é Valor único: {opcao.descrever()}; o nome ainda não é Pagador conhecido",
        tuple(titulo for titulo, _ in opcao.titulos),
    )


def _por_parecer(
    lancamento: Lancamento,
    nome: str,
    por_prefixo: list[_NomeDoFranqueado],
    candidatos: dict[str, _Busca],
    abertos: _Titulos,
) -> Classificacao:
    prefixados = {n.raiz for n in por_prefixo}
    valor = formatar_reais(lancamento.valor_centavos)
    pareceres = tuple(
        ParecerSobreFranqueado(raiz, abertos.parecerista.dar_parecer(nome, abertos.nomes_do_franqueado(raiz)))
        for raiz in candidatos
        if raiz not in prefixados
    )
    parecer = (
        f"parecer da IA sobre os Franqueados com que o valor {valor} fecha e de cujos nomes o nome do Extrato "
        f"não é Nome por prefixo: {'; '.join(p.descrever() for p in pareceres)}"
    )
    if por_prefixo:
        nomes = ", ".join(f"{n.nome} ({n.sistema_de_origem}, raiz {n.raiz})" for n in por_prefixo)
        identificacao = f"Nome '{nome}' do Extrato é Nome por prefixo de {nomes}; {parecer}"
    else:
        identificacao = f"{_sem_prefixo(nome)}; {parecer}"
    respostas = {p.parecer.resposta for p in pareceres}
    indisponivel = Resposta.INDISPONIVEL in respostas
    pela_ia = [p.franqueado for p in pareceres if p.parecer.resposta is Resposta.SIM]
    pelo_prefixo = [raiz for raiz in candidatos if raiz in prefixados]
    confirmados = sorted(pelo_prefixo + pela_ia)

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        evidencia: tuple[TipoDeEvidencia, ...],
        titulos_candidatos: tuple[Titulo, ...] = (),
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=titulos_candidatos,
            explicacao=f"{identificacao}. {explicacao}.",
            motivo=motivo,
            evidencia=evidencia,
            pareceres=pareceres,
            citados=citados,
            franqueado=None if indisponivel else _unico(set(confirmados)),
        )

    if not indisponivel and not confirmados and por_prefixo:
        pelo_nome = _por_nome(lancamento, nome, por_prefixo, abertos)
        return replace(pelo_nome, explicacao=f"{pelo_nome.explicacao} A IA negou: {parecer}.", pareceres=pareceres)
    if indisponivel or not confirmados:
        busca = _Busca(
            tuple(opcao for busca in candidatos.values() for opcao in busca.opcoes),
            any(busca.limite_atingido for busca in candidatos.values()),
            abertos.limite_de_combinacoes,
        )
        sem_parecer = "IA indisponível; o nome fica sem parecer" if indisponivel else "A IA negou"
        if opcao := busca.unica:
            return fila(
                MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
                f"{sem_parecer}; só o valor {valor} aponta {opcao.descrever()}",
                (TipoDeEvidencia.SO_VALOR,),
                tuple(titulo for titulo, _ in opcao.titulos),
            )
        return fila(
            MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
            f"{sem_parecer}; só o valor {valor} {busca.descrever_ambiguidade()}",
            (TipoDeEvidencia.SO_VALOR,),
            citados=busca.titulos,
        )
    evidencia = tuple(
        tipo
        for tipo, presente in ((TipoDeEvidencia.NOME_POR_PREFIXO, pelo_prefixo), (TipoDeEvidencia.PARECER_DE_LLM, pela_ia))
        if presente
    )
    if len(confirmados) > 1:
        return fila(
            MotivoDeNaoIdentificacao.NOME_AMBIGUO,
            f"O nome é de mais de um Franqueado com que o valor fecha: raízes {', '.join(confirmados)}",
            evidencia,
            citados=tuple(titulo for raiz in confirmados for titulo in candidatos[raiz].titulos),
        )
    [franqueado] = confirmados
    busca = candidatos[franqueado]
    por_quem = "Pelo parecer da IA" if pela_ia else "Pelo Nome por prefixo, com a IA negando os outros Franqueados"
    if opcao := busca.unica:
        return fila(
            MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
            f"{por_quem}, o valor {valor} é Valor único do Franqueado de raiz {franqueado}: "
            f"{opcao.descrever()}; o nome ainda não é Pagador conhecido",
            evidencia,
            tuple(titulo for titulo, _ in opcao.titulos),
        )
    return fila(
        MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        f"{por_quem}, o pagador é o Franqueado de raiz {franqueado}, mas o valor {valor} "
        f"{busca.descrever_ambiguidade()}",
        evidencia,
        citados=busca.titulos,
    )


def _sem_prefixo(nome: str) -> str:
    return f"Nome '{nome}' do Extrato não é Nome por prefixo de nenhum nome de Franqueado"


def _so_valor(lancamento: Lancamento, pagador: str, abertos: _Titulos) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    que_fecham = abertos.que_fecham(abertos.todos, lancamento)
    if not que_fecham:
        return _sem_identificacao(lancamento, f"{pagador}; o valor {valor} não fecha com nenhum Título em aberto.", ())
    if len(que_fecham) > 1:
        return _sem_identificacao(
            lancamento,
            f"{pagador}; só o valor {valor} aponta mais de um Título em aberto: "
            f"{_documentos([titulo for titulo, _ in que_fecham])}.",
            (TipoDeEvidencia.SO_VALOR,),
            citados=tuple(titulo for titulo, _ in que_fecham),
        )
    [(titulo, enquadrado)] = que_fecham
    return _sem_identificacao(
        lancamento,
        f"{pagador}; só o valor {valor} aponta o Título {titulo.documento} ({titulo.sistema_de_origem}) "
        f"do Franqueado {titulo.nome_do_franqueado}, {enquadrado.descrever()}.",
        (TipoDeEvidencia.SO_VALOR,),
        (titulo,),
    )


def _por_pagador_identificado(
    lancamento: Lancamento,
    franqueado: str,
    pagador: str,
    evidencia: TipoDeEvidencia,
    regras: tuple[RegraDaProposta, RegraDaProposta],
    abertos: _Titulos,
) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    titulos = abertos.por_franqueado.get(franqueado, [])

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        titulos_candidatos: tuple[Titulo, ...] = (),
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(evidencia,),
            destino=Destino.FILA_DE_EXCECOES,
            titulos=titulos_candidatos,
            explicacao=explicacao,
            motivo=motivo,
            citados=citados,
            franqueado=franqueado,
        )

    busca = abertos.buscar(titulos, lancamento)
    if opcao := busca.unica:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(evidencia,),
            destino=Destino.LISTA_DE_BAIXA,
            titulos=tuple(titulo for titulo, _ in opcao.titulos),
            explicacao=f"{pagador}; o valor {valor} é Valor único entre os Títulos em aberto dele: {opcao.descrever()}.",
            franqueado=franqueado,
            regra=regras[0] if len(opcao.titulos) == 1 else regras[1],
        )
    if busca.fecha:
        return fila(
            MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
            f"{pagador}, mas o valor {valor} {busca.descrever_ambiguidade()}.",
            citados=busca.titulos,
        )
    if unico := _unico_em_aberto(titulos):
        return fila(
            MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
            f"{pagador}, mas o valor {valor} {_nao_fecha(unico, lancamento, abertos.encargo)}.",
            (unico,),
        )
    return fila(MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO, f"{pagador}; {_sem_titulo_candidato(titulos, valor)}.")


def _unico_em_aberto(titulos: list[Titulo]) -> Titulo | None:
    # Sem opção que feche, só o único Título em aberto do Franqueado é candidato: é frente a ele que o Crédito
    # é Diferença a menor ou Valor a maior. Com vários, nenhum deles é apontado.
    return titulos[0] if len(titulos) == 1 else None


def _nao_fecha(titulo: Titulo, lancamento: Lancamento, encargo: ParametrosDeEncargo) -> str:
    return (
        f"não fecha, nem considerando o Encargo, com o único Título em aberto do Franqueado, {_documentos([titulo])}: "
        f"{enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo).descrever()}"
    )


def _sem_titulo_candidato(titulos: list[Titulo], valor: str) -> str:
    if not titulos:
        return "nenhum Título em aberto, então nenhum Título candidato"
    return (
        f"nenhum Título candidato: o valor {valor} não fecha com nenhum dos Títulos em aberto, sozinho considerando "
        f"o Encargo ou em soma exata, e com mais de um Título em aberto nenhum deles é apontado: {_documentos(titulos)}"
    )


def _documentos(titulos: list[Titulo]) -> str:
    return ", ".join(
        f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})" for titulo in titulos
    )


def _por_nosso_numero(lancamento: Lancamento, titulo: Titulo, encargo: ParametrosDeEncargo) -> Classificacao:
    enquadrado = enquadrar(titulo, lancamento.valor_centavos, lancamento.data, encargo)
    identificacao = (
        f"Nosso número {titulo.nosso_numero} é do Título {titulo.documento} ({titulo.sistema_de_origem}); "
        f"valor {formatar_reais(lancamento.valor_centavos)}: {enquadrado.descrever()}."
    )
    if enquadrado.fecha:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.LISTA_DE_BAIXA,
            titulos=(titulo,),
            explicacao=identificacao,
            evidencia=(TipoDeEvidencia.NOSSO_NUMERO,),
            franqueado=titulo.franqueado,
            regra=RegraDaProposta.NOSSO_NUMERO_E_VALOR,
        )
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=(titulo,),
        explicacao=identificacao,
        motivo=MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
        evidencia=(TipoDeEvidencia.NOSSO_NUMERO,),
        franqueado=titulo.franqueado,
    )
