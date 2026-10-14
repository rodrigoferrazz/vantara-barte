from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao, ConfiguracaoInvalida, carregar_configuracao
from conciliacao.dominio import MotivoDeNaoIdentificacao, RegraDaProposta, Resultado, TipoDeEvidencia
from conciliacao.emissao import emitir_cobrancas
from conciliacao.encargo import ParametrosDeEncargo
from conciliacao.execucao import executar_conciliacao
from conciliacao.identificadores import FaixaDeNossoNumeroEsgotada
from conciliacao.porta import CobrancaIdentificada, PortaSimulada
from tests.arquivos import (
    LinhaItau,
    MovimentoCnab,
    TituloOmie,
    TituloProtheus,
    configuracao_com_boleto,
    configuracao_com_migracao,
    escrever_extrato_itau,
    escrever_linhas,
    escrever_omie,
    escrever_protheus,
    escrever_retorno_cnab,
    linhas_do_retorno_cnab,
)
from tests.parecerista import PareceristaFalso

REFERENCIA = LinhaItau("05/03/2025", "TARIFA MANUTENCAO CONTA", "9,90", tipo="D")


def _conciliar(pasta: Path, armazenamento: Armazenamento, configuracao: Configuracao | None = None) -> Resultado:
    return executar_conciliacao(pasta, armazenamento, configuracao or configuracao_com_boleto(), PareceristaFalso())


def _emitir(
    pasta: Path,
    armazenamento: Armazenamento,
    titulos: list[TituloProtheus],
    configuracao: Configuracao | None = None,
    omie: list[TituloOmie] | None = None,
) -> dict[str, CobrancaIdentificada]:
    configuracao = configuracao or configuracao_com_boleto()
    escrever_protheus(pasta, titulos)
    if omie is not None:
        escrever_omie(pasta, omie)
    escrever_extrato_itau(pasta, [REFERENCIA])
    _conciliar(pasta, armazenamento, configuracao)
    porta = PortaSimulada()
    emitir_cobrancas(armazenamento, configuracao, porta)
    return {cobranca.documento: cobranca for cobranca in porta.emitidas}


def _nosso_numero(cobranca: CobrancaIdentificada) -> str:
    assert cobranca.nosso_numero is not None
    return cobranca.nosso_numero


def _liquidado(pasta: Path, valor: str, documento: str = "", data: str = "12/03/2025") -> None:
    escrever_extrato_itau(pasta, [REFERENCIA, LinhaItau(data, "LIQUIDACAO COBRANCA SIMPLES", valor, documento=documento)])


def test_titulo_sem_nosso_numero_recebe_boleto_e_pix_e_o_com_nosso_numero_do_protheus_so_pix(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025", nosso_numero="000014000011"),
            TituloProtheus(documento="NF 2", valor="500,00", vencimento="10/03/2025"),
        ],
        omie=[TituloOmie(documento="FAT-1", valor="700.00", vencimento="2025-03-10")],
    )

    assert emitidas["NF 1"].nosso_numero is None
    assert emitidas["NF 1"].txid is not None
    assert [emitidas[documento].txid is not None for documento in ("NF 2", "FAT-1")] == [True, True]
    assert sorted(_nosso_numero(emitidas[documento]) for documento in ("NF 2", "FAT-1")) == ["0000700001", "0000700002"]


