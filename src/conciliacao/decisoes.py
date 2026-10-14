import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from conciliacao.acompanhamento import saldos
from conciliacao.adaptadores import nome_do_pagador
from conciliacao.armazenamento import Armazenamento
from conciliacao.dominio import (
    DecisoesLidas,
    Item,
    ItemDeTitulo,
    Lancamento,
    LinhaDeDecisao,
    MotivoDeNaoIdentificacao,
    Resposta,
    TipoDeDecisao,
    TipoDeEvidencia,
    Titulo,
)
from conciliacao.encargo import ParametrosDeEncargo, enquadrar
from conciliacao.normalizacao import nome_normalizado
from conciliacao.saidas import (
    ABA_DA_FILA_DE_EXCECOES,
    ABA_DA_LISTA_DE_BAIXA,
    ABA_DE_REVERSAO,
    COLUNA_DA_DECISAO,
    COLUNA_DA_REFERENCIA_DO_CONCILIADO_FORA,
    COLUNA_DO_FRANQUEADO_DO_CONCILIADO_FORA,
    COLUNA_DO_ITEM,
    COLUNA_DO_MOTIVO_DA_REJEICAO,
    COLUNA_DOS_TITULOS_ESCOLHIDOS,
    LINHA_DA_EXECUCAO_NO_RESUMO,
)

ORIGEM_EXCEL = "Excel"
ORIGEM_TELA = "Tela"

type ChaveDoTitulo = tuple[str, str]

DECISOES_DE_CREDITO_DA_FILA = (
    TipoDeDecisao.CONFIRMAR,
    TipoDeDecisao.ANTECIPACAO,
    TipoDeDecisao.DEVOLUCAO,
    TipoDeDecisao.ERRO,
    TipoDeDecisao.CONCILIADO_FORA,
    TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA,
)
DECISOES_DE_DUPLICIDADE = (TipoDeDecisao.MESMA_DIVIDA, TipoDeDecisao.DIVIDAS_DISTINTAS)
_TITULO_COM_SISTEMA = re.compile(r"(?P<documento>.+?)\s*\((?P<sistema>[^()]+)\)")
_CNPJ_OU_RAIZ = re.compile(r"[\d./\- ]+")


@dataclass(frozen=True)
class _Autoria:
    autor: str
    momento: datetime
    origem: str


@dataclass(frozen=True)
class _WorkbookLido:
    execucao: object
    autor: str
    momento: datetime | None
    linhas: tuple[LinhaDeDecisao, ...]


@dataclass(frozen=True)
class DecisoesAplicadas:
    lidas: DecisoesLidas
    registradas: tuple[int, ...]
    duplicidades: tuple[int, ...] = ()
    da_tela: tuple[int, ...] = ()


class _NaoAplicada(Exception):
    pass


@dataclass(frozen=True)
class _Decisao:
    item: str
    tipo: TipoDeDecisao
    usa: frozenset[ChaveDoTitulo]
    registrar: Callable[[], int]


