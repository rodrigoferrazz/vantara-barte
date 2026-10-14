import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from conciliacao.dominio import TipoDeIdentificador
from conciliacao.encargo import ParametrosDeEncargo, multa_e_juros

_CODIGOS_DOS_BANCOS = {"itau": "341"}
_ISPB_DO_RECEBEDOR = "60701190"
_TAMANHO_DO_REGISTRO = 240


@dataclass(frozen=True)
class CobrancaIdentificada:
    sistema_de_origem: str
    documento: str
    valor_centavos: int
    vencimento: date
    cnpj: str
    txid: str | None
    nosso_numero: str | None

    def identificador(self, tipo: TipoDeIdentificador) -> str | None:
        return self.txid if tipo is TipoDeIdentificador.TXID else self.nosso_numero


@dataclass(frozen=True)
class PagamentoDeCobranca:
    cobranca: CobrancaIdentificada
    tipo: TipoDeIdentificador
    banco: str
    data: date
    valor_centavos: int
    multa_centavos: int
    juros_centavos: int
    documento_do_pagador: str
    nome_do_pagador: str

    @property
    def principal_centavos(self) -> int:
        return self.valor_centavos - self.multa_centavos - self.juros_centavos


class PagamentoInvalido(ValueError):
    pass


class PortaDeCobranca(Protocol):
    def emitir(self, cobranca: CobrancaIdentificada) -> None: ...

    def trazer_retornos(self, pasta: Path, inicio: date, fim: date) -> list[Path]: ...


def arquivo_de_pix_recebidos(inicio: date, fim: date) -> str:
    return f"pix_recebidos_{inicio:%Y%m%d}_{fim:%Y%m%d}.json"


def arquivo_de_retorno_cnab(banco: str, inicio: date, fim: date) -> str:
    return f"retorno_cnab_{_codigo_do_banco(banco)}_{inicio:%Y%m%d}_{fim:%Y%m%d}.ret"


class PortaSimulada:
    def __init__(self, encargo: ParametrosDeEncargo = ParametrosDeEncargo()) -> None:
        self.encargo = encargo
        self.emitidas: list[CobrancaIdentificada] = []
        self._por_identificador: dict[tuple[TipoDeIdentificador, str], CobrancaIdentificada] = {}
        self._pagamentos: list[PagamentoDeCobranca] = []
        self._pagos: set[tuple[TipoDeIdentificador, str]] = set()

    def emitir(self, cobranca: CobrancaIdentificada) -> None:
        chaves = [(tipo, identificador) for tipo in TipoDeIdentificador if (identificador := cobranca.identificador(tipo))]
        if not chaves:
            raise ValueError(f"cobrança do Título {cobranca.documento} sem Identificador de cobrança")
        anteriores = {self._por_identificador[chave] for chave in chaves if chave in self._por_identificador}
        if anteriores == {cobranca}:
            return
        if anteriores:
            raise ValueError(f"Identificador de cobrança do Título {cobranca.documento} já usado em outra cobrança")
        self.emitidas.append(cobranca)
        self._por_identificador.update(dict.fromkeys(chaves, cobranca))

    def _multa_e_juros(self, cobranca: CobrancaIdentificada, data: date) -> tuple[int, int]:
        return multa_e_juros(cobranca.valor_centavos, cobranca.vencimento, data, self.encargo)

    def pagar(self, pagamento: PagamentoDeCobranca) -> None:
        cobranca, tipo = pagamento.cobranca, pagamento.tipo
        identificador = cobranca.identificador(tipo)
        if identificador is None or self._por_identificador.get((tipo, identificador)) != cobranca:
            raise PagamentoInvalido(f"{tipo} do Título {cobranca.documento} não foi emitido por esta porta")
        multa, juros = self._multa_e_juros(cobranca, pagamento.data)
        if tipo is TipoDeIdentificador.TXID:
            if (pagamento.principal_centavos, pagamento.multa_centavos, pagamento.juros_centavos) != (
                cobranca.valor_centavos,
                multa,
                juros,
            ):
                raise PagamentoInvalido(f"Pix com txid {identificador} só é pago pelo valor da cobrança na data")
        elif pagamento.valor_centavos > cobranca.valor_centavos + multa + juros or (
            pagamento.multa_centavos + pagamento.juros_centavos != max(pagamento.valor_centavos - cobranca.valor_centavos, 0)
        ):
            raise PagamentoInvalido(f"boleto {identificador} pago acima do valor com Encargo ou com acréscimos errados")
        if (tipo, identificador) in self._pagos:
            raise PagamentoInvalido(f"{tipo} {identificador} já foi pago")
        self._pagamentos.append(pagamento)
        self._pagos.add((tipo, identificador))

    def trazer_retornos(self, pasta: Path, inicio: date, fim: date) -> list[Path]:
        no_periodo = sorted(
            ((sequencial, p) for sequencial, p in enumerate(self._pagamentos, start=1) if inicio <= p.data <= fim),
            key=lambda par: (par[1].data, par[0]),
        )
        trazidos = []
        pix = [par for par in no_periodo if par[1].tipo is TipoDeIdentificador.TXID]
        if pix:
            caminho = pasta / arquivo_de_pix_recebidos(inicio, fim)
            caminho.write_text(_pix_recebidos(pix, inicio, fim), encoding="utf-8")
            trazidos.append(caminho)
        boletos = [p for _, p in no_periodo if p.tipo is TipoDeIdentificador.NOSSO_NUMERO]
        for banco in sorted({p.banco for p in boletos}):
            caminho = pasta / arquivo_de_retorno_cnab(banco, inicio, fim)
            linhas = _retorno_cnab_240(banco, [p for p in boletos if p.banco == banco], fim)
            caminho.write_text("\r\n".join(linhas) + "\r\n", encoding="utf-8")
            trazidos.append(caminho)
        return trazidos


