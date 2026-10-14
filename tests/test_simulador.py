import json
from collections import Counter
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from conciliacao.adaptadores import ler_pasta
from conciliacao.dominio import Canal, Destino, Item, Resultado, TipoDeIdentificador
from conciliacao.encargo import ParametrosDeEncargo, multa_e_juros
from conciliacao.gerador import Caso
from conciliacao.porta import CobrancaIdentificada, PagamentoInvalido
from conciliacao.simulador import (
    ConfiguracaoDoSimulador,
    ConfiguracaoDoSimuladorInvalida,
    CreditoEsperado,
    Desfecho,
    ProporcoesDoSimulador,
    plano_por_proporcoes,
)
from tests.simulacao import INICIO, Simulacao, simular

SEMENTE = 5
TOLERANCIA = 0.03
ENCARGO = ParametrosDeEncargo(multa_percentual=Decimal("2"), juros_ao_mes_percentual=Decimal("1"))

type _Chave = tuple[str, date, str, int]


def _chave_do_item(item: Item) -> _Chave:
    lancamento = item.lancamento
    return (lancamento.conta, lancamento.data, lancamento.historico, lancamento.valor_centavos)


def _gabarito(simulacao: Simulacao) -> dict[_Chave, CreditoEsperado]:
    return {(e.conta, e.data, e.historico, e.valor_centavos): e for e in simulacao.plano.gabarito}


def _cobrancas_por_txid(simulacao: Simulacao) -> dict[str, CobrancaIdentificada]:
    return {c.txid: c for c in simulacao.porta.emitidas if c.txid is not None}


@pytest.fixture(scope="module")
def volume(tmp_path_factory: pytest.TempPathFactory) -> Simulacao:
    return simular(tmp_path_factory.mktemp("volume"), SEMENTE, titulos=1_900, franqueados=210, encargo=ENCARGO)


@pytest.fixture(scope="module")
def ponta_a_ponta(tmp_path_factory: pytest.TempPathFactory) -> tuple[Simulacao, Resultado]:
    simulacao = simular(tmp_path_factory.mktemp("ponta_a_ponta"), SEMENTE, encargo=ENCARGO)
    return simulacao, simulacao.conciliar()


def test_proporcoes_respeitadas_dentro_da_tolerancia_em_volume(volume: Simulacao) -> None:
    proporcoes = ProporcoesDoSimulador()
    desfechos = Counter(esperado.desfecho for esperado in volume.plano.gabarito)
    total = sum(desfechos.values())

    assert total == len({(c.sistema_de_origem, c.documento) for c in volume.porta.emitidas}) > 1_500
    for desfecho in Desfecho:
        assert abs(desfechos[desfecho] / total - proporcoes.de(desfecho)) <= TOLERANCIA, desfecho


def test_outras_proporcoes_mudam_o_volume_de_cada_desfecho(tmp_path: Path) -> None:
    proporcoes = ProporcoesDoSimulador(em_dia=0.2, atraso_com_multa=0.2, atraso_sem_encargo=0.2, parcial=0.2, credito_solto=0.2)
    simulacao = simular(tmp_path, SEMENTE, proporcoes=proporcoes, titulos=1_000, franqueados=120)

    desfechos = Counter(esperado.desfecho for esperado in simulacao.plano.gabarito)
    total = sum(desfechos.values())
    for desfecho in Desfecho:
        assert abs(desfechos[desfecho] / total - 0.2) <= TOLERANCIA, desfecho


@pytest.mark.parametrize(
    "proporcoes",
    [ProporcoesDoSimulador(parcial=-0.05, credito_solto=0.3), ProporcoesDoSimulador(credito_solto=0.5)],
    ids=["negativa", "soma diferente de 1"],
)
def test_proporcoes_invalidas_sao_recusadas(volume: Simulacao, proporcoes: ProporcoesDoSimulador) -> None:
    with pytest.raises(ConfiguracaoDoSimuladorInvalida):
        plano_por_proporcoes(
            volume.porta.emitidas,
            volume.armazenamento.ultima_fotografia(),
            volume.configuracao,
            ConfiguracaoDoSimulador(semente=SEMENTE, inicio=INICIO, proporcoes=proporcoes),
        )


def test_pix_com_txid_sempre_com_o_valor_da_cobranca_com_ou_sem_multa_e_juros(volume: Simulacao) -> None:
    [arquivo] = [p for p in volume.simulados if p.suffix == ".json"]
    cobrancas = _cobrancas_por_txid(volume)
    com_encargo = 0

    for pix in json.loads(arquivo.read_text(encoding="utf-8"))["pix"]:
        cobranca = cobrancas[pix["txid"]]
        data = date.fromisoformat(pix["horario"][:10])
        componentes = {nome: _centavos(c["valor"]) for nome, c in pix["componentesValor"].items()}
        multa, juros = multa_e_juros(cobranca.valor_centavos, cobranca.vencimento, data, ENCARGO)
        assert componentes == {k: v for k, v in {"original": cobranca.valor_centavos, "multa": multa, "juros": juros}.items() if v}
        assert _centavos(pix["valor"]) == cobranca.valor_centavos + multa + juros
        com_encargo += bool(multa)

    assert com_encargo > 0


def test_valor_a_menos_com_identificador_so_em_boleto_parcial_autorizado(volume: Simulacao) -> None:
    gabarito = volume.plano.gabarito
    abaixo_com_identificador = [e for e in gabarito if e.identificador is not None and e.valor_centavos < _valor_do_titulo(volume, e)]
    retornos = ler_pasta(volume.pasta, volume.configuracao).retornos
    nominais = {c.identificador(t): c.valor_centavos for c in volume.porta.emitidas for t in TipoDeIdentificador if c.identificador(t)}

    assert abaixo_com_identificador
    assert {(e.canal, e.desfecho) for e in abaixo_com_identificador} == {(Canal.BOLETO, Desfecho.PARCIAL)}
    assert all(r.tipo is TipoDeIdentificador.NOSSO_NUMERO for r in retornos if r.valor_centavos < nominais[r.identificador])
    assert any(e.desfecho is Desfecho.PARCIAL and e.identificador is None for e in gabarito)


