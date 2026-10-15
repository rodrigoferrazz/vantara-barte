import argparse
import getpass
import sys
import webbrowser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import HTTP
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from conciliacao.armazenamento import Armazenamento
from conciliacao.cli import ConciliacaoNaoRodou, PareceristaDe, conciliar_a_pasta, parecerista_configurado
from conciliacao.configuracao import Configuracao, ConfiguracaoInvalida, carregar_configuracao
from conciliacao.demonstracao import CobrancaEmitida, Demonstracao, DemonstracaoRecusada, cobrancas_emitidas
from conciliacao.decisoes import (
    DecisaoDaTelaRecusada,
    SemExecucaoParaDecidir,
    confirmar_o_lote_pela_tela,
    registrar_decisao_da_tela,
)
from conciliacao.dominio import DecisaoDaTela, LinhaDeDecisao, RelatorioDeImpacto, Resultado
from conciliacao.encargo import ParametrosDeEncargo
from conciliacao.pagina import Visao, renderizar_recusa
from conciliacao.pagina_da_analista import renderizar_analista
from conciliacao.pagina_da_cobranca import renderizar_cobranca
from conciliacao.pagina_da_demonstracao import renderizar_demonstracao
from conciliacao.pagina_da_emissao import renderizar_emissao
from conciliacao.pagina_da_gestao import renderizar_gestao
from conciliacao.pagina_da_migracao import renderizar_migracao

ENDERECO_LOCAL = "127.0.0.1"
PORTA_PADRAO = 8765
_TIPO_DO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Resposta:
    status: HTTPStatus
    corpo: str | bytes
    tipo: str = "text/html; charset=utf-8"
    cabecalhos: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Locais:
    estado: Path
    entrada: Path = Path("entrada")
    configuracao: Path = Path("conciliacao.toml")
    saida: Path = Path("conciliacao.xlsx")


    @property
    def demonstracao(self) -> Demonstracao:
        return Demonstracao(self.estado, self.entrada, self.saida)


@dataclass(frozen=True)
class Arquivo:
    nome: str
    conteudo: bytes


@dataclass(frozen=True)
class Envio:
    campos: Mapping[str, str]
    analista: str
    arquivos: Sequence[Arquivo] = ()


@dataclass(frozen=True)
class Tela:
    locais: Locais
    parecerista_de: PareceristaDe = parecerista_configurado


Rota = Callable[[Tela], Resposta]
RotaDeEnvio = Callable[[Tela, Envio], Resposta]


def _ultimo_estado(estado: Path) -> tuple[Resultado | None, Mapping[str, DecisaoDaTela], RelatorioDeImpacto | None]:
    if not estado.exists():
        return None, {}, None
    armazenamento = Armazenamento(estado)
    try:
        analise = armazenamento.ultima_analise_de_impacto()
        execucao = armazenamento.ultima_execucao()
        if execucao is None:
            return None, {}, analise
        pendentes = {p.linha.item: p for p in armazenamento.decisoes_da_tela_pendentes() if p.execucao == execucao}
        return armazenamento.carregar_resultado(execucao), pendentes, analise
    finally:
        armazenamento.fechar()


def arquivos_na_entrada(entrada: Path) -> list[str]:
    if not entrada.is_dir():
        return []
    return sorted(p.name for p in entrada.iterdir() if p.is_file() and not p.name.startswith("."))


def _pagina_da_analista(tela: Tela) -> Resposta:
    resultado, pendentes, _ = _ultimo_estado(tela.locais.estado)
    return Resposta(
        HTTPStatus.OK,
        renderizar_analista(
            resultado,
            pendentes,
            arquivos_na_entrada(tela.locais.entrada),
            tela.locais.saida.is_file(),
            _parametros_de_encargo(tela.locais.configuracao),
        ),
    )


def _parametros_de_encargo(configuracao: Path) -> ParametrosDeEncargo | None:
    try:
        return carregar_configuracao(configuracao).encargo
    except (FileNotFoundError, ConfiguracaoInvalida):
        return None