class _Interpretacao:
    def __init__(
        self,
        armazenamento: Armazenamento,
        execucao: int,
        encargo: ParametrosDeEncargo,
    ) -> None:
        self._armazenamento = armazenamento
        self._execucao = execucao
        self._encargo = encargo
        resultado = armazenamento.carregar_resultado(execucao)
        self._lista = {item.identificador: item for item in resultado.lista_de_baixa}
        self._fila = {item.identificador: item for item in resultado.fila_de_excecoes}
        self._duplicidades = {item.identificador: item for item in resultado.itens_de_titulo}
        titulos = armazenamento.titulos_da_execucao(execucao)
        cancelados = armazenamento.titulos_cancelados_na_origem()
        self._saldos = saldos(titulos, armazenamento.confirmacoes_em_vigor())
        self._abertos = {
            _chave(titulo): titulo
            for titulo in titulos
            if _chave(titulo) not in cancelados and self._saldos[_chave(titulo)] > 0
        }
        self._nomes = {raiz: franqueado.todos_os_nomes for raiz, franqueado in armazenamento.franqueados().items()}

    def interpretar(self, linha: LinhaDeDecisao, autoria: _Autoria) -> _Decisao:
        if linha.aba == ABA_DA_LISTA_DE_BAIXA:
            return self._da_lista(linha, autoria)
        if linha.aba == ABA_DE_REVERSAO:
            return self._reversao(linha, autoria)
        if linha.item in self._fila:
            return self._do_credito_da_fila(linha, self._fila[linha.item], autoria)
        if linha.item in self._duplicidades:
            return self._da_duplicidade(linha, self._duplicidades[linha.item], autoria)
        raise _NaoAplicada(
            f"Item {linha.item}: não está na Fila de exceções da execução {self._execucao}; decisão ignorada."
        )

    def _da_lista(self, linha: LinhaDeDecisao, autoria: _Autoria) -> _Decisao:
        item = self._lista.get(linha.item)
        if item is None:
            raise _NaoAplicada(
                f"Item {linha.item}: não está na Lista de baixa da execução {self._execucao}; decisão ignorada."
            )
        tipo = _tipo_da_lista(linha.decisao)
        if tipo is None:
            raise _NaoAplicada(
                f"Item {linha.item}: decisão '{linha.decisao}' não reconhecida "
                "(use 'confirmar', ou deixe vazio ou 'rejeitar' com motivo); não aplicada."
            )
        if tipo is TipoDeDecisao.REJEITAR:
            if not linha.motivo:
                raise _NaoAplicada(f"Item {linha.item}: rejeição sem motivo; não aplicada.")
            return _Decisao(
                item.identificador, tipo, frozenset(), lambda: self._registrar(item, tipo, item.titulos, autoria, linha.motivo)
            )
        return self._confirmacao(item, item.titulos, autoria)

    def _reversao(self, linha: LinhaDeDecisao, autoria: _Autoria) -> _Decisao:
        confirmacao = self._armazenamento.confirmacao_em_vigor_do_item(linha.item)
        if confirmacao is None:
            raise _NaoAplicada(f"Item {linha.item}: não há confirmação em vigor para reverter; não aplicada.")
        if not linha.motivo:
            raise _NaoAplicada(f"Item {linha.item}: reversão sem motivo; não aplicada.")
        return _Decisao(
            linha.item,
            TipoDeDecisao.REVERTER,
            frozenset(),
            lambda: self._armazenamento.registrar_reversao(
                confirmacao, linha.motivo, autoria.autor, autoria.momento, autoria.origem
            ),
        )

    def _do_credito_da_fila(self, linha: LinhaDeDecisao, item: Item, autoria: _Autoria) -> _Decisao:
        tipo = _tipo(linha.decisao, DECISOES_DE_CREDITO_DA_FILA)
        if tipo is None:
            raise _NaoAplicada(_nao_reconhecida(linha, DECISOES_DE_CREDITO_DA_FILA))
        if tipo is TipoDeDecisao.CONFIRMAR:
            titulos = self._escolhidos(linha, self._abertos) if linha.titulos else item.titulos
            if not titulos:
                raise _NaoAplicada(f"Item {linha.item}: confirmação sem Título escolhido nem sugerido; não aplicada.")
            fechados = [titulo for titulo in titulos if _chave(titulo) not in self._abertos]
            if fechados:
                raise _NaoAplicada(
                    f"Item {linha.item}: Título(s) {_descrever(fechados)} não está(ão) mais em aberto; não aplicada."
                )
            return self._confirmacao(item, titulos, autoria)
        if tipo is TipoDeDecisao.CONCILIADO_FORA:
            return self._conciliado_fora(linha, item, autoria)
        if tipo is TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA:
            return _Decisao(item.identificador, tipo, frozenset(), lambda: self._registrar(item, tipo, (), autoria))
        if item.motivo is not MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO:
            raise _NaoAplicada(
                f"Item {linha.item}: '{tipo.value}' só classifica Crédito sem título em aberto, e o Motivo do item é "
                f"'{item.motivo}'; não aplicada."
            )
        return _Decisao(item.identificador, tipo, frozenset(), lambda: self._registrar(item, tipo, (), autoria))

    def _conciliado_fora(self, linha: LinhaDeDecisao, item: Item, autoria: _Autoria) -> _Decisao:
        digitos = re.sub(r"\D", "", linha.franqueado)
        if not _CNPJ_OU_RAIZ.fullmatch(linha.franqueado) or len(digitos) not in (8, 14):
            raise _NaoAplicada(
                f"Item {linha.item}: Conciliado fora exige o CNPJ ou a raiz do CNPJ do Franqueado "
                f"(recebido '{linha.franqueado}'); não aplicada."
            )
        if not linha.referencia:
            raise _NaoAplicada(f"Item {linha.item}: Conciliado fora exige a referência; não aplicada.")

        def registrar() -> int:
            decisao = self._registrar(item, TipoDeDecisao.CONCILIADO_FORA, (), autoria)
            self._armazenamento.registrar_conciliado_fora(decisao, digitos[:8], linha.referencia)
            return decisao

        return _Decisao(item.identificador, TipoDeDecisao.CONCILIADO_FORA, frozenset(), registrar)

    def _da_duplicidade(self, linha: LinhaDeDecisao, item: ItemDeTitulo, autoria: _Autoria) -> _Decisao:
        tipo = _tipo(linha.decisao, DECISOES_DE_DUPLICIDADE)
        if tipo is None:
            raise _NaoAplicada(_nao_reconhecida(linha, DECISOES_DE_DUPLICIDADE))
        oficial: Titulo | None = None
        if tipo is TipoDeDecisao.MESMA_DIVIDA:
            escolhidos = self._escolhidos(linha, {_chave(titulo): titulo for titulo in item.titulos})
            if len(escolhidos) != 1:
                raise _NaoAplicada(
                    f"Item {linha.item}: 'mesma dívida' exige escolher um só Título oficial do grupo; não aplicada."
                )
            [oficial] = escolhidos
        outros = frozenset(_chave(titulo) for titulo in item.titulos if titulo != oficial) if oficial else frozenset()

        def registrar() -> int:
            return self._armazenamento.registrar_decisao_de_duplicidade(
                execucao=self._execucao,
                item=item.identificador,
                tipo=tipo,
                oficial=_chave(oficial) if oficial else None,
                autor=autoria.autor,
                momento=autoria.momento,
                origem=autoria.origem,
            )

        return _Decisao(item.identificador, tipo, outros, registrar)

    def _confirmacao(self, item: Item, titulos: tuple[Titulo, ...], autoria: _Autoria) -> _Decisao:
        devidos = tuple(replace(titulo, valor_centavos=self._saldos[_chave(titulo)]) for titulo in titulos)
        credito = item.lancamento
        if len(devidos) > 1 and credito.valor_centavos < sum(devido.valor_centavos for devido in devidos):
            raise _NaoAplicada(
                f"Item {item.identificador}: o Crédito é menor que a soma dos Saldos dos Títulos {_descrever(titulos)}; "
                "a plataforma não escolhe como dividir um pagamento parcial; não aplicada."
            )
        encargos = _encargos(devidos, credito, self._encargo)
        principais = {
            _chave(devido): min(credito.valor_centavos, devido.valor_centavos) if len(devidos) == 1 else devido.valor_centavos
            for devido in devidos
        }

        def registrar() -> int:
            decisao = self._registrar(
                item, TipoDeDecisao.CONFIRMAR, titulos, autoria, encargos=encargos, principais=principais
            )
            self._vincular_pagador(decisao, item, titulos)
            return decisao

        return _Decisao(item.identificador, TipoDeDecisao.CONFIRMAR, frozenset(map(_chave, titulos)), registrar)

    def _registrar(
        self,
        item: Item,
        tipo: TipoDeDecisao,
        titulos: tuple[Titulo, ...],
        autoria: _Autoria,
        motivo: str | None = None,
        encargos: Mapping[ChaveDoTitulo, int] | None = None,
        principais: Mapping[ChaveDoTitulo, int] | None = None,
    ) -> int:
        return self._armazenamento.registrar_decisao(
            execucao=self._execucao,
            item=item.identificador,
            tipo=tipo,
            motivo=motivo,
            autor=autoria.autor,
            momento=autoria.momento,
            origem=autoria.origem,
            encargos=encargos if encargos is not None else {_chave(titulo): 0 for titulo in titulos},
            principais=principais,
        )

    def _vincular_pagador(self, decisao: int, item: Item, titulos: tuple[Titulo, ...]) -> None:
        nome = nome_do_pagador(item.lancamento)
        normalizado = nome_normalizado(nome) if nome else ""
        if not normalizado:
            return
        franqueados = sorted({titulo.franqueado for titulo in titulos})
        for franqueado in franqueados:
            por_nome = len(franqueados) == 1 and self._identificou_por_nome(item, franqueado, normalizado)
            self._armazenamento.registrar_vinculo_de_pagador(decisao, normalizado, franqueado, por_nome)

    def _identificou_por_nome(self, item: Item, franqueado: str, nome: str) -> bool:
        evidencia = set(item.evidencia)
        return (
            (
                TipoDeEvidencia.NOME_POR_PREFIXO in evidencia
                and any(nome_normalizado(n).startswith(nome) for n in self._nomes.get(franqueado, ()))
            )
            or (
                TipoDeEvidencia.PARECER_DE_LLM in evidencia
                and any(p.franqueado == franqueado and p.parecer.resposta is Resposta.SIM for p in item.pareceres)
            )
            or (TipoDeEvidencia.PAGADOR_CONHECIDO in evidencia and item.franqueado == franqueado)
        )

    def _escolhidos(self, linha: LinhaDeDecisao, entre: Mapping[ChaveDoTitulo, Titulo]) -> tuple[Titulo, ...]:
        escolhidos: list[Titulo] = []
        for texto in (parte.strip() for parte in linha.titulos.split(";")):
            if not texto:
                continue
            com_sistema = _TITULO_COM_SISTEMA.fullmatch(texto)
            if com_sistema:
                chave = (com_sistema["sistema"].strip(), com_sistema["documento"].strip())
                candidatos = [entre[chave]] if chave in entre else []
            else:
                candidatos = [titulo for (_, documento), titulo in entre.items() if documento == texto]
            if len(candidatos) != 1:
                situacao = "identifica mais de um Título" if candidatos else "não é Título em aberto que possa ser escolhido"
                raise _NaoAplicada(
                    f"Item {linha.item}: '{texto}' {situacao} na execução {self._execucao}; não aplicada."
                )
            escolhidos.extend(candidatos)
        return tuple(dict.fromkeys(escolhidos))


