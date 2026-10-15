import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest

from conciliacao.dominio import RegraDaProposta
from conciliacao.pagina_da_analista import POR_QUE_DA_REGRA
from conciliacao.tela import criar_servidor
from tests.arquivos import LinhaItau, TituloProtheus, escrever_extrato_itau, escrever_protheus
from tests.pagina import Elemento, ler_pagina
from tests.parecerista import PareceristaFalso

CONFIGURACAO = '[[contas]]\npadrao = "itau_cobranca*.csv"\nbanco = "itau"\nconta = "1234-5"\n'
CNPJ_B = "20.400.600/0001-80"
NOME_B = "Confeitaria Alvorada Comercio de Alimentos Ltda"
DEMONSTRACAO = "/enderecada/demonstracao"
EMISSAO = "/enderecada/emissao"


@pytest.fixture
def estado(tmp_path: Path) -> Path:
    return tmp_path / "estado.sqlite"


@pytest.fixture
def saida(tmp_path: Path) -> Path:
    return tmp_path / "conciliacao.xlsx"


@pytest.fixture
def endereco(estado: Path, pasta: Path, saida: Path, tmp_path: Path) -> Iterator[str]:
    configuracao = tmp_path / "conciliacao.toml"
    configuracao.write_text(CONFIGURACAO, encoding="utf-8")
    servidor = criar_servidor(
        estado,
        porta=0,
        entrada=pasta,
        configuracao=configuracao,
        saida=saida,
        parecerista_de=lambda _: PareceristaFalso(),
    )
    linha = threading.Thread(target=servidor.serve_forever, daemon=True)
    linha.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_address[1]}"
    finally:
        servidor.shutdown()
        servidor.server_close()


def _abrir(endereco: str, caminho: str = DEMONSTRACAO) -> Elemento:
    with urllib.request.urlopen(endereco + caminho) as resposta:
        return ler_pagina(resposta.read().decode("utf-8"))


def _postar(endereco: str, caminho: str, volta_para: str = DEMONSTRACAO) -> Elemento:
    with urllib.request.urlopen(urllib.request.Request(endereco + caminho, data=b"", method="POST")) as resposta:
        assert resposta.status == 200
        assert urllib.parse.urlsplit(resposta.url).path == volta_para
        return ler_pagina(resposta.read().decode("utf-8"))


def _postar_recusado(endereco: str, caminho: str) -> tuple[int, str]:
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(urllib.request.Request(endereco + caminho, data=b"", method="POST"))
    return erro.value.code, ler_pagina(erro.value.read().decode("utf-8")).por_id("recusa").texto


def _titulos_a_vencer_e_vencido(pasta: Path) -> None:
    escrever_protheus(
        pasta,
        [
            TituloProtheus(documento="NF COM NOSSO NUMERO", valor="1.000,00", nosso_numero="12345", vencimento="20/06/2025"),
            TituloProtheus(documento="NF SEM NOSSO NUMERO", valor="2.500,00", cliente=NOME_B, cnpj=CNPJ_B, vencimento="25/06/2025"),
            TituloProtheus(documento="NF VENCIDA", valor="730,00", vencimento="02/06/2025"),
        ],
    )  # fmt: skip
    escrever_extrato_itau(pasta, [LinhaItau("10/06/2025", "TARIFA BANCARIA", "1,00", tipo="D")])


def test_emitir_simular_e_conciliar_leva_os_pagamentos_a_lista_pelo_identificador(
    endereco: str, pasta: Path
) -> None:
    _titulos_a_vencer_e_vencido(pasta)
    _postar(endereco, "/conciliar", "/")

    pagina = _postar(endereco, "/demonstracao/emitir")

    assert "Simulação" in pagina.por_id("marca-de-simulacao").texto
    assert "3 cobrança(s) emitida(s)" in pagina.por_id("demonstracao").texto
    emissao = _abrir(endereco, EMISSAO)
    cobrancas = emissao.por_id("cobrancas-emitidas").linhas()
    assert cobrancas[0] == ["Franqueado", "Título", "Valor", "Vencimento", "txid", "Nosso número", "Situação"]
    por_titulo = {linha[1]: linha for linha in cobrancas[1:]}
    assert {titulo: linha[0] for titulo, linha in por_titulo.items()} == {
        "NF COM NOSSO NUMERO (Protheus)": "Franquia Teste Ltda",
        "NF SEM NOSSO NUMERO (Protheus)": NOME_B,
        "NF VENCIDA (Protheus)": "Franquia Teste Ltda",
    }
    assert all(linha[4] != "-" for linha in cobrancas[1:])
    assert por_titulo["NF COM NOSSO NUMERO (Protheus)"][5] == "-"
    assert por_titulo["NF SEM NOSSO NUMERO (Protheus)"][5] != "-"
    assert [linha[6] for linha in cobrancas[1:]] == ["Emitida"] * 3
    assert "Simulação" in emissao.por_id("marca-de-simulacao").texto
    assert not pagina.tem_id("ver-na-conciliacao")

    pagina = _postar(endereco, "/demonstracao/simular")

    gerados = set(p.name for p in pasta.iterdir()) - {"receber_protheus.csv", "itau_cobranca.csv"}
    assert "itau_cobranca_demonstracao.csv" in gerados
    assert gerados - {"itau_cobranca_demonstracao.csv"}
    assert set(pagina.por_id("pagamentos-simulados").texto.split()) >= gerados
    assert "disabled" in pagina.por_id("simular-pagamentos").todos("button")[0].atributos
    assert pagina.por_id("ver-na-conciliacao").atributos["href"] == "/#arquivos"

    pagina = _postar(endereco, "/conciliar", "/")

    lista = pagina.por_id("itens-da-lista")
    linhas = lista.linhas()[1:]
    assert sorted(linha[1] for linha in linhas) == [
        "NF COM NOSSO NUMERO (Protheus)",
        "NF SEM NOSSO NUMERO (Protheus)",
        "NF VENCIDA (Protheus)",
    ]
    for linha in linhas:
        assert re.match(r"Pagamento endereçado: o (Pix|boleto) já dizia a fatura", linha[4])
        assert POR_QUE_DA_REGRA[RegraDaProposta.IDENTIFICADOR_E_VALOR] in linha[4]
        assert "Identificador de cobrança" in linha[4]
    assert [tr.classes for tr in lista.todos("tr")[1:]] == [{"destacada"}] * 3
    situacoes = [linha[6] for linha in _abrir(endereco, EMISSAO).por_id("cobrancas-emitidas").linhas()[1:]]
    assert all(situacao.startswith("Paga em ") for situacao in situacoes)


