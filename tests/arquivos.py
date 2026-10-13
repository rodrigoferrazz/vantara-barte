from dataclasses import dataclass
from pathlib import Path

from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.encargo import ParametrosDeEncargo

CABECALHO_PROTHEUS = "cliente;cnpj;unidade;documento;nosso_numero;tipo;emissao;vencimento;valor;status"
CABECALHO_ITAU = "data;historico;documento;valor;tipo"
CABECALHO_OMIE = "customer_name,tax_id,invoice_ref,due_date,amount,paid_flag"


@dataclass(frozen=True)
class TituloProtheus:
    documento: str
    valor: str
    nosso_numero: str = ""
    cliente: str = "Franquia Teste Ltda"
    cnpj: str = "10.200.300/0001-40"
    vencimento: str = "05/03/2025"

    def linha(self) -> str:
        return ";".join(
            [
                self.cliente,
                self.cnpj,
                "Unidade X",
                self.documento,
                self.nosso_numero,
                "Produto",
                "20/02/2025",
                self.vencimento,
                self.valor,
                "Aberto",
            ]
        )


@dataclass(frozen=True)
class TituloOmie:
    documento: str
    valor: str
    cliente: str = "FRANQUIA TESTE NORTE LTDA"
    cnpj: str = "10200300000140"
    vencimento: str = "2025-03-05"
    pago: str = "N"

    def linha(self) -> str:
        return ",".join([self.cliente, self.cnpj, self.documento, self.vencimento, self.valor, self.pago])


@dataclass(frozen=True)
class LinhaItau:
    data: str
    historico: str
    valor: str
    tipo: str = "C"
    documento: str = ""

    def linha(self) -> str:
        return ";".join([self.data, self.historico, self.documento, self.valor, self.tipo])


def escrever_protheus(pasta: Path, titulos: list[TituloProtheus], nome: str = "receber_protheus.csv") -> Path:
    caminho = pasta / nome
    caminho.write_text("\n".join([CABECALHO_PROTHEUS, *(t.linha() for t in titulos)]) + "\n", encoding="utf-8")
    return caminho


def escrever_omie(pasta: Path, titulos: list[TituloOmie], nome: str = "titulos_omie.csv") -> Path:
    caminho = pasta / nome
    caminho.write_text("\n".join([CABECALHO_OMIE, *(t.linha() for t in titulos)]) + "\n", encoding="utf-8")
    return caminho


def escrever_extrato_itau(pasta: Path, linhas: list[LinhaItau], nome: str = "itau_cobranca.csv") -> Path:
    caminho = pasta / nome
    caminho.write_text("\n".join([CABECALHO_ITAU, *(l.linha() for l in linhas)]) + "\n", encoding="utf-8")
    return caminho


def configuracao_itau(
    padrao: str = "itau_cobranca*.csv",
    conta: str = "1234-5",
    encargo: ParametrosDeEncargo = ParametrosDeEncargo(),
    limite_de_combinacoes: int = Configuracao.limite_de_combinacoes,
) -> Configuracao:
    return Configuracao(
        contas=(ContaDeExtrato(padrao=padrao, banco="itau", conta=conta),),
        encargo=encargo,
        limite_de_combinacoes=limite_de_combinacoes,
    )
