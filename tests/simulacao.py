from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from conciliacao.armazenamento import Armazenamento
from conciliacao.configuracao import Configuracao, ConfiguracaoDeMigracao, ContaDeExtrato, FaixaDeNossoNumero
from conciliacao.dominio import Resultado
from conciliacao.emissao import emitir_cobrancas
from conciliacao.encargo import ParametrosDeEncargo
from conciliacao.execucao import executar_conciliacao
from conciliacao.gerador import ConfiguracaoDoGerador, DadosSinteticos, Proporcoes, gerar_dados_sinteticos
from conciliacao.porta import PortaSimulada
from conciliacao.simulador import (
    ConfiguracaoDoSimulador,
    PlanoDePagamentos,
    ProporcoesDoSimulador,
    plano_por_proporcoes,
)
from tests.arquivos import CABECALHO_ITAU, LinhaItau
from tests.parecerista import PareceristaFalso

SEMENTE_DO_GERADOR = 20260801
INICIO = date(2026, 8, 1)
_REFERENCIA = LinhaItau("31/07/2026", "TARIFA MANUTENCAO CONTA", "9,90", tipo="D")


@dataclass
class Simulacao:
    pasta: Path
    armazenamento: Armazenamento
    configuracao: Configuracao
    porta: PortaSimulada
    plano: PlanoDePagamentos
    simulados: list[Path]
    dados: DadosSinteticos

    def conciliar(self) -> Resultado:
        nomes = {
            raiz: {titulo.nome_do_franqueado for titulo in self.armazenamento.ultima_fotografia() if titulo.franqueado == raiz}
            for raiz in {esperado.pagador for esperado in self.plano.gabarito}
        }
        parecerista = PareceristaFalso(
            sim_para=(
                (esperado.nome_no_extrato, nome)
                for esperado in self.plano.gabarito
                if esperado.nome_no_extrato
                for nome in nomes[esperado.pagador]
            )
        )
        return executar_conciliacao(self.pasta, self.armazenamento, self.configuracao, parecerista)


def configuracao_da_simulacao(dados: DadosSinteticos, encargo: ParametrosDeEncargo) -> Configuracao:
    principal = dados.contas[0]
    return Configuracao(
        contas=(
            *dados.contas,
            ContaDeExtrato(padrao="*pix_recebidos*.json", banco=principal.banco, conta=principal.conta),
            ContaDeExtrato(padrao="*retorno_cnab*.ret", banco=principal.banco, conta=principal.conta),
        ),
        encargo=encargo,
        migracao=ConfiguracaoDeMigracao(
            franqueados=frozenset(dados.nomes_dos_franqueados),
            boleto=FaixaDeNossoNumero(banco=principal.banco, conta=principal.conta, inicial="0000700001", final="0000799999"),
        ),
    )


def simular(
    raiz: Path,
    semente: int,
    proporcoes: ProporcoesDoSimulador = ProporcoesDoSimulador(),
    titulos: int = 300,
    franqueados: int = 40,
    encargo: ParametrosDeEncargo = ParametrosDeEncargo(),
) -> Simulacao:
    pasta = raiz / "entrada"
    pasta.mkdir(parents=True)
    dados = gerar_dados_sinteticos(
        ConfiguracaoDoGerador(
            semente=SEMENTE_DO_GERADOR,
            titulos=titulos,
            franqueados=franqueados,
            proporcoes=replace(Proporcoes(), duplicidade_entre_sistemas=0),
        )
    )
    for nome, conteudo in dados.arquivos.items():
        if not nome.startswith("extrato_"):
            (pasta / nome).write_text(conteudo, encoding="utf-8")
    for conta in dados.contas:
        (pasta / f"extrato_itau_{conta.conta}_referencia.csv").write_text(
            f"{CABECALHO_ITAU}\n{_REFERENCIA.linha()}\n", encoding="utf-8"
        )
    configuracao = configuracao_da_simulacao(dados, encargo)
    armazenamento = Armazenamento(raiz / "estado.sqlite")
    executar_conciliacao(pasta, armazenamento, configuracao, PareceristaFalso())
    porta = PortaSimulada(configuracao.encargo)
    emitir_cobrancas(armazenamento, configuracao, porta)
    plano = plano_por_proporcoes(
        porta.emitidas,
        armazenamento.ultima_fotografia(),
        configuracao,
        ConfiguracaoDoSimulador(semente=semente, inicio=INICIO, proporcoes=proporcoes),
    )
    for pagamento in plano.pagamentos_de_cobranca:
        porta.pagar(pagamento)
    simulados = []
    for conta in dados.contas:
        extrato = pasta / f"extrato_itau_{conta.conta}_simulado.csv"
        extrato.write_text(plano.extrato(conta.conta), encoding="utf-8")
        simulados.append(extrato)
    simulados += porta.trazer_retornos(pasta, INICIO, plano.ultimo_dia)
    return Simulacao(pasta, armazenamento, configuracao, porta, plano, simulados, dados)
