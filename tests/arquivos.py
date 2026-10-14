import json
from dataclasses import dataclass, replace
from pathlib import Path

from conciliacao.configuracao import Configuracao, ConfiguracaoDeMigracao, ContaDeExtrato
from conciliacao.encargo import ParametrosDeEncargo

CABECALHO_PROTHEUS = "cliente;cnpj;unidade;documento;nosso_numero;tipo;emissao;vencimento;valor;status"
CABECALHO_ITAU = "data;historico;documento;valor;tipo"
CABECALHO_OMIE = "customer_name,tax_id,invoice_ref,due_date,amount,paid_flag"
FRANQUEADO_DOS_TITULOS = "10200300"


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


def configuracao_com_migracao(
    migrados: tuple[str, ...] | None = (FRANQUEADO_DOS_TITULOS,), conta_do_pix: str = "1234-5"
) -> Configuracao:
    base = configuracao_itau()
    return replace(
        base,
        contas=(*base.contas, ContaDeExtrato(padrao="pix_recebidos*.json", banco="itau", conta=conta_do_pix)),
        migracao=None if migrados is None else ConfiguracaoDeMigracao(frozenset(migrados)),
    )


def pix_recebido(
    txid: str | None,
    valor: str,
    horario: str = "2025-03-05T14:30:00.000Z",
    fim_do_e2e: str = "1",
    componentes: dict[str, object] | None = None,
) -> dict[str, object]:
    recebido: dict[str, object] = {
        "endToEndId": f"E00000000202503051430{fim_do_e2e:0>11}",
        "valor": valor,
        "horario": horario,
        "chave": "chave-pix-do-recebedor",
        "infoPagador": "pagamento",
    }
    if txid is not None:
        recebido["txid"] = txid
    if componentes is not None:
        recebido["componentesValor"] = componentes
    return recebido


def escrever_pix_recebidos(pasta: Path, recebidos: list[dict[str, object]], nome: str = "pix_recebidos.json") -> Path:
    caminho = pasta / nome
    conteudo = {
        "parametros": {
            "inicio": "2025-03-01T00:00:00Z",
            "fim": "2025-03-31T23:59:59Z",
            "paginacao": {
                "paginaAtual": 0,
                "itensPorPagina": 100,
                "quantidadeDePaginas": 1,
                "quantidadeTotalDeItens": len(recebidos),
            },
        },
        "pix": recebidos,
    }
    caminho.write_text(json.dumps(conteudo), encoding="utf-8")
    return caminho