def test_nosso_numero_fica_na_faixa_e_nunca_e_reaproveitado_nem_duplicado(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    configuracao = configuracao_com_boleto(inicial="0000700001", final="0000700003")
    primeira = _emitir(
        pasta,
        armazenamento,
        [TituloProtheus(documento=f"NF {numero}", valor="100,00", vencimento="10/03/2025") for numero in (1, 2)],
        configuracao,
    )
    de_novo = PortaSimulada()
    emitir_cobrancas(armazenamento, configuracao, de_novo)
    escrever_protheus(pasta, [TituloProtheus(documento="NF 3", valor="100,00", vencimento="10/03/2025")])
    _conciliar(pasta, armazenamento, configuracao)
    terceira = PortaSimulada()
    emitir_cobrancas(armazenamento, configuracao, terceira)
    escrever_protheus(pasta, [TituloProtheus(documento="NF 4", valor="100,00", vencimento="10/03/2025")])
    _conciliar(pasta, armazenamento, configuracao)

    with pytest.raises(FaixaDeNossoNumeroEsgotada, match="0000700001 a 0000700003"):
        emitir_cobrancas(armazenamento, configuracao, PortaSimulada())

    assert sorted(_nosso_numero(c) for c in primeira.values()) == ["0000700001", "0000700002"]
    assert de_novo.emitidas == []
    assert [_nosso_numero(c) for c in terceira.emitidas] == ["0000700003"]


def test_faixa_configurada_depois_so_acrescenta_o_boleto_sem_reenviar_o_pix(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    so_pix = _emitir(pasta, armazenamento, [TituloProtheus(documento="NF 1", valor="100,00", vencimento="10/03/2025")], configuracao_com_migracao())
    boleto = PortaSimulada()
    emitir_cobrancas(armazenamento, configuracao_com_boleto(), boleto)

    assert so_pix["NF 1"].nosso_numero is None
    [so_o_boleto] = boleto.emitidas
    assert (so_o_boleto.documento, so_o_boleto.txid, so_o_boleto.nosso_numero) == ("NF 1", None, "0000700001")


def test_titulo_que_ganhou_nosso_numero_no_protheus_nao_recebe_boleto_da_plataforma(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    class _PortaFora(PortaSimulada):
        def emitir(self, cobranca: CobrancaIdentificada) -> None:
            raise ConnectionError("porta fora do ar")

    escrever_protheus(pasta, [TituloProtheus(documento="NF 1", valor="100,00", vencimento="10/03/2025")])
    escrever_extrato_itau(pasta, [REFERENCIA])
    _conciliar(pasta, armazenamento)
    with pytest.raises(ConnectionError):
        emitir_cobrancas(armazenamento, configuracao_com_boleto(), _PortaFora())
    escrever_protheus(pasta, [TituloProtheus(documento="NF 1", valor="100,00", vencimento="10/03/2025", nosso_numero="000014000099")])
    _conciliar(pasta, armazenamento)
    porta = PortaSimulada()

    emitir_cobrancas(armazenamento, configuracao_com_boleto(), porta)

    [so_o_pix] = porta.emitidas
    assert so_o_pix.nosso_numero is None
    assert so_o_pix.txid is not None


def test_boleto_da_plataforma_liquidado_com_nosso_numero_vai_para_a_lista_como_um_boleto_do_protheus(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025"),
            TituloProtheus(documento="NF 2", valor="1.000,00", vencimento="10/03/2025"),
        ],
    )
    nosso_numero = _nosso_numero(emitidas["NF 2"])
    _liquidado(pasta, "1.020,00", documento=nosso_numero)

    resultado = _conciliar(pasta, armazenamento)

    [item] = resultado.lista_de_baixa
    assert [titulo.documento for titulo in item.titulos] == ["NF 2"]
    assert item.evidencia == (TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA,)
    assert item.regra is RegraDaProposta.IDENTIFICADOR_E_VALOR
    assert f"nosso número {nosso_numero} (Identificador de cobrança de origem plataforma)" in item.explicacao
    assert "Encargo R$ 20,00" in item.explicacao
    assert resultado.fila_de_excecoes == []


def test_boleto_da_plataforma_com_valor_acima_do_encargo_vai_para_a_fila_com_valor_nao_fecha(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(pasta, armazenamento, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025")])
    _liquidado(pasta, "1.050,00", documento=_nosso_numero(emitidas["NF 1"]))

    resultado = _conciliar(pasta, armazenamento)

    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [titulo.documento for titulo in item.titulos] == ["NF 1"]
    assert "Valor a maior" in item.explicacao


def test_parcial_de_boleto_vai_para_a_fila_como_diferenca_a_menor_apontando_o_titulo(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    emitidas = _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="12/03/2025"),
            TituloProtheus(documento="NF 2", valor="400,00", vencimento="12/03/2025"),
        ],
    )
    nosso_numero = _nosso_numero(emitidas["NF 1"])
    _liquidado(pasta, "400,00")
    escrever_retorno_cnab(pasta, [MovimentoCnab(nosso_numero, valor_nominal=100000, valor_pago=40000)])

    resultado = _conciliar(pasta, armazenamento)

    [item] = resultado.fila_de_excecoes
    assert item.motivo is MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
    assert [titulo.documento for titulo in item.titulos] == ["NF 1"]
    assert item.evidencia == (TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA,)
    assert "Diferença a menor" in item.explicacao
    assert resultado.lista_de_baixa == []


def test_atraso_com_acrescimos_do_segmento_u_aparece_separado_na_explicacao(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    configuracao = replace(configuracao_com_boleto(), encargo=ParametrosDeEncargo(juros_ao_mes_percentual=Decimal("1")))
    emitidas = _emitir(
        pasta, armazenamento, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025")], configuracao
    )
    _liquidado(pasta, "1.020,67")
    escrever_retorno_cnab(
        pasta, [MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=102067, acrescimos=2067)]
    )

    resultado = _conciliar(pasta, armazenamento, configuracao)

    [item] = resultado.lista_de_baixa
    assert [titulo.documento for titulo in item.titulos] == ["NF 1"]
    assert (
        "O Retorno de cobrança separa principal R$ 1.000,00 e acréscimos (juros, multa e encargos) R$ 20,67"
        in item.explicacao
    )


def test_regra_de_nosso_numero_do_protheus_continua_igual_e_o_retorno_cnab_so_acrescenta_os_acrescimos(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="10/03/2025", nosso_numero="000014000011"),
            TituloProtheus(documento="NF 2", valor="1.000,00", vencimento="10/03/2025", nosso_numero="000014000012"),
        ],
    )
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("12/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.020,00", documento="000014000011"),
            LinhaItau("13/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.020,00"),
        ],
    )
    escrever_retorno_cnab(
        pasta,
        [
            MovimentoCnab(
                "000014000012", valor_nominal=100000, valor_pago=102000, acrescimos=2000, ocorrencia="13032025", credito="13032025"
            )
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    pelo_extrato, pelo_retorno = sorted(resultado.lista_de_baixa, key=lambda item: item.lancamento.data)
    for item, documento in ((pelo_extrato, "NF 1"), (pelo_retorno, "NF 2")):
        assert [titulo.documento for titulo in item.titulos] == [documento]
        assert item.evidencia == (TipoDeEvidencia.NOSSO_NUMERO,)
        assert item.regra is RegraDaProposta.NOSSO_NUMERO_E_VALOR
    assert pelo_extrato.explicacao.startswith("Nosso número 000014000011 é do Título NF 1 (Protheus)")
    assert "Retorno de cobrança" not in pelo_extrato.explicacao
    assert "acréscimos (juros, multa e encargos) R$ 20,00" in pelo_retorno.explicacao


def test_adaptador_cnab_so_transforma_liquidacao_em_retorno(pasta: Path, armazenamento: Armazenamento) -> None:
    emitidas = _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="12/03/2025"),
            TituloProtheus(documento="NF 2", valor="1.000,00", vencimento="12/03/2025"),
            TituloProtheus(documento="NF 3", valor="1.000,00", vencimento="12/03/2025"),
        ],
    )
    escrever_extrato_itau(
        pasta,
        [
            REFERENCIA,
            LinhaItau("12/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.000,00"),
            LinhaItau("12/03/2025", "PIX RECEBIDO FULANO", "700,00"),
            LinhaItau("13/03/2025", "LIQUIDACAO COBRANCA SIMPLES", "1.000,00"),
        ],
    )
    escrever_retorno_cnab(
        pasta,
        [
            MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=100000),
            MovimentoCnab(_nosso_numero(emitidas["NF 2"]), valor_nominal=100000, valor_pago=70000, movimento="02"),
            MovimentoCnab(_nosso_numero(emitidas["NF 2"]), valor_nominal=100000, valor_pago=70000, movimento="09"),
            MovimentoCnab(
                _nosso_numero(emitidas["NF 3"]), valor_nominal=100000, valor_pago=100000, movimento="17",
                ocorrencia="13032025", credito="13032025",
            ),
        ],
    )

    resultado = _conciliar(pasta, armazenamento)

    assert resultado.arquivos_recusados == ()
    assert sorted(titulo.documento for item in resultado.lista_de_baixa for titulo in item.titulos) == ["NF 1", "NF 3"]
    [pix] = resultado.fila_de_excecoes
    assert TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA not in pix.evidencia


