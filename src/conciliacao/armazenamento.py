import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from conciliacao.dominio import (
    ArquivoRecusado,
    BaixaManual,
    DecisaoRegistrada,
    DecisoesLidas,
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
    MotivoDeNaoIdentificacao,
    Natureza,
    Parecer,
    ParecerSobreFranqueado,
    PossivelDuplicidade,
    Resposta,
    Resultado,
    Resumo,
    TipoDeEvidencia,
    Titulo,
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
    cliente TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS cobranca_creditos_candidatos (
    cobranca_id INTEGER NOT NULL REFERENCES cobranca(id),
    lancamento_id INTEGER NOT NULL REFERENCES lancamentos(id)
);
"""

_COLUNAS_LANCAMENTO = "banco, conta, data, natureza, valor_centavos, historico, documento, ordinal"
_COLUNAS_DO_LANCAMENTO_L = ", ".join(f"l.{coluna}" for coluna in _COLUNAS_LANCAMENTO.split(", "))
_COLUNAS_TITULO = (
    "t.sistema_de_origem, t.documento, t.cliente, t.cnpj, t.nosso_numero, t.vencimento, t.valor_centavos"
)


class Armazenamento:
    def __init__(self, caminho: Path) -> None:
        self._conexao = sqlite3.connect(caminho, autocommit=False)
        self._conexao.execute("PRAGMA foreign_keys = ON")
        self._conexao.executescript(_ESQUEMA)
        self._conexao.commit()

    def fechar(self) -> None:
        self._conexao.close()

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
        linhas = self._conexao.execute(
            f"SELECT id, {_COLUNAS_LANCAMENTO} FROM lancamentos WHERE natureza = ?"
            " AND id NOT IN (SELECT lancamento_id FROM decisoes WHERE tipo = ?) ORDER BY data, id",
            (Natureza.CREDITO.value, TipoDeDecisao.CONFIRMAR.value),
        )
        return {linha[0]: _lancamento(linha[1:]) for linha in linhas}

    def ultima_execucao(self) -> int | None:
        (execucao,) = self._conexao.execute("SELECT MAX(id) FROM execucoes").fetchone()
        return int(execucao) if execucao is not None else None

    def titulos_com_baixa_confirmada(self) -> set[tuple[str, str]]:
        linhas = self._conexao.execute(
            "SELECT DISTINCT t.sistema_de_origem, t.documento FROM decisoes d"
            " JOIN decisoes_titulos dt ON dt.decisao_id = d.id JOIN titulos t ON t.id = dt.titulo_id WHERE d.tipo = ?",
            (TipoDeDecisao.CONFIRMAR.value,),
        )
        return {(sistema, documento) for sistema, documento in linhas}

    def pares_rejeitados(self) -> list[ParRejeitado]:
        linhas = self._conexao.execute(
            f"SELECT t.sistema_de_origem, t.documento, d.motivo, {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d"
            " JOIN decisoes_titulos dt ON dt.decisao_id = d.id JOIN titulos t ON t.id = dt.titulo_id"
            " JOIN lancamentos l ON l.id = d.lancamento_id WHERE d.tipo = ? ORDER BY d.id, t.id",
            (TipoDeDecisao.REJEITAR.value,),
        )
        return [
            ParRejeitado(_lancamento(lancamento).chave_natural, sistema, documento, motivo)
            for sistema, documento, motivo, *lancamento in linhas
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
        titulos = self._conexao.execute(
            "SELECT t.id, t.sistema_de_origem, t.documento FROM itens_titulos it JOIN titulos t ON t.id = it.titulo_id"
            " WHERE it.item_id = ? ORDER BY t.id",
            (item_id,),
        ).fetchall()
        self._conexao.executemany(
            "INSERT INTO decisoes_titulos (decisao_id, titulo_id, encargo_centavos) VALUES (?, ?, ?)",
            [(decisao, titulo_id, encargos[(sistema, documento)]) for titulo_id, sistema, documento in titulos],
        )
        return decisao

    def decisoes(self) -> tuple[DecisaoRegistrada, ...]:
        linhas = self._conexao.execute(
            "SELECT id, lancamento_id, execucao_do_item, tipo, motivo, autor, momento, origem, explicacao, regra"
            " FROM decisoes ORDER BY id"
        ).fetchall()
        return tuple(
            DecisaoRegistrada(
                item=_identificador_do_item(lancamento_id),
                tipo=TipoDeDecisao(tipo),
                motivo=motivo,
                autor=autor,
                momento=datetime.fromisoformat(momento),
                origem=origem,
                execucao=execucao,
                titulos=self._titulos_ligados("decisoes_titulos", decisao, coluna="decisao_id"),
                evidencia=tuple(
                    TipoDeEvidencia(t)
                    for (t,) in self._conexao.execute(
                        "SELECT tipo FROM decisoes_evidencias WHERE decisao_id = ? ORDER BY rowid", (decisao,)
                    )
                ),
                explicacao=explicacao,
                regra=RegraDaProposta(regra) if regra else None,
            )
            for decisao, lancamento_id, execucao, tipo, motivo, autor, momento, origem, explicacao, regra in linhas
        )

    def ultimas_datas(self) -> dict[tuple[str, str], date]:
        linhas = self._conexao.execute("SELECT banco, conta, MAX(data) FROM lancamentos GROUP BY banco, conta")
        return {(banco, conta): date.fromisoformat(data) for banco, conta, data in linhas}

    def franqueados(self) -> dict[str, Franqueado]:
        nomes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        linhas = self._conexao.execute("SELECT DISTINCT cnpj, sistema_de_origem, cliente FROM titulos")
        for cnpj, sistema, cliente in linhas:
            nomes[raiz_do_cnpj(cnpj)][sistema].add(cliente)
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
    ) -> int:
        cursor = self._conexao.execute(
            "INSERT INTO execucoes (momento, lancamentos_novos) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), lancamentos_novos),
        )
        execucao = cursor.lastrowid
        assert execucao is not None
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
            "INSERT INTO avisos_das_decisoes (execucao_id, texto) VALUES (?, ?)",
            [(execucao, aviso) for aviso in avisos_das_decisoes],
        )
        id_do_titulo = {titulo: self._guardar_titulo(execucao, titulo) for titulo in titulos}
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
            "INSERT INTO titulos (execucao_id, sistema_de_origem, documento, cliente, cnpj, nosso_numero, vencimento,"
            " valor_centavos) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execucao,
                titulo.sistema_de_origem,
                titulo.documento,
                titulo.cliente,
                titulo.cnpj,
                titulo.nosso_numero,
                titulo.vencimento.isoformat(),
                titulo.valor_centavos,
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def carregar_resultado(self, execucao: int) -> Resultado:
        (lancamentos_novos,) = self._conexao.execute(
            "SELECT lancamentos_novos FROM execucoes WHERE id = ?", (execucao,)
        ).fetchone()
        arquivos = self._conexao.execute(
            "SELECT nome, motivo_da_recusa FROM arquivos WHERE execucao_id = ? ORDER BY nome", (execucao,)
        ).fetchall()
        itens = tuple(self._itens(execucao))
        totais = {
            destino: TotalDoDestino(
                quantidade=sum(1 for item in itens if item.destino is destino),
                valor_centavos=sum(item.lancamento.valor_centavos for item in itens if item.destino is destino),
            )
            for destino in Destino
        }
        resumo = Resumo(
            execucao=execucao,
            arquivos_lidos=tuple(nome for nome, motivo in arquivos if motivo is None),
            arquivos_recusados=tuple(ArquivoRecusado(nome, motivo) for nome, motivo in arquivos if motivo is not None),
            lancamentos_novos=lancamentos_novos,
            totais=totais,
            itens_com_parecer=sum(1 for item in itens if item.pareceres and not item.ia_indisponivel),
            itens_ia_indisponivel=sum(1 for item in itens if item.ia_indisponivel),
            data_de_referencia=self._data_de_referencia(execucao),
            decisoes=self._decisoes_lidas(execucao),
        )
        return Resultado(
            resumo=resumo,
            itens=itens,
            itens_de_titulo=tuple(self._itens_de_titulo(execucao)),
            cobranca=tuple(self._cobranca(execucao)),
            causa_raiz=CausaRaiz.da_fila(
                (item for item in itens if item.destino is Destino.FILA_DE_EXCECOES),
                {raiz: franqueado.todos_os_nomes for raiz, franqueado in self.franqueados().items()},
            ),
            baixa_manual=tuple(self._baixa_manual(execucao)),
        )

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
        return DecisoesLidas(
            confirmadas=tipos[TipoDeDecisao.CONFIRMAR],
            rejeitadas=tipos[TipoDeDecisao.REJEITAR],
            nao_aplicadas=tuple(texto for (texto,) in avisos),
        )

    def _baixa_manual(self, execucao: int) -> Iterator[BaixaManual]:
        linhas = self._conexao.execute(
            f"SELECT d.lancamento_id, dt.titulo_id, dt.encargo_centavos, {_COLUNAS_DO_LANCAMENTO_L} FROM decisoes d"
            " JOIN decisoes_titulos dt ON dt.decisao_id = d.id JOIN lancamentos l ON l.id = d.lancamento_id"
            " WHERE d.execucao_que_aplicou = ? AND d.tipo = ? ORDER BY l.data, l.id, dt.titulo_id",
            (execucao, TipoDeDecisao.CONFIRMAR.value),
        ).fetchall()
        for lancamento_id, titulo_id, encargo, *lancamento in linhas:
            titulo = self._titulo(titulo_id)
            yield BaixaManual(
                item=_identificador_do_item(lancamento_id),
                titulo=titulo,
                principal_centavos=titulo.valor_centavos,
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
                identificador=f"D{duplicidade_id}",
                titulos=self._titulos_ligados("itens_de_titulo_titulos", item_id),
                explicacao=explicacao,
                motivo=MotivoDeNaoIdentificacao(motivo),
            )

    def _itens(self, execucao: int) -> Iterator[Item]:
        linhas = self._conexao.execute(
            "SELECT i.id, i.lancamento_id, i.destino, i.explicacao, i.motivo, r.regra, a.franqueado, a.canal,"
            f" {_COLUNAS_LANCAMENTO} FROM itens i JOIN lancamentos l ON l.id = i.lancamento_id"
            " LEFT JOIN itens_atribuicoes a ON a.item_id = i.id LEFT JOIN itens_regras r ON r.item_id = i.id"
            " WHERE i.execucao_id = ?"
            " ORDER BY l.data, l.id",
            (execucao,),
        ).fetchall()
        for item_id, lancamento_id, destino, explicacao, motivo, regra, franqueado, canal, *lancamento in linhas:
            yield Item(
                identificador=_identificador_do_item(lancamento_id),
                destino=Destino(destino),
                lancamento=_lancamento(lancamento),
                titulos=self._titulos_ligados("itens_titulos", item_id),
                explicacao=explicacao,
                motivo=MotivoDeNaoIdentificacao(motivo) if motivo else None,
                evidencia=self._evidencia(item_id),
                pareceres=self._pareceres(item_id),
                franqueado=franqueado,
                canal=Canal(canal) if canal else None,
                regra=RegraDaProposta(regra) if regra else None,
            )

    def _pareceres(self, item_id: int) -> tuple[ParecerSobreFranqueado, ...]:
        linhas = self._conexao.execute(
            "SELECT franqueado, resposta, explicacao, modelo, versao_do_prompt FROM itens_pareceres"
            " WHERE item_id = ? ORDER BY rowid",
            (item_id,),
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
    sistema, documento, cliente, cnpj, nosso_numero, vencimento, valor = linha
    return Titulo(
        sistema_de_origem=sistema,
        documento=documento,
        cliente=cliente,
        cnpj=cnpj,
        nosso_numero=nosso_numero,
        vencimento=date.fromisoformat(vencimento),
        valor_centavos=valor,
    )


_PREFIXO_DO_ITEM = "L"


def _identificador_do_item(lancamento_id: int) -> str:
    return f"{_PREFIXO_DO_ITEM}{lancamento_id}"


def _lancamento_do_item(identificador: str) -> int:
    assert identificador.startswith(_PREFIXO_DO_ITEM)
    return int(identificador.removeprefix(_PREFIXO_DO_ITEM))


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