def _pagina_da_cobranca(tela: Tela) -> Resposta:
    resultado, _, _ = _ultimo_estado(tela.locais.estado)
    return Resposta(HTTPStatus.OK, renderizar_cobranca(resultado))


def _pagina_da_gestao(tela: Tela) -> Resposta:
    resultado, _, _ = _ultimo_estado(tela.locais.estado)
    return Resposta(HTTPStatus.OK, renderizar_gestao(resultado))


def _pagina_da_emissao(tela: Tela) -> Resposta:
    return Resposta(
        HTTPStatus.OK, renderizar_emissao(_cobrancas_emitidas(tela.locais.estado), tela.locais.demonstracao.ativa)
    )


def _cobrancas_emitidas(estado: Path) -> tuple[CobrancaEmitida, ...]:
    if not estado.exists():
        return ()
    armazenamento = Armazenamento(estado)
    try:
        return cobrancas_emitidas(armazenamento)
    finally:
        armazenamento.fechar()


def _pagina_da_migracao(tela: Tela) -> Resposta:
    _, _, analise = _ultimo_estado(tela.locais.estado)
    return Resposta(HTTPStatus.OK, renderizar_migracao(analise))


def _pagina_da_demonstracao(tela: Tela) -> Resposta:
    resultado, _, _ = _ultimo_estado(tela.locais.estado)
    return Resposta(
        HTTPStatus.OK, renderizar_demonstracao(tela.locais.demonstracao.situacao(), ha_execucao=resultado is not None)
    )


def _excel(tela: Tela) -> Resposta:
    saida = tela.locais.saida
    if not saida.is_file():
        return Resposta(
            HTTPStatus.NOT_FOUND,
            renderizar_recusa("Ainda não há Excel: clique em Conciliar para gerar.", "Excel não encontrado"),
        )
    return Resposta(
        HTTPStatus.OK,
        saida.read_bytes(),
        _TIPO_DO_EXCEL,
        {"Content-Disposition": f'attachment; filename="{saida.name}"'},
    )


def _decidir(tela: Tela, envio: Envio) -> Resposta:
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
        tela.locais.estado,
        lambda armazenamento: registrar_decisao_da_tela(armazenamento, linha, envio.analista, datetime.now()),
        f"/#item-{linha.item}" if linha.item else "/",
    )


def _confirmar_o_lote(tela: Tela, envio: Envio) -> Resposta:
    return _gravar(
        tela.locais.estado,
        lambda armazenamento: confirmar_o_lote_pela_tela(armazenamento, envio.analista, datetime.now()),
        "/#lista-de-baixa",
    )


def _gravar(estado: Path, gravacao: Callable[[Armazenamento], object], volta_para: str) -> Resposta:
    if not estado.exists():
        return _recusa(SemExecucaoParaDecidir("Não há execução registrada; não há o que decidir."))
    armazenamento = Armazenamento(estado)
    try:
        gravacao(armazenamento)
    except DecisaoDaTelaRecusada as recusa:
        return _recusa(recusa)
    finally:
        armazenamento.fechar()
    return _voltar(volta_para)


def _voltar(para: str = "/") -> Resposta:
    return Resposta(HTTPStatus.SEE_OTHER, "", cabecalhos={"Location": para})


def _recusa(recusa: DecisaoDaTelaRecusada) -> Resposta:
    status = HTTPStatus.CONFLICT if isinstance(recusa, SemExecucaoParaDecidir) else HTTPStatus.BAD_REQUEST
    return Resposta(status, renderizar_recusa(str(recusa)))


def _arquivo_recusado(mensagem: str) -> Resposta:
    return Resposta(HTTPStatus.BAD_REQUEST, renderizar_recusa(mensagem, "Arquivo não recebido"))


def _nome_seguro(nome: str) -> str | None:
    base = nome.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not base or base.startswith("."):
        return None
    return base


