import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from openpyxl import load_workbook

from conciliacao.armazenamento import Armazenamento
from conciliacao.dominio import MotivoDeNaoIdentificacao, Resultado
from conciliacao.execucao import executar_conciliacao
from conciliacao.normalizacao import formatar_reais
from conciliacao.saidas import gerar_workbook
from conciliacao.tela import criar_servidor
from tests.arquivos import LinhaItau, TituloProtheus, configuracao_itau, escrever_extrato_itau, escrever_protheus
from tests.pagina import Elemento, ler_pagina
from tests.parecerista import PareceristaFalso

CNPJ_B = "20.400.600/0001-80"
NOME_B = "Confeitaria Alvorada Comercio de Alimentos Ltda"


@pytest.fixture
def estado(tmp_path: Path) -> Path:
    return tmp_path / "estado.sqlite"


@pytest.fixture
def endereco(estado: Path) -> Iterator[str]:
    servidor = criar_servidor(estado, porta=0)
    linha = threading.Thread(target=servidor.serve_forever, daemon=True)
    linha.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()
        servidor.server_close()


def _abrir(endereco: str, caminho: str = "/") -> Elemento:
    with urllib.request.urlopen(endereco + caminho) as resposta:
        assert resposta.status == 200
        assert resposta.headers.get_content_type() == "text/html"
        return ler_pagina(resposta.read().decode("utf-8"))


def _html(endereco: str) -> str:
    with urllib.request.urlopen(endereco + "/") as resposta:
        texto: str = resposta.read().decode("utf-8")
        return texto


def _executar(pasta: Path, armazenamento: Armazenamento, parecerista: PareceristaFalso | None = None) -> Resultado:
    return executar_conciliacao(pasta, armazenamento, configuracao_itau(), parecerista or PareceristaFalso())


def _cobranca_e_em_analise(pasta: Path) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF NA LISTA", valor="1.000,00", vencimento="02/06/2025"),
            TituloProtheus(documento="NF NA FILA", valor="500,00", vencimento="02/06/2025"),
            TituloProtheus(documento="NF SEM CREDITO", valor="730,00", vencimento="02/06/2025"),
            TituloProtheus(documento="NF A VENCER", valor="90,00", vencimento="20/06/2025"),
        ],
    )
    escrever_extrato_itau(
        pasta,
        [
            LinhaItau("02/06/2025", "PIX RECEBIDO 10200300000140", "1.000,00"),
            LinhaItau("03/06/2025", "DEPOSITO EM DINHEIRO", "500,00"),
            LinhaItau("10/06/2025", "TARIFA BANCARIA", "1,00", tipo="D"),
        ],
    )


def _parecer_de_nome(pasta: Path) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 7", valor="3.200,00", cliente=NOME_B, cnpj=CNPJ_B)])
    escrever_extrato_itau(pasta, [LinhaItau("05/03/2025", "PIX RECEBIDO CONF ALVORADA COM", "3.200,00")])


def _texto_da_celula(valor: object) -> str:
    return "" if valor is None else str(valor)


def test_sem_execucao_a_tela_diz_que_nao_ha_execucao_sem_inventar_dados(endereco: str, estado: Path) -> None:
    pagina = _abrir(endereco)

    assert "Não há execução" in pagina.por_id("sem-execucao").texto
    assert not pagina.tem_id("resumo")
    assert pagina.todos("table") == []
    assert not estado.exists()


def test_armazenamento_sem_execucao_tambem_diz_que_nao_ha_execucao(endereco: str, armazenamento: Armazenamento) -> None:
    pagina = _abrir(endereco)

    assert "Não há execução" in pagina.por_id("sem-execucao").texto
    assert pagina.todos("table") == []


def test_resumo_e_itens_da_tela_sao_os_do_workbook_da_mesma_execucao(
    endereco: str, pasta: Path, armazenamento: Armazenamento, tmp_path: Path
) -> None:
    _cobranca_e_em_analise(pasta)
    resultado = _executar(pasta, armazenamento)
    workbook_path = tmp_path / "conciliacao.xlsx"
    gerar_workbook(resultado, workbook_path)
    workbook = load_workbook(workbook_path)

    pagina = _abrir(endereco)

    resumo_do_workbook = [
        [_texto_da_celula(c) for c in linha] for linha in workbook["Resumo"].iter_rows(values_only=True)
    ]
    assert pagina.por_id("resumo").linhas() == resumo_do_workbook
    for aba, secao in (("Lista de baixa", "lista-de-baixa"), ("Fila de exceções", "fila-de-excecoes")):
        do_workbook = [linha[0] for linha in workbook[aba].iter_rows(min_row=2, values_only=True)]
        assert [linha[0] for linha in pagina.por_id(secao).linhas()[1:]] == do_workbook
        assert do_workbook


