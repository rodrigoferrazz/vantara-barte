from datetime import date, datetime
from pathlib import Path

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao
from conciliacao.decisoes import registrar_decisao_da_tela
from conciliacao.dominio import LinhaDeDecisao, Resultado, TipoDeDecisao, TipoDeEvidencia
from conciliacao.emissao import emitir_cobrancas
from conciliacao.execucao import executar_conciliacao
from conciliacao.porta import CobrancaIdentificada, PortaSimulada
from conciliacao.saidas import ABA_DA_FILA_DE_EXCECOES, linhas_do_resumo
from tests.arquivos import (
    FRANQUEADO_DOS_TITULOS,
    LinhaItau,
    MovimentoCnab,
    TituloProtheus,
    configuracao_com_boleto,
    escrever_extrato_itau,
    escrever_linhas,
    escrever_pix_recebidos,
    escrever_protheus,
    escrever_retorno_cnab,
    linhas_do_retorno_cnab,
    pix_recebido,
)
from tests.parecerista import PareceristaFalso

REFERENCIA = LinhaItau("05/03/2025", "TARIFA MANUTENCAO CONTA", "9,90", tipo="D")
OUTRO_FRANQUEADO = "20300400"
TITULOS = [
    TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025"),
    TituloProtheus(
        documento="NF 2",
        valor="1.000,00",
        vencimento="10/03/2025",
        cliente="Outra Rede Comercio Ltda",
        cnpj="20.300.400/0001-50",
    ),
]


def _configuracao() -> Configuracao:
    return configuracao_com_boleto(migrados=(FRANQUEADO_DOS_TITULOS, OUTRO_FRANQUEADO))


def _conciliar(pasta: Path, armazenamento: Armazenamento) -> Resultado:
    return executar_conciliacao(pasta, armazenamento, _configuracao(), PareceristaFalso())


def _emitir(pasta: Path, armazenamento: Armazenamento) -> dict[str, CobrancaIdentificada]:
    escrever_protheus(pasta, TITULOS)
    escrever_extrato_itau(pasta, [REFERENCIA])
    _conciliar(pasta, armazenamento)
    porta = PortaSimulada()
    emitir_cobrancas(armazenamento, _configuracao(), porta)
    return {cobranca.documento: cobranca for cobranca in porta.emitidas}


def _txid(cobranca: CobrancaIdentificada) -> str:
    assert cobranca.txid is not None
    return cobranca.txid


def _nosso_numero(cobranca: CobrancaIdentificada) -> str:
    assert cobranca.nosso_numero is not None
    return cobranca.nosso_numero


def _pago(txid: str, fim_do_e2e: str, pagador: dict[str, str] | None = None) -> dict[str, object]:
    recebido = pix_recebido(txid, "1000.00", horario="2025-03-06T10:00:00Z", fim_do_e2e=fim_do_e2e)
    if pagador is not None:
        recebido["pagador"] = pagador
    return recebido


def _identificados_na_lista(resultado: Resultado) -> dict[str, list[str]]:
    return {
        item.lancamento.historico: [t.documento for t in item.titulos]
        for item in resultado.lista_de_baixa
        if item.evidencia == (TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA,)
    }


