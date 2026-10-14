import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from conciliacao.dominio import (
    ArquivoRecusado,
    ChaveDoIdentificador,
    OrigemDoIdentificador,
    ComponentesDoValor,
    RetornoDeCobranca,
    TipoDeIdentificador,
    VinculoDeCobranca,
    ConfirmacaoEmVigor,
    ConfirmacaoRevertida,
    SituacaoNoErp,
    TituloConfirmado,
    TituloNoAcompanhamento,
    BaixaManual,
    DecisaoDaTela,
    DecisaoRegistrada,
    DecisaoSobreProposta,
    DecisoesLidas,
    Metricas,
    ParteAutomatica,
    PrimeiroParecerDaIa,
    ParRejeitado,
    RegraDaProposta,
    TipoDeDecisao,
    Canal,
    CausaRaiz,
    ChaveNatural,
    Classificacao,
    DataDeReferencia,
    Destino,
    Franqueado,
    Item,
    ItemDeTitulo,
    Lancamento,
    LinhaDeDecisao,
    MotivoDeNaoIdentificacao,
    Natureza,
    PagadorConhecido,
    Parecer,
    ParecerSobreFranqueado,
    PossivelDuplicidade,
    Resposta,
    Resultado,
    Resumo,
    TipoDeEvidencia,
    Titulo,
    TituloACancelar,
    TituloNaCobranca,
    TotalDoDestino,
    UltimaDataDaConta,
)
from conciliacao.normalizacao import raiz_do_cnpj

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS lancamentos (
    id INTEGER PRIMARY KEY,
    banco TEXT NOT NULL,
    conta TEXT NOT NULL,
    data TEXT NOT NULL,
    natureza TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL,
    historico TEXT NOT NULL,
    documento TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    UNIQUE (banco, conta, data, natureza, valor_centavos, historico, documento, ordinal)
);
CREATE TABLE IF NOT EXISTS execucoes (
    id INTEGER PRIMARY KEY,
    momento TEXT NOT NULL,
    lancamentos_novos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS arquivos (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    nome TEXT NOT NULL,
    motivo_da_recusa TEXT
);
CREATE TABLE IF NOT EXISTS titulos (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    sistema_de_origem TEXT NOT NULL,
    documento TEXT NOT NULL,
    nome_do_franqueado TEXT NOT NULL,
    cnpj TEXT NOT NULL,
    nosso_numero TEXT,
    vencimento TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS itens (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id),
    destino TEXT NOT NULL,
    explicacao TEXT NOT NULL,
    motivo TEXT
);
CREATE TABLE IF NOT EXISTS itens_regras (
    item_id INTEGER NOT NULL UNIQUE REFERENCES itens(id),
    regra TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS itens_evidencias (
    item_id INTEGER NOT NULL REFERENCES itens(id),
    tipo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS itens_pareceres (
    item_id INTEGER NOT NULL REFERENCES itens(id),
    franqueado TEXT NOT NULL,
    resposta TEXT NOT NULL,
    explicacao TEXT NOT NULL,
    modelo TEXT NOT NULL,
    versao_do_prompt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS itens_atribuicoes (
    item_id INTEGER NOT NULL UNIQUE REFERENCES itens(id),
    franqueado TEXT,
    canal TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS itens_titulos (
    item_id INTEGER NOT NULL REFERENCES itens(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id)
);
CREATE TABLE IF NOT EXISTS duplicidades (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS itens_de_titulo (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    duplicidade_id INTEGER NOT NULL REFERENCES duplicidades(id),
    explicacao TEXT NOT NULL,
    motivo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS itens_de_titulo_titulos (
    item_id INTEGER NOT NULL REFERENCES itens_de_titulo(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id)
);
CREATE TABLE IF NOT EXISTS ultimas_datas_das_contas (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    banco TEXT NOT NULL,
    conta TEXT NOT NULL,
    ultima_data TEXT
);
CREATE TABLE IF NOT EXISTS cobranca (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id),
    saldo_centavos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes (
    id INTEGER PRIMARY KEY,
    lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id),
    execucao_do_item INTEGER NOT NULL REFERENCES execucoes(id),
    execucao_que_aplicou INTEGER REFERENCES execucoes(id),
    tipo TEXT NOT NULL,
    motivo TEXT,
    autor TEXT NOT NULL,
    momento TEXT NOT NULL,
    origem TEXT NOT NULL,
    explicacao TEXT NOT NULL,
    regra TEXT
);
CREATE TABLE IF NOT EXISTS decisoes_evidencias (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id),
    tipo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes_titulos (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id),
    encargo_centavos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS avisos_das_decisoes (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes_pareceres (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id),
    franqueado TEXT NOT NULL,
    resposta TEXT NOT NULL,
    explicacao TEXT NOT NULL,
    modelo TEXT NOT NULL,
    versao_do_prompt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes_conciliado_fora (
    decisao_id INTEGER NOT NULL UNIQUE REFERENCES decisoes(id),
    franqueado TEXT NOT NULL,
    referencia TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pagadores_conhecidos (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id),
    nome TEXT NOT NULL,
    franqueado TEXT NOT NULL,
    por_nome INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes_de_duplicidade (
    id INTEGER PRIMARY KEY,
    item_de_titulo_id INTEGER NOT NULL REFERENCES itens_de_titulo(id),
    execucao_que_aplicou INTEGER REFERENCES execucoes(id),
    tipo TEXT NOT NULL,
    titulo_oficial_id INTEGER REFERENCES titulos(id),
    autor TEXT NOT NULL,
    momento TEXT NOT NULL,
    origem TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cobranca_creditos_candidatos (
    cobranca_id INTEGER NOT NULL REFERENCES cobranca(id),
    lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id)
);
CREATE TABLE IF NOT EXISTS exportacoes (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    sistema_de_origem TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes_principais (
    decisao_id INTEGER NOT NULL REFERENCES decisoes(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id),
    principal_centavos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reversoes (
    confirmacao_id INTEGER NOT NULL UNIQUE REFERENCES decisoes(id),
    reversao_id INTEGER NOT NULL UNIQUE REFERENCES decisoes(id)
);
CREATE TABLE IF NOT EXISTS divergencias_de_baixa (
    confirmacao_id INTEGER NOT NULL REFERENCES decisoes(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id),
    execucao_id INTEGER REFERENCES execucoes(id),
    explicacao TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acompanhamento_do_erp (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    situacao TEXT NOT NULL,
    titulo_id INTEGER NOT NULL REFERENCES titulos(id),
    item TEXT,
    explicacao TEXT NOT NULL,
    saldo_centavos INTEGER
);
CREATE TABLE IF NOT EXISTS decisoes_da_tela (
    id INTEGER PRIMARY KEY,
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    aba TEXT NOT NULL,
    item TEXT NOT NULL,
    decisao TEXT NOT NULL,
    motivo TEXT NOT NULL,
    titulos TEXT NOT NULL,
    franqueado TEXT NOT NULL,
    referencia TEXT NOT NULL,
    autor TEXT NOT NULL,
    momento TEXT NOT NULL,
    execucao_que_leu INTEGER REFERENCES execucoes(id)
);
CREATE TABLE IF NOT EXISTS conflitos_das_decisoes (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS limites_de_queda (
    execucao_id INTEGER NOT NULL UNIQUE REFERENCES execucoes(id),
    pontos_percentuais TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vinculos_de_cobranca (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    identificador TEXT NOT NULL,
    origem TEXT NOT NULL,
    sistema_de_origem TEXT NOT NULL,
    documento TEXT NOT NULL,
    cnpj TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL,
    vencimento TEXT NOT NULL,
    momento_da_emissao TEXT NOT NULL,
    momento_do_envio TEXT,
    UNIQUE (tipo, identificador),
    UNIQUE (tipo, sistema_de_origem, documento)
);
CREATE TABLE IF NOT EXISTS retornos_de_cobranca (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL,
    chave_natural TEXT NOT NULL,
    identificador TEXT NOT NULL,
    banco TEXT NOT NULL,
    conta TEXT NOT NULL,
    data TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL,
    principal_centavos INTEGER,
    multa_centavos INTEGER,
    juros_centavos INTEGER,
    UNIQUE (tipo, chave_natural)
);
CREATE TABLE IF NOT EXISTS enriquecimentos (
    retorno_id INTEGER NOT NULL UNIQUE REFERENCES retornos_de_cobranca(id),
    lancamento_id INTEGER NOT NULL UNIQUE REFERENCES lancamentos(id)
);
"""

_SEM_REVERSAO = "d.id NOT IN (SELECT confirmacao_id FROM reversoes)"
_EM_VIGOR = f"{_SEM_REVERSAO} AND d.id NOT IN (SELECT confirmacao_id FROM divergencias_de_baixa)"

_COLUNAS_LANCAMENTO = "banco, conta, data, natureza, valor_centavos, historico, documento, ordinal"
_COLUNAS_DO_LANCAMENTO_L = ", ".join(f"l.{coluna}" for coluna in _COLUNAS_LANCAMENTO.split(", "))
_COLUNAS_VINCULO = (
    "tipo, identificador, origem, sistema_de_origem, documento, cnpj, valor_centavos, vencimento"
)
_COLUNAS_RETORNO = (
    "r.tipo, r.chave_natural, r.identificador, r.banco, r.conta, r.data, r.valor_centavos,"
    " r.principal_centavos, r.multa_centavos, r.juros_centavos"
)
_COLUNAS_TITULO = (
    "t.sistema_de_origem, t.documento, t.nome_do_franqueado, t.cnpj, t.nosso_numero, t.vencimento, t.valor_centavos"
)


class Armazenamento:
    def __init__(self, caminho: Path) -> None:
        self._conexao = sqlite3.connect(caminho, autocommit=False)
        self._conexao.execute("PRAGMA foreign_keys = ON")
        self._renomear_coluna_antiga_do_nome_do_franqueado()
        self._conexao.executescript(_ESQUEMA)
        self._conexao.commit()

    def fechar(self) -> None:
        self._conexao.close()

    def _renomear_coluna_antiga_do_nome_do_franqueado(self) -> None:
        colunas = {linha[1] for linha in self._conexao.execute("PRAGMA table_info(titulos)")}
        if "cliente" in colunas:
            self._conexao.execute("ALTER TABLE titulos RENAME COLUMN cliente TO nome_do_franqueado")

    @contextmanager
    def transacao(self) -> Iterator[None]:
        try:
            yield
        except BaseException:
            self._conexao.rollback()
            raise
        self._conexao.commit()

    def guardar_lancamentos(self, lancamentos: Iterable[Lancamento]) -> tuple[dict[ChaveNatural, int], int]:
        identificadores: dict[ChaveNatural, int] = {}
        novos = 0
        for lancamento in lancamentos:
            chave = lancamento.chave_natural
            if chave in identificadores:
                continue
            parametros = _parametros_da_chave(chave)
            linha = self._conexao.execute(
                f"SELECT id FROM lancamentos WHERE ({_COLUNAS_LANCAMENTO}) = (?, ?, ?, ?, ?, ?, ?, ?)", parametros
            ).fetchone()
            if linha is None:
                cursor = self._conexao.execute(
                    f"INSERT INTO lancamentos ({_COLUNAS_LANCAMENTO}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", parametros
                )
                assert cursor.lastrowid is not None
                identificadores[chave] = cursor.lastrowid
                novos += 1
            else:
                identificadores[chave] = linha[0]
        return identificadores, novos

    def creditos_vivos(self) -> dict[int, Lancamento]:
        encerram = [tipo.value for tipo in TipoDeDecisao if tipo.encerra_o_credito]
        linhas = self._conexao.execute(
            f"SELECT id, {_COLUNAS_LANCAMENTO} FROM lancamentos WHERE natureza = ?"
            " AND id NOT IN (SELECT d.lancamento_id FROM decisoes d"
            f" WHERE d.tipo IN ({_marcadores(encerram)}) AND {_EM_VIGOR})"
            " ORDER BY data, id",
            (Natureza.CREDITO.value, *encerram),
        )
        return {linha[0]: _lancamento(linha[1:]) for linha in linhas}

    def classificados_como(self, tipo: TipoDeDecisao) -> dict[ChaveNatural, datetime]:
        linhas = self._conexao.execute(
            f"SELECT d.momento, {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d JOIN lancamentos l ON l.id = d.lancamento_id"
            " WHERE d.tipo = ? ORDER BY d.id",
            (tipo.value,),
        )
        return {_lancamento(lancamento).chave_natural: datetime.fromisoformat(momento) for momento, *lancamento in linhas}

    def titulos_da_execucao(self, execucao: int) -> list[Titulo]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_TITULO} FROM titulos t WHERE t.execucao_id = ? ORDER BY t.id", (execucao,)
        )
        return [_titulo(linha) for linha in linhas]

    def titulos_cancelados_na_origem(self) -> set[tuple[str, str]]:
        return {
            (cancelado.sistema_de_origem, cancelado.documento)
            for _, titulos, oficial in self._mesmas_dividas()
            for cancelado in titulos
            if cancelado != oficial
        }

    def duplicidades_decididas(self) -> set[frozenset[tuple[str, str]]]:
        linhas = self._conexao.execute("SELECT item_de_titulo_id FROM decisoes_de_duplicidade").fetchall()
        return {
            frozenset((t.sistema_de_origem, t.documento) for t in self._titulos_ligados("itens_de_titulo_titulos", item))
            for (item,) in linhas
        }

    def pagadores_conhecidos(self) -> list[PagadorConhecido]:
        linhas = self._conexao.execute(
            "SELECT p.nome, p.franqueado, MAX(p.por_nome) FROM pagadores_conhecidos p"
            f" JOIN decisoes d ON d.id = p.decisao_id WHERE d.tipo = ? AND {_SEM_REVERSAO}"
            " GROUP BY p.nome, p.franqueado ORDER BY p.nome, p.franqueado",
            (TipoDeDecisao.CONFIRMAR.value,),
        )
        franqueados: dict[str, list[str]] = defaultdict(list)
        por_nome: set[str] = set()
        for nome, franqueado, confirmado_por_nome in linhas:
            franqueados[nome].append(franqueado)
            if confirmado_por_nome:
                por_nome.add(nome)
        return [PagadorConhecido(nome, tuple(f)) for nome, f in franqueados.items() if nome in por_nome]

    def registrar_decisao_da_tela(self, execucao: int, linha: LinhaDeDecisao, autor: str, momento: datetime) -> None:
        self._conexao.execute(
            "DELETE FROM decisoes_da_tela WHERE execucao_id = ? AND item = ? AND execucao_que_leu IS NULL",
            (execucao, linha.item),
        )
        self._conexao.execute(
            "INSERT INTO decisoes_da_tela (execucao_id, aba, item, decisao, motivo, titulos, franqueado, referencia,"
            " autor, momento) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execucao,
                linha.aba,
                linha.item,
                linha.decisao,
                linha.motivo,
                linha.titulos,
                linha.franqueado,
                linha.referencia,
                autor,
                momento.isoformat(),
            ),
        )

    def decisoes_da_tela_pendentes(self) -> list[DecisaoDaTela]:
        linhas = self._conexao.execute(
            "SELECT id, execucao_id, aba, item, decisao, motivo, titulos, franqueado, referencia, autor, momento"
            " FROM decisoes_da_tela WHERE execucao_que_leu IS NULL ORDER BY id"
        )
        return [
            DecisaoDaTela(
                identificador,
                execucao,
                LinhaDeDecisao(aba, item, decisao, motivo, titulos, franqueado, referencia),
                autor,
                datetime.fromisoformat(momento),
            )
            for identificador, execucao, aba, item, decisao, motivo, titulos, franqueado, referencia, autor, momento in linhas
        ]

    def ultima_execucao(self) -> int | None:
        (execucao,) = self._conexao.execute("SELECT MAX(id) FROM execucoes").fetchone()
        return int(execucao) if execucao is not None else None

    def confirmacoes_em_vigor(self) -> list[ConfirmacaoEmVigor]:
        linhas = self._conexao.execute(
            f"SELECT d.id, d.lancamento_id, d.execucao_do_item, {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d"
            f" JOIN lancamentos l ON l.id = d.lancamento_id WHERE d.tipo = ? AND {_EM_VIGOR} ORDER BY d.id",
            (TipoDeDecisao.CONFIRMAR.value,),
        ).fetchall()
        return [
            ConfirmacaoEmVigor(
                decisao=decisao,
                item=_identificador_do_item(lancamento_id),
                credito=_lancamento(lancamento).chave_natural,
                titulos=tuple(self._titulos_confirmados(decisao, execucao_do_item)),
            )
            for decisao, lancamento_id, execucao_do_item, *lancamento in linhas
        ]

    def _titulos_confirmados(self, decisao: int, execucao_do_item: int) -> Iterator[TituloConfirmado]:
        linhas = self._conexao.execute(
            "SELECT dt.titulo_id, COALESCE(p.principal_centavos, t.valor_centavos) FROM decisoes_titulos dt"
            " JOIN titulos t ON t.id = dt.titulo_id LEFT JOIN decisoes_principais p"
            " ON p.decisao_id = dt.decisao_id AND p.titulo_id = dt.titulo_id WHERE dt.decisao_id = ? ORDER BY t.id",
            (decisao,),
        ).fetchall()
        for titulo_id, principal in linhas:
            titulo = self._titulo(titulo_id)
            posteriores = self._conexao.execute(
                "SELECT DISTINCT valor_centavos FROM titulos WHERE sistema_de_origem = ? AND documento = ?"
                " AND execucao_id > ?",
                (titulo.sistema_de_origem, titulo.documento, execucao_do_item),
            )
            yield TituloConfirmado(titulo, principal, frozenset(valor for (valor,) in posteriores))

    def confirmacoes_revertidas(self) -> list[ConfirmacaoRevertida]:
        linhas = self._conexao.execute(
            "SELECT r.confirmacao_id, rv.lancamento_id, rv.motivo, rv.execucao_que_aplicou FROM reversoes r"
            " JOIN decisoes rv ON rv.id = r.reversao_id ORDER BY rv.id"
        ).fetchall()
        return [
            ConfirmacaoRevertida(
                item=_identificador_do_item(lancamento_id),
                motivo=motivo,
                sem_reaparecer=tuple(
                    titulo
                    for titulo in self._titulos_ligados("decisoes_titulos", confirmacao, coluna="decisao_id")
                    if aplicada is None or not self._conexao.execute(
                        "SELECT 1 FROM titulos WHERE sistema_de_origem = ? AND documento = ? AND execucao_id >= ?",
                        (titulo.sistema_de_origem, titulo.documento, aplicada),
                    ).fetchone()
                ),
            )
            for confirmacao, lancamento_id, motivo, aplicada in linhas
        ]

    def confirmacao_em_vigor_do_item(self, item: str) -> int | None:
        if not (item.startswith(_PREFIXO_DO_ITEM) and item.removeprefix(_PREFIXO_DO_ITEM).isdigit()):
            return None
        linha = self._conexao.execute(
            f"SELECT d.id FROM decisoes d WHERE d.lancamento_id = ? AND d.tipo = ? AND {_EM_VIGOR}",
            (_lancamento_do_item(item), TipoDeDecisao.CONFIRMAR.value),
        ).fetchone()
        return int(linha[0]) if linha else None

    def fotografia_anterior(self, sistemas: Iterable[str]) -> list[Titulo]:
        titulos: list[Titulo] = []
        for sistema in sorted(set(sistemas)):
            linhas = self._conexao.execute(
                f"SELECT {_COLUNAS_TITULO} FROM titulos t WHERE t.sistema_de_origem = ? AND t.execucao_id ="
                " (SELECT MAX(execucao_id) FROM exportacoes WHERE sistema_de_origem = ?) ORDER BY t.id",
                (sistema, sistema),
            )
            titulos.extend(_titulo(linha) for linha in linhas)
        return titulos

    def ultima_fotografia(self) -> list[Titulo]:
        sistemas = self._conexao.execute("SELECT DISTINCT sistema_de_origem FROM exportacoes")
        return self.fotografia_anterior(sistema for (sistema,) in sistemas.fetchall())

    def identificadores_gerados(self, tipo: TipoDeIdentificador) -> int:
        (quantidade,) = self._conexao.execute(
            "SELECT COUNT(*) FROM vinculos_de_cobranca WHERE tipo = ?", (tipo.value,)
        ).fetchone()
        return int(quantidade)

    def registrar_vinculo(self, vinculo: VinculoDeCobranca) -> None:
        self._conexao.execute(
            f"INSERT INTO vinculos_de_cobranca ({_COLUNAS_VINCULO}, momento_da_emissao)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                vinculo.tipo.value,
                vinculo.identificador,
                vinculo.origem.value,
                vinculo.sistema_de_origem,
                vinculo.documento,
                vinculo.cnpj,
                vinculo.valor_centavos,
                vinculo.vencimento.isoformat(),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

    def registrar_envio(self, vinculo: VinculoDeCobranca) -> None:
        self._conexao.execute(
            "UPDATE vinculos_de_cobranca SET momento_do_envio = ? WHERE tipo = ? AND identificador = ?",
            (datetime.now().isoformat(timespec="seconds"), vinculo.tipo.value, vinculo.identificador),
        )

    def vinculos_de_cobranca(self) -> list[VinculoDeCobranca]:
        linhas = self._conexao.execute(f"SELECT {_COLUNAS_VINCULO} FROM vinculos_de_cobranca ORDER BY id")
        return [_vinculo(linha) for linha in linhas]

    def vinculos_enviados(self) -> set[ChaveDoIdentificador]:
        linhas = self._conexao.execute(
            "SELECT tipo, identificador FROM vinculos_de_cobranca WHERE momento_do_envio IS NOT NULL"
        )
        return {(TipoDeIdentificador(tipo), identificador) for tipo, identificador in linhas}

    def guardar_retornos(self, retornos: Iterable[RetornoDeCobranca]) -> None:
        self._conexao.executemany(
            "INSERT OR IGNORE INTO retornos_de_cobranca"
            " (tipo, chave_natural, identificador, banco, conta, data, valor_centavos,"
            " principal_centavos, multa_centavos, juros_centavos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r.tipo.value,
                    r.chave_natural,
                    r.identificador,
                    r.banco,
                    r.conta,
                    r.data.isoformat(),
                    r.valor_centavos,
                    *(
                        (r.componentes.principal_centavos, r.componentes.multa_centavos, r.componentes.juros_centavos)
                        if r.componentes
                        else (None, None, None)
                    ),
                )
                for r in retornos
            ],
        )

    def retornos_sem_credito(self) -> list[RetornoDeCobranca]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_RETORNO} FROM retornos_de_cobranca r"
            " WHERE r.id NOT IN (SELECT retorno_id FROM enriquecimentos) ORDER BY r.id"
        )
        return [_retorno(linha) for linha in linhas]

    def registrar_enriquecimento(self, retorno: RetornoDeCobranca, lancamento_id: int) -> None:
        self._conexao.execute(
            "INSERT INTO enriquecimentos (retorno_id, lancamento_id)"
            " SELECT id, ? FROM retornos_de_cobranca WHERE tipo = ? AND chave_natural = ?",
            (lancamento_id, retorno.tipo.value, retorno.chave_natural),
        )

    def retornos_dos_creditos(self) -> dict[ChaveNatural, RetornoDeCobranca]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_DO_LANCAMENTO_L}, {_COLUNAS_RETORNO} FROM enriquecimentos e"
            " JOIN lancamentos l ON l.id = e.lancamento_id JOIN retornos_de_cobranca r ON r.id = e.retorno_id"
        )
        return {_lancamento(linha[:8]).chave_natural: _retorno(linha[8:]) for linha in linhas}

    def titulos_propostos_na_ultima_execucao(self) -> set[tuple[str, str]]:
        linhas = self._conexao.execute(
            "SELECT DISTINCT t.sistema_de_origem, t.documento FROM itens i JOIN itens_titulos it ON it.item_id = i.id"
            " JOIN titulos t ON t.id = it.titulo_id WHERE i.execucao_id = (SELECT MAX(id) FROM execucoes)"
        )
        return {(sistema, documento) for sistema, documento in linhas}

    def registrar_divergencia(self, confirmacao: int, baixado: Titulo, explicacao: str) -> None:
        self._conexao.execute(
            "INSERT INTO divergencias_de_baixa (confirmacao_id, titulo_id, explicacao) VALUES (?, ?, ?)",
            (confirmacao, self._ultimo_id_do_titulo(baixado), explicacao),
        )

    def divergencias(self) -> dict[ChaveNatural, list[str]]:
        linhas = self._conexao.execute(
            f"SELECT v.explicacao, {_COLUNAS_DO_LANCAMENTO_L} FROM divergencias_de_baixa v"
            " JOIN decisoes d ON d.id = v.confirmacao_id JOIN lancamentos l ON l.id = d.lancamento_id ORDER BY v.rowid"
        )
        por_credito: dict[ChaveNatural, list[str]] = defaultdict(list)
        for explicacao, *lancamento in linhas:
            por_credito[_lancamento(lancamento).chave_natural].append(explicacao)
        return dict(por_credito)

    def registrar_reversao(
        self, confirmacao: int, motivo: str, autor: str, momento: datetime, origem: str
    ) -> int:
        lancamento_id, execucao_do_item, explicacao = self._conexao.execute(
            "SELECT lancamento_id, execucao_do_item, explicacao FROM decisoes WHERE id = ?", (confirmacao,)
        ).fetchone()
        reversao = self._conexao.execute(
            "INSERT INTO decisoes (lancamento_id, execucao_do_item, tipo, motivo, autor, momento, origem, explicacao)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                lancamento_id,
                execucao_do_item,
                TipoDeDecisao.REVERTER.value,
                motivo,
                autor,
                momento.isoformat(),
                origem,
                explicacao,
            ),
        ).lastrowid
        assert reversao is not None
        self._conexao.execute(
            "INSERT INTO decisoes_titulos (decisao_id, titulo_id, encargo_centavos)"
            " SELECT ?, titulo_id, 0 FROM decisoes_titulos WHERE decisao_id = ? ORDER BY rowid",
            (reversao, confirmacao),
        )
        self._conexao.execute(
            "INSERT INTO reversoes (confirmacao_id, reversao_id) VALUES (?, ?)", (confirmacao, reversao)
        )
        return reversao

    def _ultimo_id_do_titulo(self, titulo: Titulo) -> int:
        (titulo_id,) = self._conexao.execute(
            "SELECT MAX(id) FROM titulos WHERE sistema_de_origem = ? AND documento = ?",
            (titulo.sistema_de_origem, titulo.documento),
        ).fetchone()
        assert titulo_id is not None
        return int(titulo_id)

    def _mesmas_dividas(self, ate_a_execucao: int | None = None) -> Iterator[tuple[int, tuple[Titulo, ...], Titulo]]:
        filtro = " AND dd.execucao_que_aplicou <= ?" if ate_a_execucao is not None else ""
        linhas = self._conexao.execute(
            "SELECT it.duplicidade_id, dd.item_de_titulo_id, dd.titulo_oficial_id FROM decisoes_de_duplicidade dd"
            f" JOIN itens_de_titulo it ON it.id = dd.item_de_titulo_id WHERE dd.tipo = ?{filtro} ORDER BY dd.id",
            (TipoDeDecisao.MESMA_DIVIDA.value, *(() if ate_a_execucao is None else (ate_a_execucao,))),
        ).fetchall()
        for duplicidade, item, oficial in linhas:
            yield duplicidade, self._titulos_ligados("itens_de_titulo_titulos", item), self._titulo(oficial)

    def pares_rejeitados(self) -> list[ParRejeitado]:
        linhas = self._conexao.execute(
            f"SELECT d.tipo, t.sistema_de_origem, t.documento, d.motivo, {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d"
            " JOIN decisoes_titulos dt ON dt.decisao_id = d.id JOIN titulos t ON t.id = dt.titulo_id"
            " JOIN lancamentos l ON l.id = d.lancamento_id WHERE d.tipo IN (?, ?) ORDER BY d.id, t.id",
            (TipoDeDecisao.REJEITAR.value, TipoDeDecisao.REVERTER.value),
        )
        return [
            ParRejeitado(
                _lancamento(lancamento).chave_natural,
                sistema,
                documento,
                f"confirmação revertida, {motivo}" if tipo == TipoDeDecisao.REVERTER.value else motivo,
            )
            for tipo, sistema, documento, motivo, *lancamento in linhas
        ]

    def registrar_decisao(
        self,
        execucao: int,
        item: str,
        tipo: TipoDeDecisao,
        motivo: str | None,
        autor: str,
        momento: datetime,
        origem: str,
        encargos: Mapping[tuple[str, str], int],
        principais: Mapping[tuple[str, str], int] | None = None,
    ) -> int:
        lancamento_id = _lancamento_do_item(item)
        item_id, explicacao, regra = self._conexao.execute(
            "SELECT i.id, i.explicacao, r.regra FROM itens i LEFT JOIN itens_regras r ON r.item_id = i.id"
            " WHERE i.execucao_id = ? AND i.lancamento_id = ?",
            (execucao, lancamento_id),
        ).fetchone()
        decisao = self._conexao.execute(
            "INSERT INTO decisoes (lancamento_id, execucao_do_item, tipo, motivo, autor, momento, origem, explicacao,"
            " regra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lancamento_id, execucao, tipo.value, motivo, autor, momento.isoformat(), origem, explicacao, regra),
        ).lastrowid
        assert decisao is not None
        self._conexao.execute(
            "INSERT INTO decisoes_evidencias (decisao_id, tipo) SELECT ?, tipo FROM itens_evidencias"
            " WHERE item_id = ? ORDER BY rowid",
            (decisao, item_id),
        )
        self._conexao.execute(
            "INSERT INTO decisoes_pareceres (decisao_id, franqueado, resposta, explicacao, modelo, versao_do_prompt)"
            " SELECT ?, franqueado, resposta, explicacao, modelo, versao_do_prompt FROM itens_pareceres"
            " WHERE item_id = ? ORDER BY rowid",
            (decisao, item_id),
        )
        self._conexao.executemany(
            "INSERT INTO decisoes_titulos (decisao_id, titulo_id, encargo_centavos) VALUES (?, ?, ?)",
            [
                (decisao, self._id_do_titulo(execucao, sistema, documento), encargo)
                for (sistema, documento), encargo in encargos.items()
            ],
        )
        self._conexao.executemany(
            "INSERT INTO decisoes_principais (decisao_id, titulo_id, principal_centavos) VALUES (?, ?, ?)",
            [
                (decisao, self._id_do_titulo(execucao, sistema, documento), principal)
                for (sistema, documento), principal in (principais or {}).items()
            ],
        )
        return decisao

    def registrar_conciliado_fora(self, decisao: int, franqueado: str, referencia: str) -> None:
        self._conexao.execute(
            "INSERT INTO decisoes_conciliado_fora (decisao_id, franqueado, referencia) VALUES (?, ?, ?)",
            (decisao, franqueado, referencia),
        )

    def registrar_vinculo_de_pagador(self, decisao: int, nome: str, franqueado: str, por_nome: bool) -> None:
        self._conexao.execute(
            "INSERT INTO pagadores_conhecidos (decisao_id, nome, franqueado, por_nome) VALUES (?, ?, ?, ?)",
            (decisao, nome, franqueado, int(por_nome)),
        )

    def registrar_decisao_de_duplicidade(
        self,
        execucao: int,
        item: str,
        tipo: TipoDeDecisao,
        oficial: tuple[str, str] | None,
        autor: str,
        momento: datetime,
        origem: str,
    ) -> int:
        (item_id,) = self._conexao.execute(
            "SELECT id FROM itens_de_titulo WHERE execucao_id = ? AND duplicidade_id = ?",
            (execucao, _duplicidade_do_item(item)),
        ).fetchone()
        decisao = self._conexao.execute(
            "INSERT INTO decisoes_de_duplicidade (item_de_titulo_id, tipo, titulo_oficial_id, autor, momento, origem)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                item_id,
                tipo.value,
                self._id_do_titulo(execucao, *oficial) if oficial else None,
                autor,
                momento.isoformat(),
                origem,
            ),
        ).lastrowid
        assert decisao is not None
        return decisao

    def _id_do_titulo(self, execucao: int, sistema: str, documento: str) -> int:
        (titulo_id,) = self._conexao.execute(
            "SELECT MIN(id) FROM titulos WHERE execucao_id = ? AND sistema_de_origem = ? AND documento = ?",
            (execucao, sistema, documento),
        ).fetchone()
        assert titulo_id is not None
        return int(titulo_id)

    def decisoes(self) -> tuple[DecisaoRegistrada, ...]:
        linhas = self._conexao.execute(
            "SELECT d.id, d.lancamento_id, d.execucao_do_item, d.tipo, d.motivo, d.autor, d.momento, d.origem,"
            " d.explicacao, d.regra, f.franqueado, f.referencia FROM decisoes d"
            " LEFT JOIN decisoes_conciliado_fora f ON f.decisao_id = d.id ORDER BY d.id"
        ).fetchall()
        dos_creditos = tuple(
            DecisaoRegistrada(
                item=_identificador_do_item(lancamento_id),
                tipo=TipoDeDecisao(tipo),
                motivo=motivo,
                autor=autor,
                momento=datetime.fromisoformat(momento),
                origem=origem,
                execucao=execucao,
                titulos=self._titulos_ligados("decisoes_titulos", decisao, coluna="decisao_id"),
                evidencia=self._evidencia_da_decisao(decisao),
                explicacao=explicacao,
                regra=RegraDaProposta(regra) if regra else None,
                pareceres=self._pareceres("decisoes_pareceres", "decisao_id", decisao),
                franqueado=franqueado,
                referencia=referencia,
            )
            for (
                decisao,
                lancamento_id,
                execucao,
                tipo,
                motivo,
                autor,
                momento,
                origem,
                explicacao,
                regra,
                franqueado,
                referencia,
            ) in linhas
        )
        return dos_creditos + tuple(self._decisoes_de_duplicidade())

    def _decisoes_de_duplicidade(self) -> Iterator[DecisaoRegistrada]:
        linhas = self._conexao.execute(
            "SELECT it.duplicidade_id, it.execucao_id, it.explicacao, dd.tipo, dd.titulo_oficial_id, dd.autor,"
            " dd.momento, dd.origem FROM decisoes_de_duplicidade dd JOIN itens_de_titulo it ON it.id = dd.item_de_titulo_id"
            " ORDER BY dd.id"
        ).fetchall()
        for duplicidade, execucao, explicacao, tipo, oficial, autor, momento, origem in linhas:
            yield DecisaoRegistrada(
                item=_identificador_da_duplicidade(duplicidade),
                tipo=TipoDeDecisao(tipo),
                motivo=None,
                autor=autor,
                momento=datetime.fromisoformat(momento),
                origem=origem,
                execucao=execucao,
                titulos=(self._titulo(oficial),) if oficial is not None else (),
                evidencia=(),
                explicacao=explicacao,
                regra=None,
            )

    def ultimas_datas(self) -> dict[tuple[str, str], date]:
        linhas = self._conexao.execute("SELECT banco, conta, MAX(data) FROM lancamentos GROUP BY banco, conta")
        return {(banco, conta): date.fromisoformat(data) for banco, conta, data in linhas}

    def franqueados(self) -> dict[str, Franqueado]:
        nomes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        linhas = self._conexao.execute("SELECT DISTINCT cnpj, sistema_de_origem, nome_do_franqueado FROM titulos")
        for cnpj, sistema, nome_do_franqueado in linhas:
            nomes[raiz_do_cnpj(cnpj)][sistema].add(nome_do_franqueado)
        return {
            raiz: Franqueado(raiz=raiz, nomes={sistema: frozenset(n) for sistema, n in por_sistema.items()})
            for raiz, por_sistema in nomes.items()
        }

    def registrar_execucao(
        self,
        lancamentos_novos: int,
        arquivos_lidos: Iterable[str],
        arquivos_recusados: Iterable[ArquivoRecusado],
        titulos: Iterable[Titulo],
        classificacoes: Iterable[tuple[int, Classificacao]],
        duplicidades: Iterable[PossivelDuplicidade],
        data_de_referencia: DataDeReferencia,
        cobranca: Iterable[tuple[TituloNaCobranca, tuple[int, ...]]],
        decisoes_aplicadas: Iterable[int],
        avisos_das_decisoes: Iterable[str],
        limite_de_queda: Decimal,
        decisoes_de_duplicidade_aplicadas: Iterable[int] = (),
        sistemas_exportados: Iterable[str] = (),
        acompanhamento_do_erp: Iterable[TituloNoAcompanhamento] = (),
        decisoes_da_tela_lidas: Iterable[int] = (),
        conflitos_das_decisoes: Iterable[str] = (),
    ) -> int:
        cursor = self._conexao.execute(
            "INSERT INTO execucoes (momento, lancamentos_novos) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), lancamentos_novos),
        )
        execucao = cursor.lastrowid
        assert execucao is not None
        self._conexao.execute(
            "INSERT INTO limites_de_queda (execucao_id, pontos_percentuais) VALUES (?, ?)",
            (execucao, str(limite_de_queda)),
        )
        self._conexao.executemany(
            "INSERT INTO arquivos (execucao_id, nome, motivo_da_recusa) VALUES (?, ?, ?)",
            [(execucao, nome, None) for nome in arquivos_lidos]
            + [(execucao, recusado.nome, recusado.motivo) for recusado in arquivos_recusados],
        )
        self._conexao.executemany(
            "UPDATE decisoes SET execucao_que_aplicou = ? WHERE id = ?",
            [(execucao, decisao) for decisao in decisoes_aplicadas],
        )
        self._conexao.executemany(
            "UPDATE decisoes_de_duplicidade SET execucao_que_aplicou = ? WHERE id = ?",
            [(execucao, decisao) for decisao in decisoes_de_duplicidade_aplicadas],
        )
        self._conexao.executemany(
            "INSERT INTO avisos_das_decisoes (execucao_id, texto) VALUES (?, ?)",
            [(execucao, aviso) for aviso in avisos_das_decisoes],
        )
        self._conexao.executemany(
            "UPDATE decisoes_da_tela SET execucao_que_leu = ? WHERE id = ?",
            [(execucao, decisao) for decisao in decisoes_da_tela_lidas],
        )
        self._conexao.executemany(
            "INSERT INTO conflitos_das_decisoes (execucao_id, texto) VALUES (?, ?)",
            [(execucao, conflito) for conflito in conflitos_das_decisoes],
        )
        id_do_titulo = {titulo: self._guardar_titulo(execucao, titulo) for titulo in titulos}
        self._conexao.executemany(
            "INSERT INTO exportacoes (execucao_id, sistema_de_origem) VALUES (?, ?)",
            [(execucao, sistema) for sistema in sorted(set(sistemas_exportados))],
        )
        self._conexao.execute("UPDATE divergencias_de_baixa SET execucao_id = ? WHERE execucao_id IS NULL", (execucao,))
        self._conexao.executemany(
            "INSERT INTO acompanhamento_do_erp (execucao_id, situacao, titulo_id, item, explicacao, saldo_centavos)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    execucao,
                    situacao.situacao.value,
                    self._ultimo_id_do_titulo(situacao.titulo),
                    situacao.item,
                    situacao.explicacao,
                    situacao.saldo_centavos,
                )
                for situacao in acompanhamento_do_erp
            ],
        )
        for lancamento_id, classificacao in classificacoes:
            item = self._conexao.execute(
                "INSERT INTO itens (execucao_id, lancamento_id, destino, explicacao, motivo) VALUES (?, ?, ?, ?, ?)",
                (
                    execucao,
                    lancamento_id,
                    classificacao.destino.value,
                    classificacao.explicacao,
                    classificacao.motivo.value if classificacao.motivo else None,
                ),
            ).lastrowid
            if classificacao.regra is not None:
                self._conexao.execute(
                    "INSERT INTO itens_regras (item_id, regra) VALUES (?, ?)", (item, classificacao.regra.value)
                )
            self._conexao.executemany(
                "INSERT INTO itens_evidencias (item_id, tipo) VALUES (?, ?)",
                [(item, tipo.value) for tipo in classificacao.evidencia],
            )
            self._conexao.executemany(
                "INSERT INTO itens_pareceres (item_id, franqueado, resposta, explicacao, modelo, versao_do_prompt)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        item,
                        p.franqueado,
                        p.parecer.resposta.value,
                        p.parecer.explicacao,
                        p.parecer.modelo,
                        p.parecer.versao_do_prompt,
                    )
                    for p in classificacao.pareceres
                ],
            )
            if classificacao.canal is not None:
                self._conexao.execute(
                    "INSERT INTO itens_atribuicoes (item_id, franqueado, canal) VALUES (?, ?, ?)",
                    (item, classificacao.franqueado, classificacao.canal.value),
                )
            self._conexao.executemany(
                "INSERT INTO itens_titulos (item_id, titulo_id) VALUES (?, ?)",
                [(item, id_do_titulo[titulo]) for titulo in classificacao.titulos],
            )
        for duplicidade in duplicidades:
            self._registrar_duplicidade(execucao, duplicidade, id_do_titulo)
        self._conexao.executemany(
            "INSERT INTO ultimas_datas_das_contas (execucao_id, banco, conta, ultima_data) VALUES (?, ?, ?, ?)",
            [
                (execucao, c.banco, c.conta, c.ultima_data.isoformat() if c.ultima_data else None)
                for c in data_de_referencia.contas
            ],
        )
        for na_cobranca, creditos in cobranca:
            cobranca_id = self._conexao.execute(
                "INSERT INTO cobranca (execucao_id, titulo_id, saldo_centavos) VALUES (?, ?, ?)",
                (execucao, id_do_titulo[na_cobranca.titulo], na_cobranca.saldo_centavos),
            ).lastrowid
            self._conexao.executemany(
                "INSERT INTO cobranca_creditos_candidatos (cobranca_id, lancamento_id) VALUES (?, ?)",
                [(cobranca_id, lancamento_id) for lancamento_id in creditos],
            )
        return execucao

    def _registrar_duplicidade(
        self, execucao: int, duplicidade: PossivelDuplicidade, id_do_titulo: dict[Titulo, int]
    ) -> None:
        chave = "|".join(sorted(f"{t.sistema_de_origem}:{t.documento}" for t in duplicidade.titulos))
        self._conexao.execute("INSERT OR IGNORE INTO duplicidades (chave) VALUES (?)", (chave,))
        (duplicidade_id,) = self._conexao.execute("SELECT id FROM duplicidades WHERE chave = ?", (chave,)).fetchone()
        item = self._conexao.execute(
            "INSERT INTO itens_de_titulo (execucao_id, duplicidade_id, explicacao, motivo) VALUES (?, ?, ?, ?)",
            (execucao, duplicidade_id, duplicidade.explicacao, MotivoDeNaoIdentificacao.POSSIVEL_DUPLICIDADE.value),
        ).lastrowid
        self._conexao.executemany(
            "INSERT INTO itens_de_titulo_titulos (item_id, titulo_id) VALUES (?, ?)",
            [(item, id_do_titulo[titulo]) for titulo in duplicidade.titulos],
        )

    def _guardar_titulo(self, execucao: int, titulo: Titulo) -> int:
        cursor = self._conexao.execute(
            "INSERT INTO titulos (execucao_id, sistema_de_origem, documento, nome_do_franqueado, cnpj, nosso_numero, vencimento,"
            " valor_centavos) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execucao,
                titulo.sistema_de_origem,
                titulo.documento,
                titulo.nome_do_franqueado,
                titulo.cnpj,
                titulo.nosso_numero,
                titulo.vencimento.isoformat(),
                titulo.valor_centavos,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def carregar_resultado(self, execucao: int) -> Resultado:
        lancamentos_novos, pontos_percentuais = self._conexao.execute(
            "SELECT e.lancamentos_novos, q.pontos_percentuais FROM execucoes e"
            " LEFT JOIN limites_de_queda q ON q.execucao_id = e.id WHERE e.id = ?",
            (execucao,),
        ).fetchone()
        arquivos = self._conexao.execute(
            "SELECT nome, motivo_da_recusa FROM arquivos WHERE execucao_id = ? ORDER BY nome", (execucao,)
        ).fetchall()
        itens = tuple(self._itens("i.execucao_id = ?", (execucao,)))
        conciliados_fora = tuple(self._conciliados_fora(execucao))
        anterior = self._execucao_anterior(execucao)
        resumo = Resumo(
            execucao=execucao,
            arquivos_lidos=tuple(nome for nome, motivo in arquivos if motivo is None),
            arquivos_recusados=tuple(ArquivoRecusado(nome, motivo) for nome, motivo in arquivos if motivo is not None),
            lancamentos_novos=lancamentos_novos,
            totais=_totais(itens),
            itens_com_parecer=sum(1 for item in itens if item.pareceres and not item.ia_indisponivel),
            itens_ia_indisponivel=sum(1 for item in itens if item.ia_indisponivel),
            data_de_referencia=self._data_de_referencia(execucao),
            decisoes=self._decisoes_lidas(execucao),
            limite_de_queda=Decimal(pontos_percentuais) if pontos_percentuais is not None else None,
            execucao_anterior=anterior,
            parte_automatica_anterior=(
                ParteAutomatica.dos_totais(_totais(self._itens("i.execucao_id = ?", (anterior,))))
                if anterior is not None
                else None
            ),
        )
        return Resultado(
            resumo=resumo,
            itens=itens,
            itens_de_titulo=tuple(self._itens_de_titulo(execucao)),
            cobranca=tuple(self._cobranca(execucao)),
            causa_raiz=CausaRaiz.da_fila(
                (*(item for item in itens if item.destino is Destino.FILA_DE_EXCECOES), *conciliados_fora),
                {raiz: franqueado.todos_os_nomes for raiz, franqueado in self.franqueados().items()},
            ),
            baixa_manual=tuple(self._baixa_manual(execucao)),
            cancelar_na_origem=tuple(self._cancelar_na_origem(execucao)),
            conciliados_fora=conciliados_fora,
            acompanhamento_do_erp=tuple(self._acompanhamento_do_erp(execucao)),
            metricas=Metricas.calcular(self._propostas_decididas(execucao), self._primeiros_pareceres_da_ia(execucao)),
        )

    def _execucao_anterior(self, execucao: int) -> int | None:
        (anterior,) = self._conexao.execute("SELECT MAX(id) FROM execucoes WHERE id < ?", (execucao,)).fetchone()
        return int(anterior) if anterior is not None else None

    def _propostas_decididas(self, execucao: int) -> Iterator[DecisaoSobreProposta]:
        linhas = self._conexao.execute(
            "SELECT d.id, d.tipo, d.regra, EXISTS (SELECT 1 FROM reversoes r JOIN decisoes v ON v.id = r.reversao_id"
            " WHERE r.confirmacao_id = d.id AND v.execucao_que_aplicou <= ?) FROM decisoes d"
            " WHERE d.regra IS NOT NULL AND d.tipo IN (?, ?) AND d.execucao_que_aplicou <= ? ORDER BY d.id",
            (execucao, TipoDeDecisao.CONFIRMAR.value, TipoDeDecisao.REJEITAR.value, execucao),
        ).fetchall()
        for decisao, tipo, regra, revertida in linhas:
            yield DecisaoSobreProposta(
                tipo=TipoDeDecisao(tipo),
                regra=RegraDaProposta(regra),
                evidencia=self._evidencia_da_decisao(decisao),
                revertida=bool(revertida),
            )

    def _primeiros_pareceres_da_ia(self, execucao: int) -> Iterator[PrimeiroParecerDaIa]:
        primeiros: dict[int, int] = {}
        for lancamento_id, item_id in self._conexao.execute(
            "SELECT i.lancamento_id, i.id FROM itens i WHERE i.execucao_id <= ?"
            " AND EXISTS (SELECT 1 FROM itens_pareceres p WHERE p.item_id = i.id)"
            " AND NOT EXISTS (SELECT 1 FROM itens_pareceres p WHERE p.item_id = i.id AND p.resposta = ?)"
            " ORDER BY i.execucao_id, i.id",
            (execucao, Resposta.INDISPONIVEL.value),
        ):
            primeiros.setdefault(lancamento_id, item_id)
        for lancamento_id, item_id in primeiros.items():
            yield PrimeiroParecerDaIa(
                pareceres=self._pareceres("itens_pareceres", "item_id", item_id),
                franqueados_decididos=self._franqueados_decididos(lancamento_id, execucao),
            )

    def _franqueados_decididos(self, lancamento_id: int, execucao: int) -> frozenset[str] | None:
        linha = self._conexao.execute(
            "SELECT d.id, f.franqueado FROM decisoes d LEFT JOIN decisoes_conciliado_fora f ON f.decisao_id = d.id"
            " WHERE d.lancamento_id = ? AND d.tipo IN (?, ?) AND d.execucao_que_aplicou <= ?"
            " AND NOT EXISTS (SELECT 1 FROM reversoes r JOIN decisoes v ON v.id = r.reversao_id"
            " WHERE r.confirmacao_id = d.id AND v.execucao_que_aplicou <= ?) ORDER BY d.id DESC LIMIT 1",
            (lancamento_id, TipoDeDecisao.CONFIRMAR.value, TipoDeDecisao.CONCILIADO_FORA.value, execucao, execucao),
        ).fetchone()
        if linha is None:
            return None
        decisao, franqueado = linha
        if franqueado is not None:
            return frozenset({franqueado})
        return frozenset(t.franqueado for t in self._titulos_ligados("decisoes_titulos", decisao, coluna="decisao_id"))

    def _evidencia_da_decisao(self, decisao: int) -> tuple[TipoDeEvidencia, ...]:
        return tuple(
            TipoDeEvidencia(t)
            for (t,) in self._conexao.execute(
                "SELECT tipo FROM decisoes_evidencias WHERE decisao_id = ? ORDER BY rowid", (decisao,)
            )
        )

    def _acompanhamento_do_erp(self, execucao: int) -> Iterator[TituloNoAcompanhamento]:
        linhas = self._conexao.execute(
            "SELECT situacao, titulo_id, item, explicacao, saldo_centavos FROM acompanhamento_do_erp"
            " WHERE execucao_id = ? ORDER BY rowid",
            (execucao,),
        ).fetchall()
        for situacao, titulo_id, item, explicacao, saldo in linhas:
            yield TituloNoAcompanhamento(SituacaoNoErp(situacao), self._titulo(titulo_id), item, explicacao, saldo)

    def _conciliados_fora(self, execucao: int) -> Iterator[Item]:
        linhas = self._conexao.execute(
            "SELECT d.execucao_do_item, d.lancamento_id, f.franqueado FROM decisoes d"
            " JOIN decisoes_conciliado_fora f ON f.decisao_id = d.id"
            " WHERE d.tipo = ? AND d.execucao_que_aplicou <= ? ORDER BY d.id",
            (TipoDeDecisao.CONCILIADO_FORA.value, execucao),
        ).fetchall()
        for execucao_do_item, lancamento_id, franqueado in linhas:
            [item] = self._itens("i.execucao_id = ? AND i.lancamento_id = ?", (execucao_do_item, lancamento_id))
            yield replace(item, franqueado=franqueado)

    def _cancelar_na_origem(self, execucao: int) -> Iterator[TituloACancelar]:
        na_exportacao = {(t.sistema_de_origem, t.documento): t for t in self.titulos_da_execucao(execucao)}
        for duplicidade, titulos, oficial in self._mesmas_dividas(ate_a_execucao=execucao):
            for titulo in titulos:
                atual = na_exportacao.get((titulo.sistema_de_origem, titulo.documento))
                if titulo != oficial and atual is not None:
                    yield TituloACancelar(_identificador_da_duplicidade(duplicidade), atual, oficial)

    def _decisoes_lidas(self, execucao: int) -> DecisoesLidas:
        tipos = Counter(
            TipoDeDecisao(tipo)
            for (tipo,) in self._conexao.execute(
                "SELECT tipo FROM decisoes WHERE execucao_que_aplicou = ?", (execucao,)
            )
        )
        avisos = self._conexao.execute(
            "SELECT texto FROM avisos_das_decisoes WHERE execucao_id = ? ORDER BY rowid", (execucao,)
        )
        (duplicidades,) = self._conexao.execute(
            "SELECT COUNT(*) FROM decisoes_de_duplicidade WHERE execucao_que_aplicou = ?", (execucao,)
        ).fetchone()
        conflitos = self._conexao.execute(
            "SELECT texto FROM conflitos_das_decisoes WHERE execucao_id = ? ORDER BY rowid", (execucao,)
        )
        return DecisoesLidas(
            confirmadas=tipos[TipoDeDecisao.CONFIRMAR],
            rejeitadas=tipos[TipoDeDecisao.REJEITAR],
            nao_aplicadas=tuple(texto for (texto,) in avisos),
            classificadas=sum(n for tipo, n in tipos.items() if tipo.classifica_credito_sem_titulo),
            conciliados_fora=tipos[TipoDeDecisao.CONCILIADO_FORA],
            fontes_nao_integradas=tipos[TipoDeDecisao.POSSIVEL_FONTE_NAO_INTEGRADA],
            duplicidades=duplicidades,
            revertidas=tipos[TipoDeDecisao.REVERTER],
            conflitos=tuple(texto for (texto,) in conflitos),
        )

    def _baixa_manual(self, execucao: int) -> Iterator[BaixaManual]:
        linhas = self._conexao.execute(
            "SELECT d.lancamento_id, dt.titulo_id, dt.encargo_centavos, p.principal_centavos,"
            f" {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d"
            " JOIN decisoes_titulos dt ON dt.decisao_id = d.id JOIN lancamentos l ON l.id = d.lancamento_id"
            " LEFT JOIN decisoes_principais p ON p.decisao_id = dt.decisao_id AND p.titulo_id = dt.titulo_id"
            " WHERE d.execucao_que_aplicou = ? AND d.tipo = ? ORDER BY l.data, l.id, dt.titulo_id",
            (execucao, TipoDeDecisao.CONFIRMAR.value),
        ).fetchall()
        exportados = {
            sistema
            for (sistema,) in self._conexao.execute(
                "SELECT sistema_de_origem FROM exportacoes WHERE execucao_id = ?", (execucao,)
            )
        }
        na_exportacao = {(t.sistema_de_origem, t.documento) for t in self.titulos_da_execucao(execucao)}
        for lancamento_id, titulo_id, encargo, principal, *lancamento in linhas:
            titulo = self._titulo(titulo_id)
            if titulo.sistema_de_origem in exportados and (titulo.sistema_de_origem, titulo.documento) not in na_exportacao:
                continue
            yield BaixaManual(
                item=_identificador_do_item(lancamento_id),
                titulo=titulo,
                principal_centavos=titulo.valor_centavos if principal is None else principal,
                encargo_centavos=encargo,
                credito=_lancamento(lancamento),
            )

    def _data_de_referencia(self, execucao: int) -> DataDeReferencia:
        linhas = self._conexao.execute(
            "SELECT banco, conta, ultima_data FROM ultimas_datas_das_contas WHERE execucao_id = ? ORDER BY rowid",
            (execucao,),
        )
        return DataDeReferencia(
            tuple(
                UltimaDataDaConta(banco, conta, date.fromisoformat(data) if data else None)
                for banco, conta, data in linhas
            )
        )

    def _cobranca(self, execucao: int) -> Iterator[TituloNaCobranca]:
        linhas = self._conexao.execute(
            "SELECT id, titulo_id, saldo_centavos FROM cobranca WHERE execucao_id = ? ORDER BY id", (execucao,)
        ).fetchall()
        for cobranca_id, titulo_id, saldo in linhas:
            creditos = self._conexao.execute(
                f"SELECT {_COLUNAS_LANCAMENTO} FROM cobranca_creditos_candidatos c"
                " JOIN lancamentos l ON l.id = c.lancamento_id WHERE c.cobranca_id = ? ORDER BY l.data, l.id",
                (cobranca_id,),
            )
            yield TituloNaCobranca(
                titulo=self._titulo(titulo_id),
                saldo_centavos=saldo,
                creditos_candidatos=tuple(_lancamento(linha) for linha in creditos),
            )

    def _itens_de_titulo(self, execucao: int) -> Iterator[ItemDeTitulo]:
        linhas = self._conexao.execute(
            "SELECT id, duplicidade_id, explicacao, motivo FROM itens_de_titulo WHERE execucao_id = ? ORDER BY id",
            (execucao,),
        ).fetchall()
        for item_id, duplicidade_id, explicacao, motivo in linhas:
            yield ItemDeTitulo(
                identificador=_identificador_da_duplicidade(duplicidade_id),
                titulos=self._titulos_ligados("itens_de_titulo_titulos", item_id),
                explicacao=explicacao,
                motivo=MotivoDeNaoIdentificacao(motivo),
            )

    def _itens(self, filtro: str, parametros: tuple[object, ...]) -> list[Item]:
        linhas = self._conexao.execute(
            "SELECT i.id, i.lancamento_id, i.destino, i.explicacao, i.motivo, r.regra, a.franqueado, a.canal,"
            f" {_COLUNAS_LANCAMENTO} FROM itens i JOIN lancamentos l ON l.id = i.lancamento_id"
            " LEFT JOIN itens_atribuicoes a ON a.item_id = i.id LEFT JOIN itens_regras r ON r.item_id = i.id"
            f" WHERE {filtro}"
            " ORDER BY l.data, l.id",
            parametros,
        ).fetchall()
        return [
            Item(
                identificador=_identificador_do_item(lancamento_id),
                destino=Destino(destino),
                lancamento=_lancamento(lancamento),
                titulos=self._titulos_ligados("itens_titulos", item_id),
                explicacao=explicacao,
                motivo=MotivoDeNaoIdentificacao(motivo) if motivo else None,
                evidencia=self._evidencia(item_id),
                pareceres=self._pareceres("itens_pareceres", "item_id", item_id),
                franqueado=franqueado,
                canal=Canal(canal) if canal else None,
                regra=RegraDaProposta(regra) if regra else None,
            )
            for item_id, lancamento_id, destino, explicacao, motivo, regra, franqueado, canal, *lancamento in linhas
        ]

    def _pareceres(self, tabela: str, coluna: str, chave: int) -> tuple[ParecerSobreFranqueado, ...]:
        linhas = self._conexao.execute(
            f"SELECT franqueado, resposta, explicacao, modelo, versao_do_prompt FROM {tabela}"
            f" WHERE {coluna} = ? ORDER BY rowid",
            (chave,),
        )
        return tuple(
            ParecerSobreFranqueado(franqueado, Parecer(Resposta(resposta), explicacao, modelo, versao))
            for franqueado, resposta, explicacao, modelo, versao in linhas
        )

    def _evidencia(self, item_id: int) -> tuple[TipoDeEvidencia, ...]:
        linhas = self._conexao.execute("SELECT tipo FROM itens_evidencias WHERE item_id = ? ORDER BY rowid", (item_id,))
        return tuple(TipoDeEvidencia(tipo) for (tipo,) in linhas)

    def _titulos_ligados(self, ligacao: str, item_id: int, coluna: str = "item_id") -> tuple[Titulo, ...]:
        linhas = self._conexao.execute(
            f"SELECT {_COLUNAS_TITULO} FROM {ligacao} it JOIN titulos t ON t.id = it.titulo_id"
            f" WHERE it.{coluna} = ? ORDER BY t.id",
            (item_id,),
        )
        return tuple(_titulo(linha) for linha in linhas)

    def _titulo(self, titulo_id: int) -> Titulo:
        return _titulo(
            self._conexao.execute(f"SELECT {_COLUNAS_TITULO} FROM titulos t WHERE t.id = ?", (titulo_id,)).fetchone()
        )


def _titulo(linha: tuple[str, str, str, str, str | None, str, int]) -> Titulo:
    sistema, documento, nome_do_franqueado, cnpj, nosso_numero, vencimento, valor = linha
    return Titulo(
        sistema_de_origem=sistema,
        documento=documento,
        nome_do_franqueado=nome_do_franqueado,
        cnpj=cnpj,
        nosso_numero=nosso_numero,
        vencimento=date.fromisoformat(vencimento),
        valor_centavos=valor,
    )


def _vinculo(linha: Iterable[object]) -> VinculoDeCobranca:
    tipo, identificador, origem, sistema, documento, cnpj, valor, vencimento = (str(campo) for campo in linha)
    return VinculoDeCobranca(
        tipo=TipoDeIdentificador(tipo),
        identificador=identificador,
        origem=OrigemDoIdentificador(origem),
        sistema_de_origem=sistema,
        documento=documento,
        cnpj=cnpj,
        valor_centavos=int(valor),
        vencimento=date.fromisoformat(vencimento),
    )


def _retorno(linha: Iterable[object]) -> RetornoDeCobranca:
    tipo, chave_natural, identificador, banco, conta, data, valor, principal, multa, juros = linha
    return RetornoDeCobranca(
        tipo=TipoDeIdentificador(str(tipo)),
        chave_natural=str(chave_natural),
        identificador=str(identificador),
        banco=str(banco),
        conta=str(conta),
        data=date.fromisoformat(str(data)),
        valor_centavos=int(str(valor)),
        componentes=None if principal is None else ComponentesDoValor(int(str(principal)), int(str(multa)), int(str(juros))),
    )


_PREFIXO_DO_ITEM = "L"


def _totais(itens: Iterable[Item]) -> dict[Destino, TotalDoDestino]:
    por_destino = list(itens)
    return {
        destino: TotalDoDestino(
            quantidade=sum(1 for item in por_destino if item.destino is destino),
            valor_centavos=sum(item.lancamento.valor_centavos for item in por_destino if item.destino is destino),
        )
        for destino in Destino
    }


def _identificador_do_item(lancamento_id: int) -> str:
    return f"{_PREFIXO_DO_ITEM}{lancamento_id}"


def _lancamento_do_item(identificador: str) -> int:
    assert identificador.startswith(_PREFIXO_DO_ITEM)
    return int(identificador.removeprefix(_PREFIXO_DO_ITEM))


_PREFIXO_DA_DUPLICIDADE = "D"


def _identificador_da_duplicidade(duplicidade_id: int) -> str:
    return f"{_PREFIXO_DA_DUPLICIDADE}{duplicidade_id}"


def _duplicidade_do_item(identificador: str) -> int:
    assert identificador.startswith(_PREFIXO_DA_DUPLICIDADE)
    return int(identificador.removeprefix(_PREFIXO_DA_DUPLICIDADE))


def _marcadores(valores: list[str]) -> str:
    return ", ".join("?" for _ in valores)


def _parametros_da_chave(chave: ChaveNatural) -> tuple[object, ...]:
    banco, conta, data, natureza, valor, historico, documento, ordinal = chave
    return (banco, conta, data.isoformat(), natureza.value, valor, historico, documento, ordinal)


def _lancamento(linha: Iterable[object]) -> Lancamento:
    banco, conta, data, natureza, valor, historico, documento, ordinal = linha
    assert isinstance(data, str) and isinstance(natureza, str)
    return Lancamento(
        banco=str(banco),
        conta=str(conta),
        data=date.fromisoformat(data),
        historico=str(historico),
        documento=str(documento),
        valor_centavos=int(str(valor)),
        natureza=Natureza(natureza),
        ordinal=int(str(ordinal)),
    )
