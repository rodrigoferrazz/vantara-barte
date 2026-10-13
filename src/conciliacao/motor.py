from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date

from conciliacao.dominio import (
    Classificacao,
    Destino,
    Franqueado,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    ParecerSobreFranqueado,
    PossivelDuplicidade,
    Resposta,
    TipoDeEvidencia,
    Titulo,
    TituloNaCobranca,
)
from conciliacao.calendario import somar_dias_uteis, vencimento_efetivo
from conciliacao.encargo import Pagamento, ParametrosDeEncargo, enquadrar
from conciliacao.normalizacao import cnpjs_no_texto, formatar_reais, nome_normalizado, raiz_do_cnpj
from conciliacao.parecerista import PareceristaDeNome

type NomeDoPagador = Callable[[Lancamento], str | None]

_DIAS_UTEIS_DE_COMPENSACAO_DO_BOLETO = 2


@dataclass(frozen=True)
class _NomeDoFranqueado:
    raiz: str
    sistema_de_origem: str
    nome: str
    normalizado: str


@dataclass(frozen=True)
class _Opcao:
    titulos: tuple[tuple[Titulo, Pagamento], ...]

    def descrever(self) -> str:
        if len(self.titulos) == 1:
            [(titulo, pagamento)] = self.titulos
            return f"Título {titulo.documento} ({titulo.sistema_de_origem}), {pagamento.descrever()}"
        parcelas = " + ".join(
            f"{titulo.documento} ({titulo.sistema_de_origem}, {formatar_reais(titulo.valor_centavos)})"
            for titulo, _ in self.titulos
        )
        soma = formatar_reais(sum(titulo.valor_centavos for titulo, _ in self.titulos))
        pagamentos = "; ".join(f"{titulo.documento} {pagamento.descrever()}" for titulo, pagamento in self.titulos)
        return f"soma exata dos Títulos {parcelas} = {soma} ({pagamentos})"


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

    @property
    def franqueados(self) -> set[str]:
        return {nome.raiz for nome in self.nomes}

    def nomes_do_franqueado(self, raiz: str) -> list[str]:
        return sorted({nome.nome for nome in self.nomes if nome.raiz == raiz})

    def que_fecham(self, titulos: list[Titulo], lancamento: Lancamento) -> list[tuple[Titulo, Pagamento]]:
        return [
            (titulo, pagamento)
            for titulo in titulos
            if (pagamento := enquadrar(titulo, lancamento.valor_centavos, lancamento.data, self.encargo)).fecha
        ]

    def buscar(self, titulos: list[Titulo], lancamento: Lancamento) -> _Busca:
        opcoes = [_Opcao(((titulo, pagamento),)) for titulo, pagamento in self.que_fecham(titulos, lancamento)]
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
    limite_de_combinacoes: int,
    parecerista: PareceristaDeNome,
) -> list[Classificacao]:
    todos = list(titulos)
    por_nosso_numero: dict[str, list[Titulo]] = defaultdict(list)
    por_franqueado: dict[str, list[Titulo]] = defaultdict(list)
    for titulo in todos:
        if titulo.nosso_numero:
            por_nosso_numero[titulo.nosso_numero].append(titulo)
        por_franqueado[titulo.franqueado].append(titulo)
    abertos = _Titulos(
        todos,
        por_nosso_numero,
        por_franqueado,
        _nomes_dos_franqueados(franqueados, todos),
        encargo,
        nome_do_pagador,
        limite_de_combinacoes,
        parecerista,
    )
    return _sem_titulo_disputado_na_lista([_classificar(lancamento, abertos) for lancamento in lancamentos])


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
    )


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