def test_dois_franqueados_com_o_mesmo_valor_no_mesmo_dia_sao_separados_pelo_nome_do_pagador(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("06/03/2025", "PIX RECEBIDO OUTRA REDE COM", "1.000,00"),
            LinhaItau("06/03/2025", "PIX RECEBIDO FRANQUIA TESTE", "1.000,00"),
        ],
    )
    escrever_pix_recebidos(
        pasta,
        [
            _pago(_txid(emitidas["NF 1"]), "1", {"cnpj": "10200300000140", "nome": "Franquia Teste Ltda"}),
            _pago(_txid(emitidas["NF 2"]), "2", {"cnpj": "20300400000150", "nome": "Outra Rede"}),
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert _identificados_na_lista(resultado) == {
        "PIX RECEBIDO FRANQUIA TESTE": ["NF 1"],
        "PIX RECEBIDO OUTRA REDE COM": ["NF 2"],
    }
    assert resultado.resumo.retornos_sem_credito == ()


def test_dois_franqueados_com_o_mesmo_valor_no_mesmo_dia_sao_separados_pelo_cnpj_do_pagador_no_historico(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("06/03/2025", "TED RECEBIDA 20.300.400/0001-50", "1.000,00"),
            LinhaItau("06/03/2025", "TED RECEBIDA 10.200.300/0001-40", "1.000,00"),
        ],
    )
    escrever_pix_recebidos(
        pasta,
        [
            _pago(_txid(emitidas["NF 1"]), "1", {"cnpj": "10200300000140", "nome": "Nome Que Nao Aparece"}),
            _pago(_txid(emitidas["NF 2"]), "2", {"cnpj": "20300400000150"}),
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert _identificados_na_lista(resultado) == {
        "TED RECEBIDA 10.200.300/0001-40": ["NF 1"],
        "TED RECEBIDA 20.300.400/0001-50": ["NF 2"],
    }


def test_boleto_desempata_pelo_pagador_do_segmento_t(pasta: Path, armazenamento: Armazenamento) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("12/03/2025", "TED RECEBIDA SOCIO DESCONHECIDO", "1.000,00"),
            LinhaItau("12/03/2025", "TED RECEBIDA FRANQUIA TES", "1.000,00"),
        ],
    )
    escrever_retorno_cnab(
        pasta,
        [MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=100000)],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert _identificados_na_lista(resultado) == {"TED RECEBIDA FRANQUIA TES": ["NF 1"]}


def test_empate_que_persiste_nao_enriquece_e_os_creditos_seguem_a_fase_1(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00"),
            LinhaItau("06/03/2025", "PIX RECEBIDO BELTRANO", "1.000,00"),
        ],
    )
    escrever_pix_recebidos(
        pasta,
        [
            _pago(_txid(emitidas["NF 1"]), "1", {"cnpj": "10200300000140", "nome": "Franquia Teste Ltda"}),
            _pago(_txid(emitidas["NF 2"]), "2"),
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert resultado.lista_de_baixa == []
    assert len(resultado.fila_de_excecoes) == 2
    assert all(TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA not in item.evidencia for item in resultado.fila_de_excecoes)
    pendentes = resultado.resumo.retornos_sem_credito
    assert sorted(p.retorno.identificador for p in pendentes) == sorted(
        [_txid(emitidas["NF 1"]), _txid(emitidas["NF 2"])]
    )
    assert all("empate" in p.descrever() for p in pendentes)


def test_um_retorno_com_dois_creditos_e_pagador_que_nao_bate_com_nenhum_nao_enriquece(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00"),
            LinhaItau("06/03/2025", "PIX RECEBIDO BELTRANO", "1.000,00"),
        ],
    )
    escrever_pix_recebidos(
        pasta, [_pago(_txid(emitidas["NF 1"]), "1", {"cnpj": "10200300000140", "nome": "Franquia Teste Ltda"})]
    )

    resultado = _conciliar(pasta, armazenamento)

    assert resultado.lista_de_baixa == []
    assert all(TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA not in item.evidencia for item in resultado.fila_de_excecoes)


def test_retorno_desempatado_libera_o_outro_par_na_mesma_execucao(pasta: Path, armazenamento: Armazenamento) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00"),
            LinhaItau("06/03/2025", "PIX RECEBIDO FRANQUIA TESTE", "1.000,00"),
        ],
    )
    escrever_pix_recebidos(
        pasta,
        [
            _pago(_txid(emitidas["NF 1"]), "1", {"cnpj": "10200300000140", "nome": "Franquia Teste Ltda"}),
            _pago(_txid(emitidas["NF 2"]), "2"),
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert _identificados_na_lista(resultado) == {
        "PIX RECEBIDO FRANQUIA TESTE": ["NF 1"],
        "PIX RECEBIDO FULANO": ["NF 2"],
    }


def test_retorno_sem_credito_aparece_no_resumo_e_e_ligado_quando_o_extrato_chega(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    pix = escrever_pix_recebidos(pasta, [_pago(_txid(emitidas["NF 1"]), "1")])

    antes = _conciliar(pasta, armazenamento)

    [pendente] = antes.resumo.retornos_sem_credito
    assert pendente.retorno.identificador == _txid(emitidas["NF 1"])
    assert "nenhum Crédito" in pendente.descrever()
    linhas = dict(linhas_do_resumo(antes))
    assert linhas["Retornos de cobrança sem Crédito"] == 1
    assert any(rotulo.startswith("Sem Crédito: txid") for rotulo in linhas)

    pix.unlink()
    escrever_extrato_itau(pasta, [REFERENCIA, LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00")])
    depois = _conciliar(pasta, armazenamento)

    assert _identificados_na_lista(depois) == {"PIX RECEBIDO FULANO": ["NF 1"]}
    assert depois.resumo.retornos_sem_credito == ()
    assert "Retornos de cobrança sem Crédito" not in dict(linhas_do_resumo(depois))
    assert armazenamento.carregar_resultado(antes.resumo.execucao).resumo.retornos_sem_credito == (pendente,)


def test_reimportar_o_mesmo_retorno_nao_duplica_pela_chave_de_cada_tipo(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    pago = _pago(_txid(emitidas["NF 1"]), "1")
    escrever_pix_recebidos(pasta, [pago])
    escrever_pix_recebidos(pasta, [pago], nome="pix_recebidos_de_novo.json")
    boleto = MovimentoCnab(_nosso_numero(emitidas["NF 2"]), valor_nominal=100000, valor_pago=100000)
    escrever_retorno_cnab(pasta, [boleto])
    escrever_retorno_cnab(pasta, [boleto], nome="retorno_cnab_de_novo.ret")
    escrever_retorno_cnab(pasta, [MovimentoCnab(boleto.nosso_numero, 100000, 100000, ocorrencia="13032025")], nome="retorno_cnab_outra_ocorrencia.ret")

    primeira = _conciliar(pasta, armazenamento)
    segunda = _conciliar(pasta, armazenamento)

    for resultado in (primeira, segunda):
        assert sorted((p.retorno.tipo.value, p.retorno.identificador) for p in resultado.resumo.retornos_sem_credito) == [
            ("nosso número", boleto.nosso_numero),
            ("nosso número", boleto.nosso_numero),
            ("txid", _txid(emitidas["NF 1"])),
        ]


def test_arquivo_de_retorno_com_pagador_fora_do_layout_e_recusado_sozinho(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(pasta, [REFERENCIA, LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00")])
    escrever_pix_recebidos(pasta, [_pago(_txid(emitidas["NF 1"]), "1")])
    escrever_pix_recebidos(pasta, [_pago(_txid(emitidas["NF 2"]), "2", {"cnpj": "123"})], nome="pix_recebidos_cnpj.json")
    escrever_pix_recebidos(
        pasta, [_pago(_txid(emitidas["NF 2"]), "3", {"cnpj": "10200300000140", "apelido": "x"})], nome="pix_recebidos_campo.json"
    )
    linhas = linhas_do_retorno_cnab([MovimentoCnab(_nosso_numero(emitidas["NF 2"]), 100000, 100000, pagador_cnpj="1020030000014X")])
    escrever_linhas(pasta, linhas, "retorno_cnab_pagador.ret")

    resultado = _conciliar(pasta, armazenamento)

    recusados = {recusado.nome: recusado.motivo for recusado in resultado.arquivos_recusados}
    assert sorted(recusados) == ["pix_recebidos_campo.json", "pix_recebidos_cnpj.json", "retorno_cnab_pagador.ret"]
    assert "pagador" in recusados["pix_recebidos_cnpj.json"]
    assert "apelido" in recusados["pix_recebidos_campo.json"]
    assert "pagador" in recusados["retorno_cnab_pagador.ret"]
    assert _identificados_na_lista(resultado) == {"PIX RECEBIDO FULANO": ["NF 1"]}


def test_retornos_na_pasta_nao_mudam_a_data_de_referencia_nem_a_conferencia_de_soma(tmp_path: Path) -> None:
    resultados = []
    for com_retornos in (False, True):
        pasta = tmp_path / f"entrada_{com_retornos}"
        pasta.mkdir()
        armazenamento = Armazenamento(tmp_path / f"estado_{com_retornos}.sqlite")
        emitidas = _emitir(pasta, armazenamento)
        escrever_extrato_itau(
            pasta,
            [
                REFERENCIA,
                LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00"),
                LinhaItau("07/03/2025", "PIX RECEBIDO BELTRANO", "1.000,00"),
            ],
        )
        if com_retornos:
            escrever_pix_recebidos(
                pasta,
                [
                    _pago(_txid(emitidas["NF 1"]), "1"),
                    pix_recebido(_txid(emitidas["NF 2"]), "1000.00", horario="2025-03-20T10:00:00Z", fim_do_e2e="2"),
                ],
            )
            escrever_retorno_cnab(
                pasta,
                [MovimentoCnab(_nosso_numero(emitidas["NF 2"]), 100000, 100000, ocorrencia="25032025", credito="25032025")],
            )
        resultados.append(_conciliar(pasta, armazenamento))

    sem, com = resultados
    assert com.resumo.data_de_referencia == sem.resumo.data_de_referencia
    assert com.resumo.data_de_referencia.data == date(2025, 3, 7)
    assert sum(t.quantidade for t in com.resumo.totais.values()) == sum(t.quantidade for t in sem.resumo.totais.values())
    assert sum(t.valor_centavos for t in com.resumo.totais.values()) == sum(
        t.valor_centavos for t in sem.resumo.totais.values()
    )
    assert len(com.resumo.retornos_sem_credito) == 2


def test_retorno_de_credito_ja_encerrado_pela_analista_e_ligado_sem_mudar_a_decisao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento)
    escrever_extrato_itau(pasta, [REFERENCIA, LinhaItau("06/03/2025", "PIX RECEBIDO FULANO", "1.000,00")])
    [credito] = [item for item in _conciliar(pasta, armazenamento).fila_de_excecoes if item.lancamento.valor_centavos == 100000]
    registrar_decisao_da_tela(
        armazenamento,
        LinhaDeDecisao(
            ABA_DA_FILA_DE_EXCECOES,
            credito.identificador,
            "conciliado fora",
            franqueado=FRANQUEADO_DOS_TITULOS,
            referencia="acordo 1",
        ),
        "analista",
        datetime(2025, 3, 7, 9, 0),
    )
    _conciliar(pasta, armazenamento)
    escrever_pix_recebidos(pasta, [_pago(_txid(emitidas["NF 1"]), "1")])

    depois = _conciliar(pasta, armazenamento)

    assert depois.resumo.retornos_sem_credito == ()
    assert credito.lancamento.chave_natural in armazenamento.retornos_dos_creditos()
    assert all(item.lancamento != credito.lancamento for item in depois.itens)
    assert armazenamento.classificados_como(TipoDeDecisao.CONCILIADO_FORA).keys() == {credito.lancamento.chave_natural}