class DecisaoDaTelaRecusada(Exception):
    pass


class SemExecucaoParaDecidir(DecisaoDaTelaRecusada):
    pass


def registrar_decisao_da_tela(
    armazenamento: Armazenamento, linha: LinhaDeDecisao, autor: str, momento: datetime
) -> None:
    execucao = _execucao_para_a_tela(armazenamento)
    resultado = armazenamento.carregar_resultado(execucao)
    if linha.aba == ABA_DA_LISTA_DE_BAIXA:
        itens = {item.identificador for item in resultado.lista_de_baixa}
    elif linha.aba == ABA_DA_FILA_DE_EXCECOES:
        itens = {item.identificador for item in resultado.fila_de_excecoes} | {
            item.identificador for item in resultado.itens_de_titulo
        }
    else:
        raise DecisaoDaTelaRecusada(f"A tela não decide itens de '{linha.aba}'.")
    if linha.item not in itens:
        raise DecisaoDaTelaRecusada(f"Item {linha.item}: não está na {linha.aba} da execução {execucao}.")
    if not linha.decisao.strip():
        raise DecisaoDaTelaRecusada(f"Item {linha.item}: escolha uma decisão.")
    if _tipo_da_lista(linha.decisao) is TipoDeDecisao.REJEITAR and not linha.motivo.strip():
        raise DecisaoDaTelaRecusada(f"Item {linha.item}: a rejeição exige motivo.")
    with armazenamento.transacao():
        armazenamento.registrar_decisao_da_tela(execucao, linha, autor, momento)