def test_retorno_cnab_reimportado_nao_duplica(pasta: Path, armazenamento: Armazenamento) -> None:
    emitidas = _emitir(pasta, armazenamento, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="12/03/2025")])
    _liquidado(pasta, "1.000,00")
    movimento = MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=100000)
    escrever_retorno_cnab(pasta, [movimento])
    escrever_retorno_cnab(pasta, [movimento], nome="retorno_cnab_de_novo.ret")

    resultado = _conciliar(pasta, armazenamento)
    seguinte = _conciliar(pasta, armazenamento)

    for execucao in (resultado, seguinte):
        [item] = execucao.lista_de_baixa
        assert item.evidencia == (TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA,)


def _trocar(linha: str, inicio: int, texto: str) -> str:
    return linha[: inicio - 1] + texto + linha[inicio - 1 + len(texto) :]


def test_retorno_cnab_fora_do_layout_e_recusado_sozinho_com_o_motivo(pasta: Path, armazenamento: Armazenamento) -> None:
    emitidas = _emitir(pasta, armazenamento, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="12/03/2025")])
    _liquidado(pasta, "1.000,00")
    linhas = linhas_do_retorno_cnab([MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=100000)])
    escrever_retorno_cnab(pasta, [MovimentoCnab(_nosso_numero(emitidas["NF 1"]), valor_nominal=100000, valor_pago=100000)])
    escrever_linhas(pasta, [*linhas[:2], linhas[2][:-1], *linhas[3:]], "retorno_cnab_curto.ret")
    escrever_linhas(pasta, [_trocar(linhas[0], 143, "1"), *linhas[1:]], "retorno_cnab_remessa.ret")
    escrever_linhas(pasta, [*linhas[:3], *linhas[4:]], "retorno_cnab_sem_u.ret")
    escrever_linhas(pasta, [*linhas[:3], _trocar(linhas[3], 146, "31022025"), *linhas[4:]], "retorno_cnab_data.ret")
    escrever_linhas(pasta, linhas[:-1], "retorno_cnab_sem_trailer.ret")
    escrever_retorno_cnab(
        pasta, [MovimentoCnab("1", valor_nominal=1, valor_pago=1)], nome="retorno_cnab_bradesco.ret", banco="237"
    )
    escrever_retorno_cnab(pasta, [MovimentoCnab("1", valor_nominal=1, valor_pago=1)], nome="sem_conta.ret")

    resultado = _conciliar(pasta, armazenamento)

    recusados = {recusado.nome: recusado.motivo for recusado in resultado.arquivos_recusados}
    assert sorted(recusados) == [
        "retorno_cnab_bradesco.ret",
        "retorno_cnab_curto.ret",
        "retorno_cnab_data.ret",
        "retorno_cnab_remessa.ret",
        "retorno_cnab_sem_trailer.ret",
        "retorno_cnab_sem_u.ret",
        "sem_conta.ret",
    ]
    assert "linha 3" in recusados["retorno_cnab_curto.ret"] and "240" in recusados["retorno_cnab_curto.ret"]
    assert "retorno" in recusados["retorno_cnab_remessa.ret"]
    assert "Segmento U" in recusados["retorno_cnab_sem_u.ret"]
    assert "31022025" in recusados["retorno_cnab_data.ret"]
    assert "trailer de arquivo" in recusados["retorno_cnab_sem_trailer.ret"]
    assert "237" in recusados["retorno_cnab_bradesco.ret"]
    assert "conta" in recusados["sem_conta.ret"]
    [item] = resultado.lista_de_baixa
    assert item.evidencia == (TipoDeEvidencia.IDENTIFICADOR_DE_COBRANCA,)