def test_a_tela_le_a_ultima_execucao_persistida_sem_recalcular(
    endereco: str, pasta: Path, armazenamento: Armazenamento
) -> None:
    _cobranca_e_em_analise(pasta)
    _executar(pasta, armazenamento)
    resultado = _executar(pasta, armazenamento)
    for arquivo in pasta.iterdir():
        arquivo.unlink()

    pagina = _abrir(endereco)

    assert pagina.por_id("resumo").linhas()[0] == ["Execução", str(resultado.resumo.execucao)]
    assert resultado.resumo.execucao == 2
    assert len(pagina.por_id("lista-de-baixa").linhas()) == 1 + len(resultado.lista_de_baixa)


def test_lista_de_baixa_e_fila_mostram_credito_titulos_evidencia_explicacao_e_motivo(
    endereco: str, pasta: Path, armazenamento: Armazenamento
) -> None:
    _cobranca_e_em_analise(pasta)
    resultado = _executar(pasta, armazenamento)
    [na_lista] = resultado.lista_de_baixa
    [na_fila] = resultado.fila_de_excecoes

    pagina = _abrir(endereco)

    cabecalho, linha = pagina.por_id("lista-de-baixa").linhas()
    assert cabecalho == ["Item", "Crédito", "Título(s)", "Evidência", "Motivo", "Explicação"]
    item, credito, titulos, evidencia, motivo, explicacao = linha
    assert item == na_lista.identificador
    assert "PIX RECEBIDO 10200300000140" in credito and "02/06/2025" in credito and "R$ 1.000,00" in credito
    assert titulos == "NF NA LISTA (Protheus)"
    assert evidencia == "; ".join(e.value for e in na_lista.evidencia) and evidencia
    assert motivo == ""
    assert explicacao == " ".join(na_lista.explicacao.split())
    [linha_da_fila] = pagina.por_id("fila-de-excecoes").linhas()[1:]
    assert linha_da_fila[0] == na_fila.identificador
    assert "DEPOSITO EM DINHEIRO" in linha_da_fila[1]
    assert na_fila.motivo is not None and linha_da_fila[4] == na_fila.motivo.value


def test_parecer_da_ia_aparece_destacado_com_a_explicacao(
    endereco: str, pasta: Path, armazenamento: Armazenamento
) -> None:
    _parecer_de_nome(pasta)
    _executar(pasta, armazenamento, PareceristaFalso(sim_para=[("CONF ALVORADA COM", NOME_B)]))

    pagina = _abrir(endereco)

    [linha] = pagina.por_id("fila-de-excecoes").todos("tr", classe="com-parecer")
    [parecer] = linha.todos(classe="parecer")
    assert "abrevia" in parecer.texto and "sim" in parecer.texto
    assert linha.todos(classe="ia-indisponivel") == []


def test_ia_indisponivel_aparece_marcada_no_item(endereco: str, pasta: Path, armazenamento: Armazenamento) -> None:
    _parecer_de_nome(pasta)
    _executar(pasta, armazenamento, PareceristaFalso(indisponivel=True))

    pagina = _abrir(endereco)

    [linha] = pagina.por_id("fila-de-excecoes").todos("tr", classe="com-parecer")
    [marcacao] = linha.todos(classe="ia-indisponivel")
    assert marcacao.texto == "IA indisponível"