def test_pagamento_que_fechou_sem_identificador_nao_ganha_destaque(endereco: str, pasta: Path) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="20/06/2025")])
    escrever_extrato_itau(pasta, [LinhaItau("02/06/2025", "PIX RECEBIDO 10200300000140", "1.000,00")])

    pagina = _postar(endereco, "/conciliar", "/")

    lista = pagina.por_id("itens-da-lista")
    assert len(lista.linhas()) == 2
    assert lista.todos(classe="destacada") == [] and lista.todos(classe="enderecado") == []


def test_zerar_volta_estado_entrada_e_excel_ao_que_eram_antes_da_emissao(
    endereco: str, pasta: Path, estado: Path, saida: Path
) -> None:
    _titulos_a_vencer_e_vencido(pasta)
    _postar(endereco, "/conciliar", "/")
    entrada_antes = {p.name: p.read_bytes() for p in pasta.iterdir()}
    estado_antes, excel_antes = estado.read_bytes(), saida.read_bytes()
    _postar(endereco, "/demonstracao/emitir")
    _postar(endereco, "/demonstracao/simular")
    _postar(endereco, "/conciliar", "/")

    pagina = _postar(endereco, "/demonstracao/zerar")

    assert {p.name: p.read_bytes() for p in pasta.iterdir()} == entrada_antes
    assert estado.read_bytes() == estado_antes
    assert saida.read_bytes() == excel_antes
    assert _abrir(endereco, "/").por_id("resumo").linhas()[0] == ["Execução", "1"]
    emissao = _abrir(endereco, EMISSAO)
    assert emissao.tem_id("sem-cobrancas-emitidas") and not emissao.tem_id("marca-de-simulacao")
    assert "disabled" in pagina.por_id("zerar-demonstracao").todos("button")[0].atributos
    assert not any(p.name.endswith(".demonstracao") for p in estado.parent.iterdir())


def test_titulo_ja_vencido_e_emitido_e_pago_como_se_a_cobranca_tivesse_saido_antes_do_vencimento(
    endereco: str, pasta: Path
) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF VENCIDA", valor="730,00", vencimento="02/06/2025")])
    escrever_extrato_itau(pasta, [LinhaItau("10/06/2025", "TARIFA BANCARIA", "1,00", tipo="D")])
    _postar(endereco, "/conciliar", "/")

    _postar(endereco, "/demonstracao/emitir")
    _postar(endereco, "/demonstracao/simular")
    pagina = _postar(endereco, "/conciliar", "/")

    [linha] = pagina.por_id("itens-da-lista").linhas()[1:]
    assert linha[1] == "NF VENCIDA (Protheus)"
    assert POR_QUE_DA_REGRA[RegraDaProposta.IDENTIFICADOR_E_VALOR] in linha[4]
    pago_em = datetime.strptime(linha[2][:10], "%d/%m/%Y").date()
    assert date(2025, 5, 26) <= pago_em <= date(2025, 6, 2)
    [cobranca] = _abrir(endereco, EMISSAO).por_id("cobrancas-emitidas").linhas()[1:]
    assert cobranca[6] == f"Paga em {linha[2][:10]}"


def test_sem_titulo_em_aberto_a_emissao_recusa_e_a_demonstracao_nao_comeca(endereco: str, pasta: Path) -> None:
    escrever_protheus(pasta, [])
    escrever_extrato_itau(pasta, [LinhaItau("10/06/2025", "TARIFA BANCARIA", "1,00", tipo="D")])
    _postar(endereco, "/conciliar", "/")

    codigo, mensagem = _postar_recusado(endereco, "/demonstracao/emitir")

    assert codigo == 409
    assert "Nenhum título em aberto" in mensagem
    pagina = _abrir(endereco)
    assert "disabled" in pagina.por_id("zerar-demonstracao").todos("button")[0].atributos
    assert "disabled" in pagina.por_id("simular-pagamentos").todos("button")[0].atributos


def test_sem_execucao_nao_emite_e_sem_emissao_nao_simula(endereco: str, pasta: Path) -> None:
    codigo, mensagem = _postar_recusado(endereco, "/demonstracao/emitir")
    assert codigo == 409 and "Concilie antes" in mensagem

    codigo, mensagem = _postar_recusado(endereco, "/demonstracao/simular")
    assert codigo == 409 and "Emita as cobranças" in mensagem