def test_retorno_cnab_sem_configuracao_de_migracao_e_recusado(pasta: Path, armazenamento: Armazenamento) -> None:
    escrever_protheus(pasta, [TituloProtheus(documento="NF 1", valor="1.000,00", vencimento="12/03/2025")])
    _liquidado(pasta, "1.000,00")
    escrever_retorno_cnab(pasta, [MovimentoCnab("0000700001", valor_nominal=100000, valor_pago=100000)])
    sem_migracao = replace(configuracao_com_boleto(), migracao=None)

    resultado = _conciliar(pasta, armazenamento, sem_migracao)

    assert [recusado.nome for recusado in resultado.arquivos_recusados] == ["retorno_cnab.ret"]


def test_boleto_da_plataforma_tem_a_mesma_janela_de_compensacao_na_lista_de_cobranca(
    pasta: Path, armazenamento: Armazenamento
) -> None:
    _emitir(
        pasta,
        armazenamento,
        [
            TituloProtheus(documento="NF 1", valor="100,00", vencimento="06/03/2025"),
            TituloProtheus(documento="NF 9", valor="900,00", vencimento="06/03/2025", cnpj="20.300.400/0001-50"),
        ],
        omie=[TituloOmie(documento="FAT-1", valor="200.00", vencimento="2025-03-06")],
    )
    escrever_extrato_itau(pasta, [LinhaItau("07/03/2025", "TARIFA MANUTENCAO CONTA", "9,90", tipo="D")])

    resultado = _conciliar(pasta, armazenamento)

    assert resultado.resumo.data_de_referencia.data == date(2025, 3, 7)
    assert [na_cobranca.titulo.documento for na_cobranca in resultado.lista_de_cobranca] == ["NF 9"]