def _enviar(tela: Tela, envio: Envio) -> Resposta:
    if not envio.arquivos:
        return _arquivo_recusado("Escolha ao menos um arquivo para enviar.")
    destinos = []
    for arquivo in envio.arquivos:
        nome = _nome_seguro(arquivo.nome)
        if nome is None:
            return _arquivo_recusado(f"Nome de arquivo inválido: '{arquivo.nome}'.")
        destinos.append((nome, arquivo.conteudo))
    tela.locais.entrada.mkdir(parents=True, exist_ok=True)
    for nome, conteudo in destinos:
        (tela.locais.entrada / nome).write_bytes(conteudo)
    return _voltar("/#arquivos")


def _remover_arquivo(tela: Tela, envio: Envio) -> Resposta:
    nome = envio.campos.get("nome", "")
    if nome not in arquivos_na_entrada(tela.locais.entrada):
        return _arquivo_recusado(f"O arquivo '{nome}' não está entre os enviados.")
    (tela.locais.entrada / nome).unlink()
    return _voltar("/#arquivos")


def _conciliar(tela: Tela, envio: Envio) -> Resposta:
    locais = tela.locais
    if not arquivos_na_entrada(locais.entrada):
        return Resposta(
            HTTPStatus.BAD_REQUEST,
            renderizar_recusa("Envie os extratos e as exportações antes de conciliar.", "Conciliação não rodou"),
        )
    try:
        conciliar_a_pasta(
            locais.entrada,
            locais.configuracao,
            locais.estado,
            locais.saida,
            tela.parecerista_de,
            locais.demonstracao.ajustar,
        )
    except (ConciliacaoNaoRodou, DemonstracaoRecusada) as erro:
        return Resposta(HTTPStatus.CONFLICT, renderizar_recusa(str(erro), "Conciliação não rodou"))
    return _voltar()


def _na_demonstracao(acao: Callable[[Demonstracao, Configuracao], object]) -> RotaDeEnvio:
    def rota(tela: Tela, envio: Envio) -> Resposta:
        try:
            acao(tela.locais.demonstracao, carregar_configuracao(tela.locais.configuracao))
        except FileNotFoundError:
            return _demonstracao_recusada(f"Configuração não encontrada: {tela.locais.configuracao}")
        except (ConfiguracaoInvalida, DemonstracaoRecusada) as erro:
            return _demonstracao_recusada(str(erro))
        return _voltar(Visao.DEMONSTRACAO.value)

    return rota


def _demonstracao_recusada(mensagem: str) -> Resposta:
    return Resposta(
        HTTPStatus.CONFLICT,
        renderizar_recusa(mensagem, "Demonstração não avançou", (Visao.DEMONSTRACAO, "Voltar à demonstração")),
    )


def _zerar_a_demonstracao(tela: Tela, envio: Envio) -> Resposta:
    tela.locais.demonstracao.zerar()
    return _voltar(Visao.DEMONSTRACAO.value)


_ROTAS_GET: Mapping[str, Rota] = {
    Visao.ANALISTA.value: _pagina_da_analista,
    Visao.COBRANCA.value: _pagina_da_cobranca,
    Visao.GESTAO.value: _pagina_da_gestao,
    Visao.EMISSAO.value: _pagina_da_emissao,
    Visao.MIGRACAO.value: _pagina_da_migracao,
    Visao.DEMONSTRACAO.value: _pagina_da_demonstracao,
    "/excel": _excel,
}
_ROTAS_POST: Mapping[str, RotaDeEnvio] = {
    "/decidir": _decidir,
    "/confirmar-lote": _confirmar_o_lote,
    "/enviar": _enviar,
    "/remover-arquivo": _remover_arquivo,
    "/conciliar": _conciliar,
    "/demonstracao/emitir": _na_demonstracao(Demonstracao.emitir),
    "/demonstracao/simular": _na_demonstracao(Demonstracao.simular_pagamentos),
    "/demonstracao/zerar": _zerar_a_demonstracao,
}
_NAO_ENCONTRADA = Resposta(HTTPStatus.NOT_FOUND, "Página não encontrada.", "text/plain; charset=utf-8")


