import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao
from conciliacao.dominio import Destino, Item, MotivoDeNaoIdentificacao, Resultado
from conciliacao.execucao import executar_conciliacao
from conciliacao.gerador import (
    Caso,
    ConfiguracaoDoGerador,
    DadosSinteticos,
    LancamentoEsperado,
    ConfiguracaoDoGeradorInvalida,
    Proporcoes,
    gerar_dados_sinteticos,
)
from tests.parecerista import PareceristaFalso

SEMENTE = 20260801
SEGUNDOS_ACEITAVEIS = 60


def _pequena(semente: int = SEMENTE, proporcoes: Proporcoes = Proporcoes()) -> ConfiguracaoDoGerador:
    return ConfiguracaoDoGerador(semente=semente, titulos=300, franqueados=40, proporcoes=proporcoes)


def _ia_que_reconhece_os_nomes_verdadeiros(dados: DadosSinteticos) -> PareceristaFalso:
    return PareceristaFalso(
        sim_para=(
            (esperado.nome_no_extrato, nome)
            for esperado in dados.gabarito
            if esperado.pagador and esperado.nome_no_extrato
            for nome in dados.nomes_dos_franqueados[esperado.pagador]
        )
    )


def _executar(dados: DadosSinteticos, pasta: Path, armazenamento: Armazenamento) -> Resultado:
    dados.escrever(pasta)
    return executar_conciliacao(
        pasta, armazenamento, Configuracao(contas=dados.contas), _ia_que_reconhece_os_nomes_verdadeiros(dados)
    )


def _chave(item: Item) -> tuple[str, object, str, int]:
    lancamento = item.lancamento
    return (lancamento.conta, lancamento.data, lancamento.historico, lancamento.valor_centavos)


def _gabarito_por_chave(dados: DadosSinteticos) -> dict[tuple[str, object, str, int], LancamentoEsperado]:
    return {(e.conta, e.data, e.historico, e.valor_centavos): e for e in dados.gabarito}


def _titulos(item: Item) -> frozenset[tuple[str, str]]:
    return frozenset((titulo.sistema_de_origem, titulo.documento) for titulo in item.titulos)


def test_mesma_semente_gera_exatamente_os_mesmos_arquivos(tmp_path: Path) -> None:
    primeira, segunda, outra = tmp_path / "primeira", tmp_path / "segunda", tmp_path / "outra"
    gerar_dados_sinteticos(_pequena()).escrever(primeira)
    gerar_dados_sinteticos(_pequena()).escrever(segunda)
    gerar_dados_sinteticos(_pequena(semente=SEMENTE + 1)).escrever(outra)

    conteudo = {arquivo.name: arquivo.read_bytes() for arquivo in sorted(primeira.iterdir())}
    assert conteudo == {arquivo.name: arquivo.read_bytes() for arquivo in sorted(segunda.iterdir())}
    assert conteudo != {arquivo.name: arquivo.read_bytes() for arquivo in sorted(outra.iterdir())}


def test_arquivos_gerados_sao_aceitos_pelos_adaptadores_sem_ajuste(pasta: Path, armazenamento: Armazenamento) -> None:
    dados = gerar_dados_sinteticos(_pequena())

    resultado = _executar(dados, pasta, armazenamento)

    assert resultado.arquivos_recusados == ()
    assert sorted(resultado.resumo.arquivos_lidos) == sorted(arquivo.name for arquivo in pasta.iterdir())
    assert len(resultado.resumo.arquivos_lidos) == 2 + len(dados.contas) == 6
    assert len(resultado.itens) == len(dados.gabarito)


def test_extratos_de_quatro_contas_e_exportacoes_dos_dois_sistemas(tmp_path: Path) -> None:
    dados = gerar_dados_sinteticos(_pequena())

    assert len({conta.conta for conta in dados.contas}) == 4
    assert {e.conta for e in dados.gabarito} == {conta.conta for conta in dados.contas}
    sistemas = {sistema for esperado in dados.gabarito for sistema, _ in esperado.titulos}
    assert sistemas == {"Protheus", "Omie"}


def test_cada_proporcao_vira_a_quantidade_de_casos_no_gabarito() -> None:
    proporcoes = Proporcoes(
        nome_truncado=0.05,
        nome_abreviado=0.03,
        nome_invertido=0.02,
        cnpj_no_historico=0.06,
        soma_de_titulos=0.02,
        parcial=0.03,
        multa=0.04,
        encargo_nao_pago=0.05,
        deposito_sem_nome=0.02,
        antecipacao=0.01,
        debitos=0.04,
        duplicidade_entre_sistemas=0.02,
    )

    dados = gerar_dados_sinteticos(_pequena(proporcoes=proporcoes))

    casos = Counter(esperado.caso for esperado in dados.gabarito)
    assert casos[Caso.NOME_TRUNCADO] == 15
    assert casos[Caso.NOME_ABREVIADO] == 9
    assert casos[Caso.NOME_INVERTIDO] == 6
    assert casos[Caso.SOMA_DE_TITULOS] == 6
    assert casos[Caso.PARCIAL] == 9
    assert casos[Caso.MULTA] == 12
    assert casos[Caso.ENCARGO_NAO_PAGO] == 15
    assert casos[Caso.DEPOSITO_SEM_NOME] == 6
    assert casos[Caso.ANTECIPACAO] == 3
    assert casos[Caso.DEBITO] == 12
    assert casos[Caso.CNPJ_NO_HISTORICO] >= 18
    assert len(dados.duplicidades) == 6