def confirmar_o_lote_pela_tela(armazenamento: Armazenamento, autor: str, momento: datetime) -> int:
    execucao = _execucao_para_a_tela(armazenamento)
    decididos = {p.linha.item for p in armazenamento.decisoes_da_tela_pendentes() if p.execucao == execucao}
    a_confirmar = [
        item.identificador
        for item in armazenamento.carregar_resultado(execucao).lista_de_baixa
        if item.identificador not in decididos
    ]
    with armazenamento.transacao():
        for item in a_confirmar:
            armazenamento.registrar_decisao_da_tela(
                execucao, LinhaDeDecisao(ABA_DA_LISTA_DE_BAIXA, item, TipoDeDecisao.CONFIRMAR.value), autor, momento
            )
    return len(a_confirmar)


def _execucao_para_a_tela(armazenamento: Armazenamento) -> int:
    execucao = armazenamento.ultima_execucao()
    if execucao is None:
        raise SemExecucaoParaDecidir("Não há execução registrada; não há o que decidir.")
    return execucao


def aplicar_decisoes(
    armazenamento: Armazenamento, encargo: ParametrosDeEncargo, agora: datetime, workbook: Path | None = None
) -> DecisoesAplicadas:
    ultima = armazenamento.ultima_execucao()
    avisos: list[str] = []
    do_excel: tuple[LinhaDeDecisao, ...] = ()
    autoria_do_excel = _Autoria("", agora, ORIGEM_EXCEL)
    if workbook is not None and workbook.exists():
        try:
            do_excel, autoria_do_excel = _linhas_do_excel(workbook, ultima, agora)
        except _NaoAplicada as nao_aplicada:
            avisos.append(str(nao_aplicada))
    pendentes = armazenamento.decisoes_da_tela_pendentes()
    da_tela: dict[str, LinhaDeDecisao] = {}
    autorias_da_tela: dict[str, _Autoria] = {}
    for pendente in pendentes:
        if pendente.execucao != ultima:
            avisos.append(
                f"Item {pendente.linha.item}: decidido na tela sobre a execução {pendente.execucao}, mas a última "
                f"execução é a execução {ultima}; não aplicada."
            )
            continue
        da_tela[pendente.linha.item] = pendente.linha
        autorias_da_tela[pendente.linha.item] = _Autoria(pendente.autor, pendente.momento, ORIGEM_TELA)
    no_excel: dict[str, LinhaDeDecisao] = {}
    for linha in do_excel:
        no_excel.setdefault(linha.item, linha)
    conflitos = tuple(
        f"Item {item}: decidido no Excel ('{linha.decisao or 'vazio'}') e na tela ('{da_tela[item].decisao}') "
        "desde a última execução; nenhuma das duas decisões aplicada."
        for item, linha in no_excel.items()
        if item in da_tela
    )
    linhas = [(linha, autoria_do_excel) for linha in do_excel if linha.item not in da_tela] + [
        (linha, autorias_da_tela[item]) for item, linha in da_tela.items() if item not in no_excel
    ]
    lidas_da_tela = tuple(pendente.identificador for pendente in pendentes)
    if ultima is None or not linhas:
        return DecisoesAplicadas(DecisoesLidas(nao_aplicadas=tuple(avisos), conflitos=conflitos), (), (), lidas_da_tela)
    interpretacao = _Interpretacao(armazenamento, ultima, encargo)
    repetidos = {
        chave for chave, vezes in Counter((linha.aba, linha.item) for linha, _ in linhas).items() if vezes > 1
    }
    decisoes: list[_Decisao] = []
    for linha, autoria in linhas:
        if (linha.aba, linha.item) in repetidos:
            avisos.append(f"Item {linha.item}: aparece mais de uma vez na aba {linha.aba}; decisão não aplicada.")
            continue
        try:
            decisoes.append(interpretacao.interpretar(linha, autoria))
        except _NaoAplicada as nao_aplicada:
            avisos.append(str(nao_aplicada))
    usos = Counter(chave for decisao in decisoes for chave in decisao.usa)
    registradas: list[int] = []
    duplicidades: list[int] = []
    tipos: list[TipoDeDecisao] = []
    for decisao in decisoes:
        disputados = sorted(chave for chave in decisao.usa if usos[chave] > 1)
        if disputados:
            avisos.append(
                f"Item {decisao.item}: Título(s) {_descrever_chaves(disputados)} usado(s) por mais de uma decisão "
                "desde a última execução; nenhuma delas aplicada."
            )
            continue
        (duplicidades if decisao.tipo in DECISOES_DE_DUPLICIDADE else registradas).append(decisao.registrar())
        tipos.append(decisao.tipo)
    return DecisoesAplicadas(
        DecisoesLidas(
            confirmadas=tipos.count(TipoDeDecisao.CONFIRMAR),
            rejeitadas=tipos.count(TipoDeDecisao.REJEITAR),
            nao_aplicadas=tuple(avisos),
            classificadas=sum(1 for tipo in tipos if tipo.classifica_credito_sem_titulo),
            conciliados_fora=tipos.count(TipoDeDecisao.CONCILIADO_FORA),
            fontes_nao_integradas=tipos.count(TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA),
            duplicidades=len(duplicidades),
            revertidas=tipos.count(TipoDeDecisao.REVERTER),
            conflitos=conflitos,
        ),
        tuple(registradas),
        tuple(duplicidades),
        lidas_da_tela,
    )