def ler_envio(tipo: str, corpo: bytes, analista: str) -> Envio:
    if not tipo.startswith("multipart/form-data"):
        return Envio(dict(parse_qsl(corpo.decode("utf-8"), keep_blank_values=True)), analista)
    mensagem = BytesParser(policy=HTTP).parsebytes(f"Content-Type: {tipo}\r\n\r\n".encode() + corpo)
    campos: dict[str, str] = {}
    arquivos: list[Arquivo] = []
    for parte in mensagem.iter_parts():
        assert isinstance(parte, EmailMessage)
        conteudo = parte.get_payload(decode=True)
        if not isinstance(conteudo, bytes):
            continue
        nome_do_arquivo = parte.get_filename()
        if nome_do_arquivo is None:
            nome_do_campo = parte.get_param("name", header="content-disposition")
            if isinstance(nome_do_campo, str):
                campos[nome_do_campo] = conteudo.decode("utf-8")
        elif nome_do_arquivo:
            arquivos.append(Arquivo(nome_do_arquivo, conteudo))
    return Envio(campos, analista, arquivos)


def criar_servidor(
    estado: Path,
    porta: int = PORTA_PADRAO,
    analista: str | None = None,
    entrada: Path = Locais.entrada,
    configuracao: Path = Locais.configuracao,
    saida: Path = Locais.saida,
    parecerista_de: PareceristaDe = parecerista_configurado,
) -> HTTPServer:
    quem_decide = analista or getpass.getuser()
    tela = Tela(Locais(estado, entrada, configuracao, saida), parecerista_de)

    class Requisicao(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            rota = _ROTAS_GET.get(urlsplit(self.path).path)
            self._responder(rota(tela) if rota is not None else _NAO_ENCONTRADA)

        def do_POST(self) -> None:
            rota = _ROTAS_POST.get(urlsplit(self.path).path)
            tamanho = int(self.headers.get("Content-Length") or 0)
            corpo = self.rfile.read(tamanho)
            if rota is None:
                self._responder(_NAO_ENCONTRADA)
                return
            envio = ler_envio(self.headers.get("Content-Type", ""), corpo, quem_decide)
            self._responder(rota(tela, envio))

        def _responder(self, resposta: Resposta) -> None:
            corpo = resposta.corpo.encode("utf-8") if isinstance(resposta.corpo, str) else resposta.corpo
            self.send_response(resposta.status)
            self.send_header("Content-Type", resposta.tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            for nome, valor in resposta.cabecalhos.items():
                self.send_header(nome, valor)
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return HTTPServer((ENDERECO_LOCAL, porta), Requisicao)


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="conciliar-tela",
        description=(
            "Abre a tela local com dois produtos: a Conciliação Assistida (Analista, cobrança e gestão) e a "
            "Cobrança Endereçada (emissão, migração e demonstração). A Analista envia os arquivos e concilia "
            "pela própria tela."
        ),
    )
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    parser.add_argument("--entrada", type=Path, default=Locais.entrada, help="pasta onde ficam os arquivos enviados")
    parser.add_argument("--configuracao", type=Path, default=Locais.configuracao)
    parser.add_argument("--saida", type=Path, default=Locais.saida, help="Excel gerado a cada conciliação")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador, só sobe a tela")
    parser.add_argument(
        "--analista", help="quem decide pela tela (padrão: o usuário do sistema que abriu a tela)", default=None
    )
    opcoes = parser.parse_args(argumentos)

    try:
        servidor = criar_servidor(
            opcoes.estado, opcoes.porta, opcoes.analista, opcoes.entrada, opcoes.configuracao, opcoes.saida
        )
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
