import re
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from conciliacao.adaptadores import ler_pasta
from conciliacao.emissao import emitir_cobrancas
from tests.simulacao import INICIO, Simulacao, simular

_TXID = re.compile(r"[a-zA-Z0-9]{26,35}")


@pytest.fixture(params=["simulada"])
def simulacao(request: pytest.FixtureRequest, tmp_path: Path) -> Simulacao:
    assert request.param == "simulada"
    return simular(tmp_path, semente=7)


def test_emitir_duas_vezes_nao_duplica(simulacao: Simulacao) -> None:
    porta = simulacao.porta
    primeira = list(porta.emitidas)

    emitir_cobrancas(simulacao.armazenamento, simulacao.configuracao, porta)
    for cobranca in primeira:
        porta.emitir(cobranca)

    assert porta.emitidas == primeira
    assert len({(c.sistema_de_origem, c.documento) for c in primeira}) == len(primeira)


def test_identificadores_unicos_e_no_formato(simulacao: Simulacao) -> None:
    faixa = simulacao.configuracao.migracao.boleto if simulacao.configuracao.migracao else None
    assert faixa is not None
    txids = [c.txid for c in simulacao.porta.emitidas if c.txid is not None]
    nossos_numeros = [c.nosso_numero for c in simulacao.porta.emitidas if c.nosso_numero is not None]

    assert len(txids) == len(simulacao.porta.emitidas)
    assert nossos_numeros
    assert all(_TXID.fullmatch(txid) for txid in txids)
    assert all(len(n) == len(faixa.inicial) and faixa.inicial <= n <= faixa.final for n in nossos_numeros)
    assert len(set(txids)) == len(txids) and len(set(nossos_numeros)) == len(nossos_numeros)


def test_arquivos_trazidos_sao_aceitos_pelos_adaptadores_de_retorno(simulacao: Simulacao, tmp_path: Path) -> None:
    so_os_retornos = tmp_path / "so_os_retornos"
    so_os_retornos.mkdir()

    trazidos = simulacao.porta.trazer_retornos(so_os_retornos, INICIO, simulacao.plano.ultimo_dia)
    leitura = ler_pasta(so_os_retornos, simulacao.configuracao)

    assert {caminho.suffix for caminho in trazidos} == {".json", ".ret"}
    assert leitura.arquivos_recusados == []
    assert sorted(leitura.arquivos_lidos) == sorted(caminho.name for caminho in trazidos)
    assert sorted((r.tipo, r.identificador, r.data, r.valor_centavos) for r in leitura.retornos) == sorted(
        (p.tipo, p.cobranca.identificador(p.tipo), p.data, p.valor_centavos) for p in simulacao.plano.pagamentos_de_cobranca
    )


def test_trazer_um_periodo_traz_so_os_pagamentos_dele(simulacao: Simulacao, tmp_path: Path) -> None:
    pagamentos = simulacao.plano.pagamentos_de_cobranca
    [(dia, _)] = Counter(p.data for p in pagamentos).most_common(1)
    so_o_dia = tmp_path / "so_o_dia"
    so_o_dia.mkdir()

    simulacao.porta.trazer_retornos(so_o_dia, dia, dia)
    leitura = ler_pasta(so_o_dia, simulacao.configuracao)

    assert leitura.arquivos_recusados == []
    assert sorted((r.tipo, r.identificador) for r in leitura.retornos) == sorted(
        (p.tipo, p.cobranca.identificador(p.tipo)) for p in pagamentos if p.data == dia
    )


def test_identificador_de_uma_cobranca_nao_serve_para_outra(simulacao: Simulacao) -> None:
    primeira, segunda = simulacao.porta.emitidas[:2]

    with pytest.raises(ValueError, match="já usado"):
        simulacao.porta.emitir(replace(segunda, txid=primeira.txid))

    assert simulacao.porta.emitidas.count(segunda) == 1
