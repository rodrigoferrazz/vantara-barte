import json
from dataclasses import dataclass, replace
from pathlib import Path

from conciliacao.configuracao import Configuracao, ConfiguracaoDeMigracao, ContaDeExtrato, FaixaDeNossoNumero
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


def configuracao_com_boleto(
    inicial: str = "0000700001", final: str = "0000700999", migrados: tuple[str, ...] = (FRANQUEADO_DOS_TITULOS,)
) -> Configuracao:
    base = configuracao_com_migracao(migrados)
    assert base.migracao is not None
    return replace(
        base,
        contas=(*base.contas, ContaDeExtrato(padrao="retorno_cnab*.ret", banco="itau", conta="1234-5")),
        migracao=replace(base.migracao, boleto=FaixaDeNossoNumero(banco="itau", conta="1234-5", inicial=inicial, final=final)),
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


@dataclass(frozen=True)
class MovimentoCnab:
    nosso_numero: str
    valor_nominal: int
    valor_pago: int
    acrescimos: int = 0
    movimento: str = "06"
    ocorrencia: str = "12032025"
    credito: str = "12032025"
    vencimento: str = "10032025"
    pagador_cnpj: str = "10200300000140"
    pagador_nome: str = "FRANQUIA TESTE LTDA"


def _registro(*campos: tuple[int, int, str | int]) -> str:
    linha = [" "] * 240
    for inicio, fim, valor in campos:
        tamanho = fim - inicio + 1
        texto = f"{valor:0{tamanho}d}" if isinstance(valor, int) else valor.ljust(tamanho)
        assert len(texto) == tamanho, (inicio, fim, valor)
        linha[inicio - 1 : fim] = texto
    return "".join(linha)


def linhas_do_retorno_cnab(movimentos: list[MovimentoCnab], banco: str = "341") -> list[str]:
    detalhes = []
    for numero, movimento in enumerate(movimentos):
        detalhes.append(
            _registro(
                (1, 3, banco), (4, 7, 1), (8, 8, "3"), (9, 13, 2 * numero + 1), (14, 14, "T"),
                (16, 17, movimento.movimento), (38, 57, movimento.nosso_numero), (74, 81, movimento.vencimento),
                (82, 96, movimento.valor_nominal), (133, 133, "2"), (134, 148, f"{movimento.pagador_cnpj:0>15}"),
                (149, 188, movimento.pagador_nome),
            )
        )
        detalhes.append(
            _registro(
                (1, 3, banco), (4, 7, 1), (8, 8, "3"), (9, 13, 2 * numero + 2), (14, 14, "U"),
                (16, 17, movimento.movimento), (18, 32, movimento.acrescimos), (33, 47, 0), (48, 62, 0), (63, 77, 0),
                (78, 92, movimento.valor_pago), (93, 107, movimento.valor_pago), (138, 145, movimento.ocorrencia),
                (146, 153, movimento.credito),
            )
        )
    return [
        _registro(
            (1, 3, banco), (4, 7, "0000"), (8, 8, "0"), (18, 18, "2"), (19, 32, "11222333000144"),
            (73, 102, "VANTARA FRANQUIAS"), (103, 132, "BANCO ITAU SA"), (143, 143, "2"), (144, 151, "14032025"),
            (158, 163, 1), (164, 166, "103"),
        ),
        _registro(
            (1, 3, banco), (4, 7, 1), (8, 8, "1"), (9, 9, "T"), (10, 11, "01"), (14, 16, "060"), (18, 18, "2"),
            (19, 33, "011222333000144"), (74, 103, "VANTARA FRANQUIAS"), (192, 199, "14032025"),
        ),
        *detalhes,
        _registro((1, 3, banco), (4, 7, 1), (8, 8, "5"), (18, 23, len(detalhes) + 2)),
        _registro((1, 3, banco), (4, 7, "9999"), (8, 8, "9"), (18, 23, 1), (24, 29, len(detalhes) + 4)),
    ]


def escrever_retorno_cnab(
    pasta: Path, movimentos: list[MovimentoCnab], nome: str = "retorno_cnab.ret", banco: str = "341"
) -> Path:
    return escrever_linhas(pasta, linhas_do_retorno_cnab(movimentos, banco), nome)


def escrever_linhas(pasta: Path, linhas: list[str], nome: str) -> Path:
    caminho = pasta / nome
    caminho.write_text("\r\n".join(linhas) + "\r\n", encoding="utf-8")
    return caminho
