import argparse
import sys
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from conciliacao.armazenamento import Armazenamento
from conciliacao.dominio import Resultado
from conciliacao.pagina import renderizar

ENDERECO_LOCAL = "127.0.0.1"
PORTA_PADRAO = 8765


@dataclass(frozen=True)
class Resposta:
    status: HTTPStatus
    corpo: str
    tipo: str = "text/html; charset=utf-8"


Rota = Callable[[Path], Resposta]


def ultimo_resultado(estado: Path) -> Resultado | None:
    if not estado.exists():
        return None
    armazenamento = Armazenamento(estado)
    try:
        execucao = armazenamento.ultima_execucao()
        return armazenamento.carregar_resultado(execucao) if execucao is not None else None
    finally:
        armazenamento.fechar()


def _pagina_inicial(estado: Path) -> Resposta:
    return Resposta(HTTPStatus.OK, renderizar(ultimo_resultado(estado)))


_ROTAS_GET: Mapping[str, Rota] = {"/": _pagina_inicial}
_NAO_ENCONTRADA = Resposta(HTTPStatus.NOT_FOUND, "Página não encontrada.", "text/plain; charset=utf-8")


def criar_servidor(estado: Path, porta: int = PORTA_PADRAO) -> HTTPServer:
    class Requisicao(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._responder(_ROTAS_GET)

        def _responder(self, rotas: Mapping[str, Rota]) -> None:
            rota = rotas.get(urlsplit(self.path).path)
            resposta = rota(estado) if rota is not None else _NAO_ENCONTRADA
            corpo = resposta.corpo.encode("utf-8")
            self.send_response(resposta.status)
            self.send_header("Content-Type", resposta.tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return HTTPServer((ENDERECO_LOCAL, porta), Requisicao)


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conciliar-tela", description="Abre a tela local com o resultado da última execução."
    )
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador, só sobe a tela")
    opcoes = parser.parse_args(argumentos)

    try:
        servidor = criar_servidor(opcoes.estado, opcoes.porta)
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
