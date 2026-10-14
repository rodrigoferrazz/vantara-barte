from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class CobrancaIdentificada:
    sistema_de_origem: str
    documento: str
    valor_centavos: int
    vencimento: date
    cnpj: str
    txid: str


class PortaDeCobranca(Protocol):
    def emitir(self, cobranca: CobrancaIdentificada) -> None: ...


class PortaSimulada:
    def __init__(self) -> None:
        self.emitidas: list[CobrancaIdentificada] = []

    def emitir(self, cobranca: CobrancaIdentificada) -> None:
        self.emitidas.append(cobranca)
