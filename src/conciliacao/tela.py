import argparse
import getpass
import sys
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from conciliacao.armazenamento import Armazenamento
from conciliacao.decisoes import (
    DecisaoDaTelaRecusada,
    SemExecucaoParaDecidir,
    confirmar_o_lote_pela_tela,
    registrar_decisao_da_tela,
)
from conciliacao.dominio import DecisaoDaTela, LinhaDeDecisao, Resultado
from conciliacao.pagina import renderizar, renderizar_impacto, renderizar_recusa

ENDERECO_LOCAL = "127.0.0.1"
PORTA_PADRAO = 8765


@dataclass(frozen=True)
class Resposta:
    status: HTTPStatus
    corpo: str
    tipo: str = "text/html; charset=utf-8"
    localizacao: str | None = None


@dataclass(frozen=True)
class Envio:
    campos: Mapping[str, str]
    analista: str


Rota = Callable[[Path], Resposta]
RotaDeEnvio = Callable[[Path, Envio], Resposta]


def ultimo_resultado(estado: Path) -> Resultado | None:
    return _ultimo_estado(estado)[0]


def _ultimo_estado(estado: Path) -> tuple[Resultado | None, Mapping[str, DecisaoDaTela]]:
    if not estado.exists():
        return None, {}
    armazenamento = Armazenamento(estado)
    try:
        execucao = armazenamento.ultima_execucao()
        if execucao is None:
            return None, {}
        pendentes = {p.linha.item: p for p in armazenamento.decisoes_da_tela_pendentes() if p.execucao == execucao}
        return armazenamento.carregar_resultado(execucao), pendentes
    finally:
        armazenamento.fechar()


def _pagina_inicial(estado: Path) -> Resposta:
    return Resposta(HTTPStatus.OK, renderizar(*_ultimo_estado(estado)))


def _pagina_de_impacto(estado: Path) -> Resposta:
    if not estado.exists():
        return Resposta(HTTPStatus.OK, renderizar_impacto(None))
    armazenamento = Armazenamento(estado)
    try:
        return Resposta(HTTPStatus.OK, renderizar_impacto(armazenamento.ultima_analise_de_impacto()))
    finally:
        armazenamento.fechar()


def _decidir(estado: Path, envio: Envio) -> Resposta:
    campos = envio.campos
    linha = LinhaDeDecisao(
        aba=campos.get("aba", ""),
        item=campos.get("item", ""),
        decisao=campos.get("decisao", "").strip(),
        motivo=campos.get("motivo", "").strip(),
        titulos=campos.get("titulos", "").strip(),
        franqueado=campos.get("franqueado", "").strip(),
        referencia=campos.get("referencia", "").strip(),
    )
    return _gravar(
        estado, lambda armazenamento: registrar_decisao_da_tela(armazenamento, linha, envio.analista, datetime.now())
    )


def _confirmar_o_lote(estado: Path, envio: Envio) -> Resposta:
    return _gravar(
        estado, lambda armazenamento: confirmar_o_lote_pela_tela(armazenamento, envio.analista, datetime.now())
    )


def _gravar(estado: Path, gravacao: Callable[[Armazenamento], object]) -> Resposta:
    if not estado.exists():
        return _recusa(SemExecucaoParaDecidir("Não há execução registrada; não há o que decidir."))
    armazenamento = Armazenamento(estado)
    try:
        gravacao(armazenamento)
    except DecisaoDaTelaRecusada as recusa:
        return _recusa(recusa)
    finally:
        armazenamento.fechar()
    return Resposta(HTTPStatus.SEE_OTHER, "", localizacao="/")


def _recusa(recusa: DecisaoDaTelaRecusada) -> Resposta:
    status = HTTPStatus.CONFLICT if isinstance(recusa, SemExecucaoParaDecidir) else HTTPStatus.BAD_REQUEST
    return Resposta(status, renderizar_recusa(str(recusa)))


_ROTAS_GET: Mapping[str, Rota] = {"/": _pagina_inicial, "/impacto": _pagina_de_impacto}
_ROTAS_POST: Mapping[str, RotaDeEnvio] = {"/decidir": _decidir, "/confirmar-lote": _confirmar_o_lote}
_NAO_ENCONTRADA = Resposta(HTTPStatus.NOT_FOUND, "Página não encontrada.", "text/plain; charset=utf-8")


def criar_servidor(estado: Path, porta: int = PORTA_PADRAO, analista: str | None = None) -> HTTPServer:
    quem_decide = analista or getpass.getuser()

    class Requisicao(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            rota = _ROTAS_GET.get(urlsplit(self.path).path)
            self._responder(rota(estado) if rota is not None else _NAO_ENCONTRADA)

        def do_POST(self) -> None:
            rota = _ROTAS_POST.get(urlsplit(self.path).path)
            tamanho = int(self.headers.get("Content-Length") or 0)
            corpo = self.rfile.read(tamanho).decode("utf-8")
            campos = dict(parse_qsl(corpo, keep_blank_values=True))
            self._responder(rota(estado, Envio(campos, quem_decide)) if rota is not None else _NAO_ENCONTRADA)

        def _responder(self, resposta: Resposta) -> None:
            corpo = resposta.corpo.encode("utf-8")
            self.send_response(resposta.status)
            self.send_header("Content-Type", resposta.tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            if resposta.localizacao is not None:
                self.send_header("Location", resposta.localizacao)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return HTTPServer((ENDERECO_LOCAL, porta), Requisicao)


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conciliar-tela",
        description="Abre a tela local com o resultado da última execução e a última análise de impacto.",
    )
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador, só sobe a tela")
    parser.add_argument(
        "--analista", help="quem decide pela tela (padrão: o usuário do sistema que abriu a tela)", default=None
    )
    opcoes = parser.parse_args(argumentos)

    try:
        servidor = criar_servidor(opcoes.estado, opcoes.porta, opcoes.analista)
    except OSError as erro:
        print(f"Não foi possível abrir a tela na porta {opcoes.porta}: {erro}", file=sys.stderr)
        return 2
    endereco = f"http://{ENDERECO_LOCAL}:{servidor.server_address[1]}/"
    print(f"Tela local em {endereco} (Ctrl+C para encerrar)", flush=True)
    if not opcoes.sem_navegador:
        webbrowser.open(endereco)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