def test_lista_de_cobranca_aparece_separada_dos_titulos_em_analise(
    endereco: str, pasta: Path, armazenamento: Armazenamento
) -> None:
    _cobranca_e_em_analise(pasta)
    resultado = _executar(pasta, armazenamento)

    pagina = _abrir(endereco)

    [a_cobrar] = pagina.por_id("lista-de-cobranca").linhas()[1:]
    assert a_cobrar[0] == "NF SEM CREDITO"
    em_analise = pagina.por_id("em-analise").linhas()
    assert em_analise[0][-1] == "Créditos candidatos"
    assert sorted(linha[0] for linha in em_analise[1:]) == ["NF NA FILA", "NF NA LISTA"]
    [na_fila] = [linha for linha in em_analise[1:] if linha[0] == "NF NA FILA"]
    assert na_fila[-1] == resultado.fila_de_excecoes[0].identificador


def test_causa_raiz_tem_grafico_por_motivo_desenhado_no_servidor_e_agregacao_por_franqueado(
    endereco: str, pasta: Path, armazenamento: Armazenamento
) -> None:
    _cobranca_e_em_analise(pasta)
    resultado = _executar(pasta, armazenamento)
    causa_raiz = resultado.causa_raiz

    pagina = _abrir(endereco)

    for grafico, valor_do_grupo in (
        ("grafico-quantidade-por-motivo", lambda quantidade, _: str(quantidade)),
        ("grafico-valor-por-motivo", lambda _, valor: formatar_reais(valor)),
    ):
        svg = pagina.por_id(grafico)
        assert svg.tag == "svg"
        barras = svg.todos("g", classe="barra")
        assert [barra.todos("text")[0].texto for barra in barras] == [m.value for m in MotivoDeNaoIdentificacao]
        for barra, grupo in zip(barras, causa_raiz.por_motivo):
            assert barra.todos("text")[1].texto == valor_do_grupo(grupo.quantidade, grupo.valor_centavos)
            assert len(barra.todos("rect")) == 1
    [com_credito] = [g for g in causa_raiz.por_motivo if g.quantidade]
    [barra] = [
        b for b in pagina.por_id("grafico-quantidade-por-motivo").todos("g", classe="barra")
        if b.todos("text")[0].texto == com_credito.nome
    ]
    assert float(barra.todos("rect")[0].atributos["width"]) > 0
    por_franqueado = pagina.por_id("causa-raiz-por-franqueado").linhas()
    assert [linha[:2] for linha in por_franqueado[1:]] == [
        [g.nome, str(g.quantidade)] for g in causa_raiz.por_franqueado
    ] + [["Total", str(causa_raiz.quantidade)]]


def test_lista_vazia_aparece_como_vazia(endereco: str, pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 1", valor="700,00", vencimento="20/06/2025")])
    escrever_extrato_itau(pasta, [LinhaItau("02/06/2025", "TARIFA BANCARIA", "1,00", tipo="D")])
    _executar(pasta, armazenamento)

    pagina = _abrir(endereco)

    for secao in ("lista-de-baixa", "fila-de-excecoes", "lista-de-cobranca", "em-analise"):
        assert pagina.por_id(secao).todos("table") == []
        assert pagina.por_id(secao).todos(classe="vazia")[0].texto == "Lista vazia."
    assert len(pagina.por_id("fora-do-escopo").linhas()) == 2


def test_a_pagina_nao_usa_recursos_externos(endereco: str, pasta: Path, armazenamento: Armazenamento) -> None:
    _cobranca_e_em_analise(pasta)
    _executar(pasta, armazenamento)

    html = _html(endereco)

    pagina = ler_pagina(html)
    assert pagina.todos("script") == [] and pagina.todos("link") == [] and pagina.todos("img") == []
    assert "url(" not in html and "@import" not in html and "src=" not in html


def test_rota_desconhecida_responde_404(endereco: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(endereco + "/nada")

    assert erro.value.code == 404


def test_comando_sobe_a_tela_local_sobre_o_armazenamento(tmp_path: Path) -> None:
    with socket.socket() as livre:
        livre.bind(("127.0.0.1", 0))
        porta = livre.getsockname()[1]
    processo = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "conciliacao.tela",
            "--estado",
            str(tmp_path / "estado.sqlite"),
            "--porta",
            str(porta),
            "--sem-navegador",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert processo.stdout is not None
        linha = processo.stdout.readline()
        assert f"http://127.0.0.1:{porta}/" in linha
        pagina = _abrir(f"http://127.0.0.1:{porta}")
        assert pagina.tem_id("sem-execucao")
    finally:
        processo.terminate()
        processo.wait(timeout=10)