def lista_de_cobranca(
    titulos: Iterable[Titulo],
    classificacoes: Iterable[Classificacao],
    duplicidades: Iterable[PossivelDuplicidade],
    data_de_referencia: date | None,
) -> list[TituloNaCobranca]:
    if data_de_referencia is None:
        return []
    em_duplicidade = {titulo for duplicidade in duplicidades for titulo in duplicidade.titulos}
    candidatos: dict[Titulo, list[Lancamento]] = defaultdict(list)
    for classificacao in classificacoes:
        if classificacao.destino is not Destino.FORA_DO_ESCOPO:
            for titulo in classificacao.titulos_candidatos:
                candidatos[titulo].append(classificacao.lancamento)
    return [
        TituloNaCobranca(titulo, titulo.valor_centavos, tuple(candidatos[titulo]))
        for titulo in sorted(titulos, key=lambda t: (t.vencimento, t.sistema_de_origem, t.documento))
        if titulo not in em_duplicidade and titulo.valor_centavos > 0 and data_de_referencia > _cobravel_depois_de(titulo)
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
        )
    documentos = [c for c in cnpjs_no_texto(lancamento.historico) if raiz_do_cnpj(c) in abertos.franqueados]
    raizes = {raiz_do_cnpj(c) for c in documentos}
    if len(raizes) == 1:
        franqueado = raiz_do_cnpj(documentos[0])
        return _por_documento(lancamento, documentos[0], abertos.por_franqueado.get(franqueado, []), abertos)
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
    if nome and normalizado:
        return _por_parecer(lancamento, nome, abertos)
    return _so_valor(lancamento, None, abertos)


def _sem_identificacao(
    lancamento: Lancamento,
    explicacao: str,
    evidencia: tuple[TipoDeEvidencia, ...],
    titulos: tuple[Titulo, ...] = (),
    citados: tuple[Titulo, ...] = (),
) -> Classificacao:
    return Classificacao(
        lancamento=lancamento,
        destino=Destino.FILA_DE_EXCECOES,
        titulos=titulos,
        explicacao=explicacao,
        motivo=MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
        evidencia=evidencia,
        citados=citados,
    )


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

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        sugeridos: tuple[Titulo, ...],
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=sugeridos,
            explicacao=f"{identificacao}; {explicacao}.",
            motivo=motivo,
            evidencia=(TipoDeEvidencia.NOME_POR_PREFIXO,),
            citados=citados,
        )

    if not titulos:
        return fila(MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO, "nenhum Título em aberto", ())
    if not buscas:
        return fila(
            MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
            f"o valor {valor} {_nao_fecha(titulos, lancamento, abertos.encargo)}",
            tuple(titulos) if len(titulos) == 1 else (),
            tuple(titulos),
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


def _por_parecer(lancamento: Lancamento, nome: str, abertos: _Titulos) -> Classificacao:
    candidatos = {
        raiz: busca
        for raiz, titulos in sorted(abertos.por_franqueado.items())
        if (busca := abertos.buscar(titulos, lancamento)).fecha
    }
    if not candidatos:
        return _so_valor(lancamento, nome, abertos)
    valor = formatar_reais(lancamento.valor_centavos)
    pareceres = tuple(
        ParecerSobreFranqueado(raiz, abertos.parecerista.dar_parecer(nome, abertos.nomes_do_franqueado(raiz)))
        for raiz in candidatos
    )
    identificacao = (
        f"Nome '{nome}' do Extrato não é Nome por prefixo de nenhum nome de Franqueado; parecer da IA sobre os "
        f"Franqueados com que o valor {valor} fecha: {'; '.join(p.descrever() for p in pareceres)}"
    )

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        evidencia: TipoDeEvidencia,
        sugeridos: tuple[Titulo, ...] = (),
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            destino=Destino.FILA_DE_EXCECOES,
            titulos=sugeridos,
            explicacao=f"{identificacao}. {explicacao}.",
            motivo=motivo,
            evidencia=(evidencia,),
            pareceres=pareceres,
            citados=citados,
        )

    respostas = {p.parecer.resposta for p in pareceres}
    confirmados = [p.franqueado for p in pareceres if p.parecer.resposta is Resposta.SIM]
    if Resposta.INDISPONIVEL in respostas or not confirmados:
        busca = _Busca(
            tuple(opcao for busca in candidatos.values() for opcao in busca.opcoes),
            any(busca.limite_atingido for busca in candidatos.values()),
            abertos.limite_de_combinacoes,
        )
        sem_parecer = "IA indisponível; o nome fica sem parecer" if Resposta.INDISPONIVEL in respostas else "A IA negou"
        if opcao := busca.unica:
            return fila(
                MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
                f"{sem_parecer}; só o valor {valor} aponta {opcao.descrever()}",
                TipoDeEvidencia.SO_VALOR,
                tuple(titulo for titulo, _ in opcao.titulos),
            )
        return fila(
            MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
            f"{sem_parecer}; só o valor {valor} {busca.descrever_ambiguidade()}",
            TipoDeEvidencia.SO_VALOR,
            citados=busca.titulos,
        )
    if len(confirmados) > 1:
        return fila(
            MotivoDeNaoIdentificacao.NOME_AMBIGUO,
            f"A IA diz que o nome é de mais de um Franqueado: raízes {', '.join(confirmados)}",
            TipoDeEvidencia.PARECER_DE_LLM,
            citados=tuple(titulo for raiz in confirmados for titulo in candidatos[raiz].titulos),
        )
    [franqueado] = confirmados
    busca = candidatos[franqueado]
    if opcao := busca.unica:
        return fila(
            MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
            f"Pelo parecer da IA, o valor {valor} é Valor único do Franqueado de raiz {franqueado}: "
            f"{opcao.descrever()}; o nome ainda não é Pagador conhecido",
            TipoDeEvidencia.PARECER_DE_LLM,
            tuple(titulo for titulo, _ in opcao.titulos),
        )
    return fila(
        MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
        f"Pelo parecer da IA o pagador é o Franqueado de raiz {franqueado}, mas o valor {valor} "
        f"{busca.descrever_ambiguidade()}",
        TipoDeEvidencia.PARECER_DE_LLM,
        citados=busca.titulos,
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
            citados=tuple(titulo for titulo, _ in que_fecham),
        )
    [(titulo, pagamento)] = que_fecham
    return _sem_identificacao(
        lancamento,
        f"{pagador}; só o valor {valor} aponta o Título {titulo.documento} ({titulo.sistema_de_origem}) "
        f"do Franqueado {titulo.cliente}, {pagamento.descrever()}.",
        (TipoDeEvidencia.SO_VALOR,),
        (titulo,),
    )