def test_porta_simulada_recusa_pagamento_que_a_spec_nao_permite(volume: Simulacao) -> None:
    pix = next(p for p in volume.plano.pagamentos_de_cobranca if p.tipo is TipoDeIdentificador.TXID)
    boleto = next(p for p in volume.plano.pagamentos_de_cobranca if p.tipo is TipoDeIdentificador.NOSSO_NUMERO)
    nao_emitida = replace(pix.cobranca, txid="CI999999999999999999999999999999")

    with pytest.raises(PagamentoInvalido, match="valor da cobrança"):
        volume.porta.pagar(replace(pix, valor_centavos=pix.valor_centavos - 1))
    with pytest.raises(PagamentoInvalido, match="já foi pago"):
        volume.porta.pagar(pix)
    with pytest.raises(PagamentoInvalido, match="acima"):
        volume.porta.pagar(replace(boleto, valor_centavos=boleto.cobranca.valor_centavos * 2))
    with pytest.raises(PagamentoInvalido, match="não foi emitido"):
        volume.porta.pagar(replace(pix, cobranca=nao_emitida))


def test_credito_solto_vem_por_pix_ted_ou_deposito_com_a_bagunca_de_nome_do_gerador(volume: Simulacao) -> None:
    soltos = [e for e in volume.plano.gabarito if e.identificador is None]

    assert {e.canal for e in soltos} == {Canal.PIX, Canal.TED, Canal.DEPOSITO}
    assert {e.bagunca for e in soltos} == {
        Caso.CNPJ_NO_HISTORICO, Caso.NOME_TRUNCADO, Caso.NOME_ABREVIADO, Caso.NOME_INVERTIDO, Caso.DEPOSITO_SEM_NOME
    }  # fmt: skip
    assert all(e.historico.startswith("DEPOSITO") for e in soltos if e.canal is Canal.DEPOSITO)


def test_gabarito_traz_destino_titulos_e_motivo_de_cada_credito(volume: Simulacao) -> None:
    gabarito = volume.plano.gabarito

    assert {e.destino for e in gabarito} == {Destino.LISTA_DE_BAIXA, Destino.FILA_DE_EXCECOES}
    assert all(len(e.titulos) == 1 for e in gabarito)
    assert all((e.motivo is None) == (e.destino is Destino.LISTA_DE_BAIXA) for e in gabarito)
    assert len({(e.conta, e.data, e.valor_centavos) for e in gabarito}) == len(gabarito)


def test_mesma_semente_gera_exatamente_os_mesmos_arquivos(tmp_path: Path) -> None:
    def arquivos(simulacao: Simulacao) -> dict[str, bytes]:
        return {caminho.name: caminho.read_bytes() for caminho in simulacao.simulados}

    primeira = arquivos(simular(tmp_path / "primeira", SEMENTE))
    segunda = arquivos(simular(tmp_path / "segunda", SEMENTE))
    outra = arquivos(simular(tmp_path / "outra", SEMENTE + 1))

    assert {nome.rsplit(".", 1)[1] for nome in primeira} == {"csv", "json", "ret"}
    assert primeira == segunda
    assert primeira != outra


def test_ponta_a_ponta_extrato_e_retornos_simulados_sao_aceitos(ponta_a_ponta: tuple[Simulacao, Resultado]) -> None:
    simulacao, resultado = ponta_a_ponta
    gabarito = _gabarito(simulacao)

    assert resultado.arquivos_recusados == ()
    assert {_chave_do_item(item) for item in resultado.itens if item.destino is not Destino.FORA_DO_ESCOPO} == set(gabarito)
    assert resultado.resumo.retornos_sem_credito == ()


def test_ponta_a_ponta_nenhum_item_da_lista_de_baixa_diverge_do_gabarito(ponta_a_ponta: tuple[Simulacao, Resultado]) -> None:
    simulacao, resultado = ponta_a_ponta
    gabarito = _gabarito(simulacao)

    divergentes = [
        (item.lancamento.historico, item.explicacao)
        for item in resultado.lista_de_baixa
        if gabarito[_chave_do_item(item)].destino is not Destino.LISTA_DE_BAIXA
        or frozenset((t.sistema_de_origem, t.documento) for t in item.titulos) != gabarito[_chave_do_item(item)].titulos
    ]

    assert divergentes == []
    assert len(resultado.lista_de_baixa) > len(gabarito) / 2


def test_ponta_a_ponta_destino_e_motivo_de_cada_credito_seguem_o_gabarito(ponta_a_ponta: tuple[Simulacao, Resultado]) -> None:
    simulacao, resultado = ponta_a_ponta
    gabarito = _gabarito(simulacao)

    divergentes = Counter(
        (esperado.desfecho, esperado.canal, esperado.motivo, item.motivo)
        for item in resultado.itens
        if (esperado := gabarito.get(_chave_do_item(item))) is not None
        and (item.destino, item.motivo) != (esperado.destino, esperado.motivo)
    )

    assert divergentes == Counter()


def _valor_do_titulo(simulacao: Simulacao, esperado: CreditoEsperado) -> int:
    [chave] = esperado.titulos
    return next(c.valor_centavos for c in simulacao.porta.emitidas if (c.sistema_de_origem, c.documento) == chave)


def _centavos(valor: str) -> int:
    reais, centavos = valor.split(".")
    return int(reais) * 100 + int(centavos)
