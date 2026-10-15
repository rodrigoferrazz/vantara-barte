import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from conciliacao.armazenamento import Armazenamento
from conciliacao.conferencia import ConferenciaDeSomaFalhou
from conciliacao.configuracao import Configuracao, ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import Resultado
from conciliacao.execucao import executar_conciliacao
from conciliacao.parecerista import PareceristaDeNome, parecerista_da_configuracao
from conciliacao.saidas import gerar_workbook

PareceristaDe = Callable[[Configuracao], PareceristaDeNome]


class ConciliacaoNaoRodou(Exception):
    def __init__(self, mensagem: str, codigo: int) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def parecerista_configurado(configuracao: Configuracao) -> PareceristaDeNome:
    return parecerista_da_configuracao(configuracao.ia)


def conciliar_a_pasta(
    pasta: Path,
    configuracao: Path,
    estado: Path,
    saida: Path,
    parecerista_de: PareceristaDe = parecerista_configurado,
    ajustar: Callable[[Configuracao], Configuracao] = lambda configuracao: configuracao,
) -> Resultado:
    if not pasta.is_dir():
        raise ConciliacaoNaoRodou(f"Pasta de entrada não encontrada: {pasta}", 2)
    try:
        carregada = ajustar(carregar_configuracao(configuracao))
    except FileNotFoundError:
        raise ConciliacaoNaoRodou(f"Configuração não encontrada: {configuracao}", 2) from None
    except ConfiguracaoInvalida as erro:
        raise ConciliacaoNaoRodou(f"Configuração inválida: {erro}", 2) from None

    armazenamento = Armazenamento(estado)
    try:
        resultado = executar_conciliacao(pasta, armazenamento, carregada, parecerista_de(carregada), workbook_anterior=saida)
    except ConferenciaDeSomaFalhou as erro:
        raise ConciliacaoNaoRodou(str(erro), 1) from None
    finally:
        armazenamento.fechar()

    gerar_workbook(resultado, saida)
    return resultado


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conciliar", description="Executa a conciliação sobre uma pasta de arquivos.")
    parser.add_argument("pasta", type=Path, help="pasta com as exportações e os Extratos, do jeito que vêm")
    parser.add_argument("--configuracao", type=Path, default=Path("conciliacao.toml"))
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    parser.add_argument("--saida", type=Path, default=Path("conciliacao.xlsx"))
    opcoes = parser.parse_args(argumentos)

    try:
        conciliar_a_pasta(opcoes.pasta, opcoes.configuracao, opcoes.estado, opcoes.saida)
    except ConciliacaoNaoRodou as erro:
        print(str(erro), file=sys.stderr)
        return erro.codigo
    print(f"Workbook gerado em {opcoes.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