def _pix_recebidos(pagamentos: list[tuple[int, PagamentoDeCobranca]], inicio: date, fim: date) -> str:
    recebidos = []
    for sequencial, pagamento in pagamentos:
        componentes = {"original": {"valor": _reais(pagamento.principal_centavos)}}
        if pagamento.multa_centavos:
            componentes["multa"] = {"valor": _reais(pagamento.multa_centavos)}
        if pagamento.juros_centavos:
            componentes["juros"] = {"valor": _reais(pagamento.juros_centavos)}
        recebidos.append(
            {
                "endToEndId": f"E{_ISPB_DO_RECEBEDOR}{pagamento.data:%Y%m%d}1500{sequencial:011d}",
                "txid": pagamento.cobranca.txid,
                "valor": _reais(pagamento.valor_centavos),
                "componentesValor": componentes,
                "chave": "cobranca@vantara.com.br",
                "horario": f"{pagamento.data.isoformat()}T15:00:00.000Z",
                "pagador": {"cnpj": pagamento.documento_do_pagador, "nome": pagamento.nome_do_pagador},
            }
        )
    parametros = {
        "inicio": f"{inicio.isoformat()}T00:00:00-03:00",
        "fim": f"{fim.isoformat()}T23:59:59-03:00",
        "paginacao": {
            "paginaAtual": 0,
            "itensPorPagina": len(recebidos),
            "quantidadeDePaginas": 1,
            "quantidadeTotalDeItens": len(recebidos),
        },
    }
    return json.dumps({"parametros": parametros, "pix": recebidos}, ensure_ascii=False, indent=2) + "\n"


def _retorno_cnab_240(banco: str, pagamentos: list[PagamentoDeCobranca], gerado_em: date) -> list[str]:
    codigo = _codigo_do_banco(banco)
    lote = "0001"
    detalhes: list[str] = []
    for pagamento in pagamentos:
        cobranca = pagamento.cobranca
        data = f"{pagamento.data:%d%m%Y}"
        sequencial = len(detalhes) + 1
        detalhes.append(
            _registro(
                (1, 3, codigo), (4, 7, lote), (8, 8, "3"), (9, 13, sequencial), (14, 14, "T"), (16, 17, "06"),
                (38, 57, cobranca.nosso_numero or ""), (74, 81, f"{cobranca.vencimento:%d%m%Y}"),
                (82, 96, cobranca.valor_centavos), (133, 133, "2"), (134, 148, f"{pagamento.documento_do_pagador:0>15}"),
                (149, 188, pagamento.nome_do_pagador[:40]),
            )
        )  # fmt: skip
        detalhes.append(
            _registro(
                (1, 3, codigo), (4, 7, lote), (8, 8, "3"), (9, 13, sequencial + 1), (14, 14, "U"), (16, 17, "06"),
                (18, 32, pagamento.multa_centavos + pagamento.juros_centavos), (33, 47, 0), (48, 62, 0), (63, 77, 0),
                (78, 92, pagamento.valor_centavos), (93, 107, pagamento.valor_centavos), (138, 145, data),
                (146, 153, data),
            )
        )  # fmt: skip
    return [
        _registro((1, 3, codigo), (4, 7, "0000"), (8, 8, "0"), (143, 143, "2"), (144, 151, f"{gerado_em:%d%m%Y}"), (164, 166, "103")),
        _registro((1, 3, codigo), (4, 7, lote), (8, 8, "1"), (9, 9, "T"), (10, 11, "01"), (14, 16, "060")),
        *detalhes,
        _registro((1, 3, codigo), (4, 7, lote), (8, 8, "5"), (18, 23, len(detalhes) + 2)),
        _registro((1, 3, codigo), (4, 7, "9999"), (8, 8, "9"), (18, 23, 1), (24, 29, len(detalhes) + 4)),
    ]


def _registro(*campos: tuple[int, int, str | int]) -> str:
    linha = [" "] * _TAMANHO_DO_REGISTRO
    for inicio, fim, valor in campos:
        tamanho = fim - inicio + 1
        texto = f"{valor:0{tamanho}d}" if isinstance(valor, int) else valor.ljust(tamanho)
        if len(texto) != tamanho:
            raise ValueError(f"campo {inicio}-{fim} do CNAB 240 com '{texto}', maior que {tamanho} posições")
        linha[inicio - 1 : fim] = texto
    return "".join(linha)


def _codigo_do_banco(banco: str) -> str:
    if banco not in _CODIGOS_DOS_BANCOS:
        raise ValueError(f"banco '{banco}' sem código de compensação na porta simulada")
    return _CODIGOS_DOS_BANCOS[banco]


def _reais(centavos: int) -> str:
    return f"{centavos // 100}.{centavos % 100:02d}"