def _linhas_do_excel(
    caminho: Path, ultima: int | None, agora: datetime
) -> tuple[tuple[LinhaDeDecisao, ...], _Autoria]:
    try:
        lido = _ler(caminho)
    except (OSError, KeyError, ValueError, BadZipFile, InvalidFileException) as erro:
        raise _NaoAplicada(f"O workbook {caminho.name} não pôde ser lido ({erro}); nenhuma decisão aplicada.")
    if not lido.autor:
        raise _NaoAplicada(
            f"O workbook {caminho.name} não foi salvo pela Analista (sem autor da última alteração); "
            "nenhuma decisão aplicada."
        )
    if ultima is None or lido.execucao != ultima:
        raise _NaoAplicada(
            f"O workbook {caminho.name} é da execução {lido.execucao}, mas a última execução é a execução {ultima}; "
            "nenhuma decisão aplicada."
        )
    return lido.linhas, _Autoria(lido.autor, lido.momento or agora, ORIGEM_EXCEL)


def _tipo_da_lista(decisao: str) -> TipoDeDecisao | None:
    normalizada = decisao.strip().lower()
    if normalizada == TipoDeDecisao.CONFIRMAR.value:
        return TipoDeDecisao.CONFIRMAR
    if normalizada in ("", TipoDeDecisao.REJEITAR.value):
        return TipoDeDecisao.REJEITAR
    return None


