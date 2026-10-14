import ast
import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from conciliacao.adaptadores import ExtratoItau
from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import carregar_configuracao
from conciliacao.dominio import Destino, Item, MotivoDeNaoIdentificacao, RegraDaProposta, Resultado, TipoDeEvidencia
from conciliacao.execucao import executar_conciliacao
from conciliacao.parecerista import PareceristaDeNome, PareceristaOllama
from tests.parecerista import PareceristaFalso, ollama_do_projeto

RAIZ = Path(__file__).parent.parent
AMOSTRA = RAIZ / "data"
CODIGO_DE_PRODUCAO = RAIZ / "src"
DESIGNACOES_DE_RAZAO_SOCIAL = {"LTDA", "EIRELI", "EPP", "CIA", "COMERCIO"}

LISTA = Destino.LISTA_DE_BAIXA
FILA = Destino.FILA_DE_EXCECOES
FORA = Destino.FORA_DO_ESCOPO
Motivo = MotivoDeNaoIdentificacao
Evidencia = TipoDeEvidencia

DOCE_PONTO = ("DOCE PONTO COM ALIME", "Doce Ponto Comercio de Alimentos")
SABOR_CIA = ("SABOR CIA", "Rede Sabor & Cia Ltda")


@dataclass(frozen=True)
class Esperado:
    data: str
    lancamento: str
    valor: str
    destino: Destino
    titulos: tuple[str, ...] = ()
    motivo: MotivoDeNaoIdentificacao | None = None
    regra: RegraDaProposta | None = None
    evidencia: TipoDeEvidencia | None = None
    na_explicacao: tuple[str, ...] = ()


TABELA_DA_SPEC = (
    Esperado("10/07", "Liquidação NN ...678", "18.450,00", LISTA, ("NF 104521",), regra=RegraDaProposta.NOSSO_NUMERO_E_VALOR),
    Esperado("10/07", "PIX PADARIA VILA NOVA LT", "3.200,00", FILA, ("NF 104522",), Motivo.PAGADOR_PROVAVEL_PRIMEIRA_VEZ),
    Esperado("13/07", "Liquidação NN ...701", "9.870,00", LISTA, ("NF 104540",), regra=RegraDaProposta.NOSSO_NUMERO_E_VALOR),
    Esperado(
        "14/07",
        "TED DOCE PONTO COM ALIME",
        "47.630,50",
        FILA,
        ("NF 104533", "NF 104588"),
        Motivo.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
        evidencia=Evidencia.PARECER_DE_LLM,
        na_explicacao=("NF 104533 pago após o Vencimento efetivo 13/07/2026 só pelo valor original; Encargo não pago",),
    ),
    Esperado("15/07", "Liquidação NN ...712", "66.300,00", LISTA, ("NF 104551",), regra=RegraDaProposta.NOSSO_NUMERO_E_VALOR),
    Esperado("15/07", "TARIFA PACOTE COBRANCA", "1.240,00", FORA),
    Esperado("16/07", "Liquidação NN ...720", "62.500,00", FILA, ("NF 104560",), Motivo.VALOR_NAO_FECHA),
    Esperado("17/07", "PIX CANTINHO MINEIRO FRA", "14.820,00", FILA, ("NF 104571",), Motivo.VALOR_NAO_FECHA),
    Esperado("20/07", "PAGAMENTO FORNECEDOR NF 88231", "18.900,00", FORA),
    Esperado("21/07", "Liquidação NN ...740", "31.250,00", LISTA, ("NF 104580",), na_explicacao=("Encargo não pago",)),
    Esperado(
        "22/07",
        "PIX 11222333000166",
        "7.430,00",
        LISTA,
        ("NF 104595",),
        regra=RegraDaProposta.DOCUMENTO_E_VALOR_UNICO,
        na_explicacao=("Encargo não pago",),
    ),
    Esperado(
        "23/07",
        "TED CNPJ 66777888000199",
        "23.358,00",
        LISTA,
        ("NF 104601",),
        evidencia=Evidencia.CNPJ_CPF,
        na_explicacao=("principal R$ 22.900,00 e Encargo R$ 458,00",),
    ),
    Esperado(
        "24/07",
        "PIX SABOR CIA",
        "7.100,00",
        FILA,
        ("NF 104552",),
        Motivo.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
        evidencia=Evidencia.PARECER_DE_LLM,
    ),
    Esperado("27/07", "PIX NORTE PANIFICADOS EI", "12.980,00", FILA, ("FAT-2026-0332",), Motivo.PAGADOR_PROVAVEL_PRIMEIRA_VEZ),
    Esperado("28/07", "DEPOSITO NAO IDENTIFICADO", "5.670,00", FILA, ("FAT-2026-0340",), Motivo.SEM_IDENTIFICACAO_DO_PAGADOR),
    Esperado(
        "29/07",
        "PIX EMPORIO BELA VISTA A",
        "3.400,00",
        FILA,
        ("FAT-2026-0335",),
        Motivo.PAGADOR_PROVAVEL_PRIMEIRA_VEZ,
        evidencia=Evidencia.NOME_POR_PREFIXO,
    ),
    Esperado("30/07", "PIX PADARIA VILA NOVA LT", "1.850,00", FILA, (), Motivo.CREDITO_SEM_TITULO_EM_ABERTO),
    Esperado("31/07", "TARIFA PIX EMISSAO", "89,00", FORA),
)


