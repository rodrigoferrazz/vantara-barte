import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from conciliacao.configuracao import ConfiguracaoDaIa, ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import Resposta
from conciliacao.parecerista import VERSAO_DO_PROMPT, PareceristaOllama
from tests.parecerista import ollama_do_projeto

CONTAS = '[[contas]]\npadrao = "itau*.csv"\nbanco = "itau"\nconta = "1"\n'


class _OllamaFalso(BaseHTTPRequestHandler):
    conteudo = ""
    pedidos: list[dict[str, object]] = []

    def do_POST(self) -> None:
        tamanho = int(self.headers["Content-Length"])
        _OllamaFalso.pedidos.append({"caminho": self.path, **json.loads(self.rfile.read(tamanho))})
        corpo = json.dumps({"model": "qualquer", "message": {"role": "assistant", "content": self.conteudo}})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo.encode())

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def ollama_falso() -> Iterator[str]:
    _OllamaFalso.pedidos = []
    servidor = HTTPServer(("127.0.0.1", 0), _OllamaFalso)
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _parecerista(endereco: str, modelo: str = "modelo-x") -> PareceristaOllama:
    return PareceristaOllama(ConfiguracaoDaIa(endereco=endereco, modelo=modelo, tempo_limite_segundos=5))


def test_resposta_estruturada_vira_parecer_com_modelo_e_versao_do_prompt(ollama_falso: str) -> None:
    _OllamaFalso.conteudo = json.dumps({"pertence": True, "explicacao": "CONF abrevia Confeitaria"})

    parecer = _parecerista(ollama_falso).dar_parecer("CONF ALVORADA", ["Confeitaria Alvorada Ltda", "CONF ALVORADA NORTE"])

    assert parecer.resposta is Resposta.SIM
    assert parecer.explicacao == "CONF abrevia Confeitaria"
    assert parecer.modelo == "modelo-x"
    assert parecer.versao_do_prompt == VERSAO_DO_PROMPT
    [pedido] = _OllamaFalso.pedidos
    assert pedido["caminho"] == "/api/chat"
    assert pedido["model"] == "modelo-x"
    assert isinstance(pedido["format"], dict)
    perguntas = json.dumps(pedido["messages"], ensure_ascii=False)
    assert "CONF ALVORADA" in perguntas
    assert "Confeitaria Alvorada Ltda" in perguntas
    assert "CONF ALVORADA NORTE" in perguntas


def test_resposta_negativa_vira_parecer_nao(ollama_falso: str) -> None:
    _OllamaFalso.conteudo = json.dumps({"pertence": False, "explicacao": "nomes diferentes"})

    parecer = _parecerista(ollama_falso).dar_parecer("MERC HORIZ", ["Confeitaria Alvorada Ltda"])

    assert parecer.resposta is Resposta.NAO
    assert parecer.explicacao == "nomes diferentes"


@pytest.mark.parametrize("conteudo", ["não é json", json.dumps({"pertence": "talvez", "explicacao": "?"}), "{}"])
def test_resposta_fora_do_formato_vira_ia_indisponivel(ollama_falso: str, conteudo: str) -> None:
    _OllamaFalso.conteudo = conteudo

    parecer = _parecerista(ollama_falso).dar_parecer("CONF ALVORADA", ["Confeitaria Alvorada Ltda"])

    assert parecer.resposta is Resposta.INDISPONIVEL


def test_ollama_fora_do_ar_vira_ia_indisponivel_com_o_motivo() -> None:
    with socket.socket() as livre:
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]

    parecer = _parecerista(f"http://127.0.0.1:{porta}").dar_parecer("CONF ALVORADA", ["Confeitaria Alvorada Ltda"])

    assert parecer.resposta is Resposta.INDISPONIVEL
    assert f"127.0.0.1:{porta}" in parecer.explicacao
    assert parecer.modelo == "modelo-x"


def test_configuracao_le_endereco_modelo_e_tempo_limite_da_ia(tmp_path: Path) -> None:
    caminho = tmp_path / "c.toml"
    caminho.write_text(
        CONTAS + '[ia]\nendereco = "http://ia:1"\nmodelo = "m:1b"\ntempo_limite_segundos = 30\n', encoding="utf-8"
    )

    assert carregar_configuracao(caminho).ia == ConfiguracaoDaIa("http://ia:1", "m:1b", 30.0)


def test_configuracao_sem_secao_de_ia_fica_sem_ia(tmp_path: Path) -> None:
    caminho = tmp_path / "c.toml"
    caminho.write_text(CONTAS, encoding="utf-8")

    assert carregar_configuracao(caminho).ia is None


@pytest.mark.parametrize(
    "secao",
    [
        '[ia]\nendereco = "http://ia:1"\nmodelo = "m"\ntempo_limite_segundos = 30\ntemperatura = 1\n',
        '[ia]\nmodelo = "m"\ntempo_limite_segundos = 30\n',
        '[ia]\nendereco = "http://ia:1"\ntempo_limite_segundos = 30\n',
        '[ia]\nendereco = "http://ia:1"\nmodelo = "m"\n',
        '[ia]\nendereco = "http://ia:1"\nmodelo = "m"\ntempo_limite_segundos = 0\n',
    ],
)
def test_configuracao_de_ia_invalida_e_recusada(tmp_path: Path, secao: str) -> None:
    caminho = tmp_path / "c.toml"
    caminho.write_text(CONTAS + secao, encoding="utf-8")

    with pytest.raises(ConfiguracaoInvalida, match=r"\[ia\]"):
        carregar_configuracao(caminho)


@pytest.mark.integracao
def test_ollama_real_responde_parecer_estruturado() -> None:
    parecerista = PareceristaOllama(ollama_do_projeto())

    parecer = parecerista.dar_parecer("CONF ALVORADA COM", ["Confeitaria Alvorada Comercio de Alimentos Ltda"])

    assert parecer.resposta in (Resposta.SIM, Resposta.NAO)
    assert parecer.explicacao
    assert parecer.versao_do_prompt == VERSAO_DO_PROMPT