def _tipo(decisao: str, aceitos: Iterable[TipoDeDecisao]) -> TipoDeDecisao | None:
    return next((tipo for tipo in aceitos if _sem_acento(tipo.value) == _sem_acento(decisao)), None)


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return " ".join("".join(c for c in decomposto if not unicodedata.combining(c)).lower().split())


def _nao_reconhecida(linha: LinhaDeDecisao, aceitos: Iterable[TipoDeDecisao]) -> str:
    opcoes = ", ".join(f"'{tipo.value}'" for tipo in aceitos)
    return f"Item {linha.item}: decisão '{linha.decisao}' não reconhecida (use {opcoes}); não aplicada."


def _chave(titulo: Titulo) -> ChaveDoTitulo:
    return (titulo.sistema_de_origem, titulo.documento)


def _descrever(titulos: Iterable[Titulo]) -> str:
    return _descrever_chaves(map(_chave, titulos))


def _descrever_chaves(chaves: Iterable[ChaveDoTitulo]) -> str:
    return ", ".join(f"{documento} ({sistema})" for sistema, documento in chaves)


def _encargos(titulos: tuple[Titulo, ...], credito: Lancamento, encargo: ParametrosDeEncargo) -> dict[ChaveDoTitulo, int]:
    return {
        _chave(titulo): enquadrar(
            titulo,
            credito.valor_centavos if len(titulos) == 1 else titulo.valor_centavos,
            credito.data,
            encargo,
        ).encargo_pago_centavos
        for titulo in titulos
    }