def _centavos(valor: str) -> int:
    return int(valor.replace(".", "").replace(",", ""))


def _conciliar_a_amostra(pasta_de_estado: Path, parecerista: PareceristaDeNome) -> Resultado:
    return executar_conciliacao(
        AMOSTRA,
        Armazenamento(pasta_de_estado / "estado.sqlite"),
        carregar_configuracao(RAIZ / "conciliacao.toml"),
        parecerista,
    )


@pytest.fixture(
    scope="module",
    params=["ia falsa", pytest.param("ollama", marks=pytest.mark.integracao)],
)
def resultado(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Resultado:
    parecerista: PareceristaDeNome
    if request.param == "ollama":
        parecerista = PareceristaOllama(ollama_do_projeto())
    else:
        parecerista = PareceristaFalso(sim_para=[DOCE_PONTO, SABOR_CIA])
    return _conciliar_a_amostra(tmp_path_factory.mktemp(request.param), parecerista)


def _item(resultado: Resultado, esperado: Esperado) -> Item:
    dia, mes = (int(parte) for parte in esperado.data.split("/"))
    [item] = [
        item
        for item in resultado.itens
        if item.lancamento.data == date(2026, mes, dia) and item.lancamento.valor_centavos == _centavos(esperado.valor)
    ]
    return item


def test_totais_com_data_de_referencia_31_07(resultado: Resultado) -> None:
    totais = resultado.resumo.totais

    assert resultado.resumo.data_de_referencia.data == date(2026, 7, 31)
    assert (totais[LISTA].quantidade, totais[LISTA].valor_centavos) == (6, _centavos("156.658,00"))
    assert (totais[FILA].quantidade, totais[FILA].valor_centavos) == (9, _centavos("159.150,50"))
    assert (totais[FORA].quantidade, totais[FORA].valor_centavos) == (3, _centavos("20.229,00"))
    assert len(resultado.itens) == len(TABELA_DA_SPEC)


@pytest.mark.parametrize("esperado", TABELA_DA_SPEC, ids=lambda e: f"{e.data} {e.lancamento}")
def test_cada_lancamento_tem_o_destino_o_titulo_e_o_motivo_da_tabela_da_spec(
    resultado: Resultado, esperado: Esperado
) -> None:
    item = _item(resultado, esperado)

    assert item.destino is esperado.destino
    assert tuple(titulo.documento for titulo in item.titulos) == esperado.titulos
    assert item.motivo is esperado.motivo
    if esperado.regra:
        assert item.regra is esperado.regra
    if esperado.evidencia:
        assert item.evidencia == (esperado.evidencia,)
    for trecho in esperado.na_explicacao:
        assert trecho in item.explicacao


def test_ia_chamada_em_exatamente_dois_casos(tmp_path: Path) -> None:
    parecerista = PareceristaFalso(sim_para=[DOCE_PONTO, SABOR_CIA])

    resultado = _conciliar_a_amostra(tmp_path, parecerista)

    assert [nome for nome, _ in parecerista.chamadas] == [DOCE_PONTO[0], SABOR_CIA[0]]
    assert resultado.resumo.itens_com_parecer == 2


@pytest.mark.integracao
def test_ollama_real_e_chamado_nos_mesmos_dois_casos_e_responde(tmp_path: Path) -> None:
    resultado = _conciliar_a_amostra(tmp_path, PareceristaOllama(ollama_do_projeto()))

    com_parecer = [item.lancamento.historico for item in resultado.itens if item.pareceres]
    assert com_parecer == ["TED RECEBIDA DOCE PONTO COM ALIME", "PIX RECEBIDO SABOR CIA"]
    assert resultado.resumo.itens_ia_indisponivel == 0


def test_um_item_de_possivel_duplicidade_grao_nobre_omie_e_protheus(resultado: Resultado) -> None:
    [item] = resultado.itens_de_titulo

    assert item.motivo is Motivo.POSSIVEL_DUPLICIDADE
    assert {titulo.sistema_de_origem for titulo in item.titulos} == {"Omie", "Protheus"}
    assert all("grao nobre" in titulo.nome_do_franqueado.lower() for titulo in item.titulos)


def test_lista_de_cobranca_com_norte_panificados(resultado: Resultado) -> None:
    [titulo] = resultado.lista_de_cobranca

    assert titulo.titulo.nome_do_franqueado.lower().startswith("norte panificados")
    assert titulo.saldo_centavos == _centavos("8.120,00")


def test_nove_titulos_em_analise(resultado: Resultado) -> None:
    assert len(resultado.em_analise) == 9


def _linhas(padrao: str, separador: str) -> list[dict[str, str]]:
    [arquivo] = AMOSTRA.glob(padrao)
    with arquivo.open(encoding="utf-8") as conteudo:
        return list(csv.DictReader(conteudo, delimiter=separador))


def _identificadores_da_amostra() -> set[str]:
    protheus = _linhas("*protheus*.csv", ";")
    omie = _linhas("*omie*.csv", ",")
    extrato = _linhas("*extrato*.csv", ";")
    nomes = [linha["cliente"] for linha in protheus] + [linha["customer_name"] for linha in omie]
    for linha in extrato:
        for prefixo in ExtratoItau.historicos_com_nome_do_pagador:
            if linha["historico"].startswith(prefixo):
                nomes.append(linha["historico"].removeprefix(prefixo))
    documentos = [linha["documento"] for linha in protheus] + [linha["invoice_ref"] for linha in omie]
    numeros = [
        *(linha[campo] for linha in protheus for campo in ("cnpj", "nosso_numero")),
        *(linha["tax_id"] for linha in omie),
        *(re.findall(r"\d+", documento)[-1] for documento in documentos),
        *(numero for linha in extrato for numero in re.findall(r"\d{5,}", linha["historico"] + " " + linha["documento"])),
    ]
    valores = [linha["valor"] for linha in protheus + extrato] + [linha["amount"] for linha in omie]
    variantes_dos_valores = {
        variante
        for valor in valores
        for centavos in [_centavos(valor) if "," in valor else int(valor.replace(".", ""))]
        for variante in (
            f"{centavos // 100:,}".replace(",", ".") + f",{centavos % 100:02d}",
            f"{centavos // 100},{centavos % 100:02d}",
            f"{centavos // 100}.{centavos % 100:02d}",
            str(centavos),
        )
    }
    return {*nomes, *documentos, *numeros, *(re.sub(r"\D", "", n) for n in numeros), *variantes_dos_valores}


def test_nenhum_nome_valor_ou_numero_de_nota_da_amostra_no_codigo_de_producao() -> None:
    codigo = {arquivo: arquivo.read_text(encoding="utf-8") for arquivo in CODIGO_DE_PRODUCAO.rglob("*.py")}
    identificadores = _identificadores_da_amostra()
    assert len(identificadores) > 50

    encontrados = {
        (arquivo.relative_to(RAIZ).as_posix(), identificador)
        for identificador in identificadores
        for arquivo, texto in codigo.items()
        if re.search(rf"(?<![\w.,]){re.escape(identificador)}(?![\w]|[.,]\d)", texto, re.IGNORECASE)
    }

    assert encontrados == set()


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def _palavras(texto: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", _sem_acento(texto).upper()))


def _palavras_distintivas_da_amostra() -> set[str]:
    arquivos = [("*protheus*.csv", ";"), ("*omie*.csv", ","), ("*extrato*.csv", ";")]
    protheus, omie, extrato = (_linhas(padrao, separador) for padrao, separador in arquivos)
    cabecalhos = {campo for linhas in (protheus, omie, extrato) for campo in linhas[0]}
    inicios_de_layout = [inicio for inicio, _ in ExtratoItau.canais_pelo_inicio_do_historico]
    com_nome = ExtratoItau.historicos_com_nome_do_pagador
    textos = [linha["cliente"] for linha in protheus] + [linha["customer_name"] for linha in omie]
    for historico in (linha["historico"] for linha in extrato):
        prefixo = next((p for p in com_nome if historico.startswith(p)), None)
        if prefixo:
            textos.append(historico.removeprefix(prefixo))
        elif not any(historico.startswith(inicio) for inicio in inicios_de_layout):
            textos.append(historico)
    linguagem_do_dominio = _palavras((RAIZ / "CONTEXT.md").read_text(encoding="utf-8"))
    layout = _palavras(" ".join([*cabecalhos, *inicios_de_layout, *com_nome]))
    return {
        palavra
        for texto in textos
        for palavra in _palavras(texto)
        if len(palavra) >= 4 and palavra not in DESIGNACOES_DE_RAZAO_SOCIAL | linguagem_do_dominio | layout
    }


def test_nenhuma_palavra_distintiva_dos_nomes_e_historicos_da_amostra_nos_textos_do_codigo_de_producao() -> None:
    palavras = _palavras_distintivas_da_amostra()
    assert {"PADARIA", "CANTINHO", "SABOR", "PACOTE", "FORNECEDOR"} <= palavras

    encontradas = {
        (arquivo.relative_to(RAIZ).as_posix(), palavra, literal.value)
        for arquivo in CODIGO_DE_PRODUCAO.rglob("*.py")
        for literal in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8")))
        if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
        for palavra in palavras
        if re.search(rf"\b(?:{palavra}|{palavra.capitalize()})\b", _sem_acento(literal.value))
    }

    assert encontradas == set()
