import argparse
import sys
from pathlib import Path

from conciliacao.armazenamento import Armazenamento
from conciliacao.conferencia import ConferenciaDeSomaFalhou
from conciliacao.configuracao import ConfiguracaoInvalida, carregar_configuracao
from conciliacao.execucao import executar_conciliacao
from conciliacao.parecerista import parecerista_da_configuracao
from conciliacao.saidas import gerar_workbook


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conciliar", description="Executa a conciliação sobre uma pasta de arquivos.")
    parser.add_argument("pasta", type=Path, help="pasta com as exportações e os Extratos, do jeito que vêm")
    parser.add_argument("--configuracao", type=Path, default=Path("conciliacao.toml"))
    parser.add_argument("--estado", type=Path, default=Path("conciliacao.sqlite"))
    parser.add_argument("--saida", type=Path, default=Path("conciliacao.xlsx"))
    opcoes = parser.parse_args(argumentos)

    if not opcoes.pasta.is_dir():
        print(f"Pasta de entrada não encontrada: {opcoes.pasta}", file=sys.stderr)
        return 2
    try:
        configuracao = carregar_configuracao(opcoes.configuracao)
    except FileNotFoundError:
        print(f"Configuração não encontrada: {opcoes.configuracao}", file=sys.stderr)
        return 2
    except ConfiguracaoInvalida as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        return 2

    armazenamento = Armazenamento(opcoes.estado)
    try:
        resultado = executar_conciliacao(
            opcoes.pasta, armazenamento, configuracao, parecerista_da_configuracao(configuracao.ia)
        )
    except ConferenciaDeSomaFalhou as erro:
        print(str(erro), file=sys.stderr)
        return 1
    finally:
        armazenamento.fechar()

    gerar_workbook(resultado, opcoes.saida)
    print(f"Workbook gerado em {opcoes.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