def _por_documento(lancamento: Lancamento, documento: str, titulos: list[Titulo], abertos: _Titulos) -> Classificacao:
    valor = formatar_reais(lancamento.valor_centavos)
    pagador = f"CNPJ {documento} no histórico identifica o Franqueado de raiz {raiz_do_cnpj(documento)}"

    def fila(
        motivo: MotivoDeNaoIdentificacao,
        explicacao: str,
        sugeridos: tuple[Titulo, ...] = (),
        citados: tuple[Titulo, ...] = (),
    ) -> Classificacao:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(TipoDeEvidencia.CNPJ_CPF,),
            destino=Destino.FILA_DE_EXCECOES,
            titulos=sugeridos,
            explicacao=explicacao,
            motivo=motivo,
            citados=citados,
        )

    if not titulos:
        return fila(MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO, f"{pagador}, que não tem Título em aberto.")
    busca = abertos.buscar(titulos, lancamento)
    if opcao := busca.unica:
        return Classificacao(
            lancamento=lancamento,
            evidencia=(TipoDeEvidencia.CNPJ_CPF,),
            destino=Destino.LISTA_DE_BAIXA,
            titulos=tuple(titulo for titulo, _ in opcao.titulos),
            explicacao=f"{pagador}; o valor {valor} é Valor único entre os Títulos em aberto dele: {opcao.descrever()}.",
        )
    if busca.fecha:
        return fila(
            MotivoDeNaoIdentificacao.MAIS_DE_UMA_COMBINACAO,
            f"{pagador}, mas o valor {valor} {busca.descrever_ambiguidade()}.",
            citados=busca.titulos,
        )
    return fila(
        MotivoDeNaoIdentificacao.VALOR_NAO_FECHA,
        f"{pagador}, mas o valor {valor} {_nao_fecha(titulos, lancamento, abertos.encargo)}.",
        tuple(titulos) if len(titulos) == 1 else (),
        tuple(titulos),
    )


def _nao_fecha(titulos: list[Titulo], lancamento: Lancamento, encargo: ParametrosDeEncargo) -> str:
    detalhe = (
        f"; {enquadrar(titulos[0], lancamento.valor_centavos, lancamento.data, encargo).descrever()}"
        if len(titulos) == 1
        else ""
    )
    return (
        "não fecha com nenhum Título em aberto nem com soma exata de Títulos em aberto, considerando o Encargo: "
        f"{_documentos(titulos)}{detalhe}"
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