def _ler(caminho: Path) -> _WorkbookLido:
    livro = load_workbook(caminho, read_only=True)
    try:
        execucao = next(
            (
                linha[1]
                for linha in livro["Resumo"].iter_rows(values_only=True)
                if linha and linha[0] == LINHA_DA_EXECUCAO_NO_RESUMO
            ),
            None,
        )
        lista = _linhas_da_aba(
            livro[ABA_DA_LISTA_DE_BAIXA].iter_rows(values_only=True),
            ABA_DA_LISTA_DE_BAIXA,
            {"motivo": COLUNA_DO_MOTIVO_DA_REJEICAO},
        )
        fila = _linhas_da_aba(
            livro[ABA_DA_FILA_DE_EXCECOES].iter_rows(values_only=True),
            ABA_DA_FILA_DE_EXCECOES,
            {
                "titulos": COLUNA_DOS_TITULOS_ESCOLHIDOS,
                "franqueado": COLUNA_DO_FRANQUEADO_DO_CONCILIADO_FORA,
                "referencia": COLUNA_DA_REFERENCIA_DO_CONCILIADO_FORA,
            },
        )
        reversoes = (
            tuple(
                LinhaDeDecisao(ABA_DE_REVERSAO, _celula(linha, 0), TipoDeDecisao.REVERTER.value, _celula(linha, 1))
                for linha in livro[ABA_DE_REVERSAO].iter_rows(min_row=2, values_only=True)
                if _celula(linha, 0)
            )
            if ABA_DE_REVERSAO in livro.sheetnames
            else ()
        )
        return _WorkbookLido(
            execucao=execucao,
            autor=(livro.properties.lastModifiedBy or "").strip(),
            momento=livro.properties.modified,
            linhas=(*lista, *(linha for linha in fila if linha.decisao), *reversoes),
        )
    finally:
        livro.close()


def _linhas_da_aba(
    linhas: Iterable[tuple[object, ...]], aba: str, campos: Mapping[str, str]
) -> tuple[LinhaDeDecisao, ...]:
    cabecalho, *dados = linhas
    colunas = [str(c) for c in cabecalho]
    item, decisao = colunas.index(COLUNA_DO_ITEM), colunas.index(COLUNA_DA_DECISAO)
    indices = {campo: colunas.index(coluna) for campo, coluna in campos.items()}
    return tuple(
        LinhaDeDecisao(
            aba,
            _celula(linha, item),
            _celula(linha, decisao),
            **{campo: _celula(linha, indice) for campo, indice in indices.items()},
        )
        for linha in dados
        if _celula(linha, item)
    )


def _celula(linha: tuple[object, ...], coluna: int) -> str:
    valor = linha[coluna] if coluna < len(linha) else None
    return "" if valor is None else str(valor).strip()