def test_proporcao_zerada_nao_gera_o_caso() -> None:
    dados = gerar_dados_sinteticos(_pequena(proporcoes=Proporcoes(nome_abreviado=0, antecipacao=0, debitos=0)))

    casos = Counter(esperado.caso for esperado in dados.gabarito)
    assert casos[Caso.NOME_ABREVIADO] == casos[Caso.ANTECIPACAO] == casos[Caso.DEBITO] == 0


@pytest.mark.parametrize(
    "proporcoes",
    [Proporcoes(multa=-0.1), Proporcoes(nome_truncado=0.6, cnpj_no_historico=0.6)],
    ids=["negativa", "soma acima de 1"],
)
def test_proporcoes_invalidas_sao_recusadas(proporcoes: Proporcoes) -> None:
    with pytest.raises(ConfiguracaoDoGeradorInvalida):
        gerar_dados_sinteticos(_pequena(proporcoes=proporcoes))


def test_gabarito_traz_destino_titulos_e_motivo_de_cada_lancamento() -> None:
    dados = gerar_dados_sinteticos(_pequena())

    por_caso = {esperado.caso: esperado for esperado in dados.gabarito}
    assert set(por_caso) == set(Caso)
    for esperado in dados.gabarito:
        if esperado.destino is Destino.FILA_DE_EXCECOES:
            assert esperado.motivo is not None
        else:
            assert esperado.motivo is None
    assert por_caso[Caso.SOMA_DE_TITULOS].destino is Destino.LISTA_DE_BAIXA
    assert len(por_caso[Caso.SOMA_DE_TITULOS].titulos) >= 2
    assert por_caso[Caso.NOME_TRUNCADO].motivo is MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ
    assert por_caso[Caso.DEPOSITO_SEM_NOME].motivo is MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR
    assert por_caso[Caso.ANTECIPACAO].titulos == frozenset()
    assert por_caso[Caso.DEBITO].destino is Destino.FORA_DO_ESCOPO


@dataclass(frozen=True)
class Volume:
    dados: DadosSinteticos
    resultado: Resultado
    segundos: float


@pytest.fixture(scope="module")
def volume(tmp_path_factory: pytest.TempPathFactory) -> Volume:
    raiz = tmp_path_factory.mktemp("volume")
    pasta = raiz / "entrada"
    inicio = time.perf_counter()
    dados = gerar_dados_sinteticos(ConfiguracaoDoGerador(semente=SEMENTE))
    armazenamento = Armazenamento(raiz / "estado.sqlite")
    try:
        resultado = _executar(dados, pasta, armazenamento)
    finally:
        armazenamento.fechar()
    return Volume(dados, resultado, time.perf_counter() - inicio)


def test_volume_tem_cerca_de_1900_titulos_de_210_franqueados(volume: Volume) -> None:
    titulos = {titulo for esperado in volume.dados.gabarito for titulo in esperado.titulos}
    assert len(volume.dados.nomes_dos_franqueados) == 210
    assert len(titulos) > 1_500
    assert volume.resultado.resumo.arquivos_recusados == ()


def test_volume_nenhum_item_da_lista_de_baixa_diverge_do_gabarito(volume: Volume) -> None:
    gabarito = _gabarito_por_chave(volume.dados)

    divergentes = [
        (item.lancamento.historico, item.explicacao)
        for item in volume.resultado.lista_de_baixa
        if gabarito[_chave(item)].destino is not Destino.LISTA_DE_BAIXA or _titulos(item) != gabarito[_chave(item)].titulos
    ]

    assert divergentes == []
    assert len(volume.resultado.lista_de_baixa) > 1_000


def test_volume_conferencia_de_soma_fecha_e_todo_item_da_fila_tem_um_unico_motivo(volume: Volume) -> None:
    resultado = volume.resultado
    totais = resultado.resumo.totais
    assert sum(t.valor_centavos for t in totais.values()) == sum(e.valor_centavos for e in volume.dados.gabarito)
    assert sum(t.quantidade for t in totais.values()) == len(volume.dados.gabarito)
    assert resultado.fila_de_excecoes
    assert all(isinstance(item.motivo, MotivoDeNaoIdentificacao) for item in resultado.fila_de_excecoes)
    assert all(isinstance(item.motivo, MotivoDeNaoIdentificacao) for item in resultado.itens_de_titulo)


def test_volume_destino_e_motivo_de_cada_lancamento_seguem_o_gabarito(volume: Volume) -> None:
    gabarito = _gabarito_por_chave(volume.dados)

    divergentes = Counter(
        (gabarito[_chave(item)].caso, gabarito[_chave(item)].motivo, item.motivo)
        for item in volume.resultado.itens
        if (item.destino, item.motivo) != (gabarito[_chave(item)].destino, gabarito[_chave(item)].motivo)
    )

    assert divergentes == Counter()
    assert {frozenset((t.sistema_de_origem, t.documento) for t in item.titulos) for item in volume.resultado.itens_de_titulo} == set(
        volume.dados.duplicidades
    )


def test_volume_termina_em_tempo_aceitavel_com_a_ia_falsa(volume: Volume) -> None:
    assert volume.segundos < SEGUNDOS_ACEITAVEIS
