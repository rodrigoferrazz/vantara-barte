import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from conciliacao.dominio import (
    ArquivoRecusado,
    ChaveNatural,
    Classificacao,
    Destino,
    Item,
    Lancamento,
    MotivoDeNaoIdentificacao,
    Natureza,
    Resultado,
    Resumo,
    Titulo,
    TotalDoDestino,
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
CREATE TABLE IF NOT EXISTS itens_titulos (
    item_id INTEGER NOT NULL REFERENCES itens(id),
    titulo_id INTEGER NOT NULL REFERENCES titulos(id)
);
"""

_COLUNAS_LANCAMENTO = "banco, conta, data, natureza, valor_centavos, historico, documento, ordinal"


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

    def creditos_guardados(self) -> dict[int, Lancamento]:
        linhas = self._conexao.execute(
            f"SELECT id, {_COLUNAS_LANCAMENTO} FROM lancamentos WHERE natureza = ? ORDER BY data, id",
            (Natureza.CREDITO.value,),
        )
        return {linha[0]: _lancamento(linha[1:]) for linha in linhas}

    def franqueados_conhecidos(self) -> frozenset[str]:
        linhas = self._conexao.execute("SELECT DISTINCT cnpj FROM titulos")
        return frozenset(raiz_do_cnpj(cnpj) for (cnpj,) in linhas)

    def registrar_execucao(
        self,
        lancamentos_novos: int,
        arquivos_lidos: Iterable[str],
        arquivos_recusados: Iterable[ArquivoRecusado],
        titulos: Iterable[Titulo],
        classificacoes: Iterable[tuple[int, Classificacao]],
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
            self._conexao.executemany(
                "INSERT INTO itens_titulos (item_id, titulo_id) VALUES (?, ?)",
                [(item, id_do_titulo[titulo]) for titulo in classificacao.titulos],
            )
        return execucao

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
        )
        return Resultado(resumo=resumo, itens=itens)

    def _itens(self, execucao: int) -> Iterator[Item]:
        linhas = self._conexao.execute(
            f"SELECT i.id, i.lancamento_id, i.destino, i.explicacao, i.motivo, {_COLUNAS_LANCAMENTO}"
            " FROM itens i JOIN lancamentos l ON l.id = i.lancamento_id WHERE i.execucao_id = ?"
            " ORDER BY l.data, l.id",
            (execucao,),
        ).fetchall()
        for item_id, lancamento_id, destino, explicacao, motivo, *lancamento in linhas:
            yield Item(
                identificador=f"L{lancamento_id}",
                destino=Destino(destino),
                lancamento=_lancamento(lancamento),
                titulos=self._titulos_do_item(item_id),
                explicacao=explicacao,
                motivo=MotivoDeNaoIdentificacao(motivo) if motivo else None,
            )

    def _titulos_do_item(self, item_id: int) -> tuple[Titulo, ...]:
        linhas = self._conexao.execute(
            "SELECT t.sistema_de_origem, t.documento, t.cliente, t.cnpj, t.nosso_numero, t.vencimento,"
            " t.valor_centavos FROM itens_titulos it JOIN titulos t ON t.id = it.titulo_id"
            " WHERE it.item_id = ? ORDER BY t.id",
            (item_id,),
        )
        return tuple(
            Titulo(
                sistema_de_origem=sistema,
                documento=documento,
                cliente=cliente,
                cnpj=cnpj,
                nosso_numero=nosso_numero,
                vencimento=date.fromisoformat(vencimento),
                valor_centavos=valor,
            )
            for sistema, documento, cliente, cnpj, nosso_numero, vencimento, valor in linhas
        )


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