def _toml(caminho: Path, boleto: str) -> Path:
    caminho.write_text(
        '[[contas]]\npadrao = "itau*.csv"\nbanco = "itau"\nconta = "1234-5"\n\n'
        f'[migracao]\nfranqueados = ["10200300"]\n\n[migracao.boleto]\n{boleto}',
        encoding="utf-8",
    )
    return caminho


def test_configuracao_da_faixa_de_nosso_numero(tmp_path: Path) -> None:
    valida = 'banco = "itau"\nconta = "1234-5"\nnosso_numero_inicial = "0000700001"\nnosso_numero_final = "0000700999"\n'

    configuracao = carregar_configuracao(_toml(tmp_path / "valida.toml", valida))

    assert configuracao.migracao is not None and configuracao.migracao.boleto is not None
    assert (configuracao.migracao.boleto.inicial, configuracao.migracao.boleto.final) == ("0000700001", "0000700999")
    for nome, boleto, motivo in [
        ("conta", valida.replace('"1234-5"', '"9999-9"'), "conta"),
        ("tamanho", valida.replace('"0000700999"', '"700999"'), "mesmo número de dígitos"),
        ("ordem", valida.replace('"0000700001"', '"0000800001"'), "maior"),
        ("letras", valida.replace('"0000700001"', '"000070000A"'), "dígitos"),
        ("longo", valida.replace('"0000700001"', f'"{1:021d}"').replace('"0000700999"', f'"{9:021d}"'), "20"),
        ("campo", valida + "carteira = 1\n", "carteira"),
    ]:
        with pytest.raises(ConfiguracaoInvalida, match=motivo):
            carregar_configuracao(_toml(tmp_path / f"{nome}.toml", boleto))
