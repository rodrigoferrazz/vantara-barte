from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum, auto

from conciliacao.calendario import vencimento_efetivo
from conciliacao.dominio import Titulo
from conciliacao.normalizacao import formatar_reais

_DIAS_DO_MES_COMERCIAL = 30


@dataclass(frozen=True)
class ParametrosDeEncargo:
    multa_percentual: Decimal = Decimal("2")
    juros_ao_mes_percentual: Decimal = Decimal("0")
    tolerancia_centavos: int = 0


class Enquadramento(Enum):
    EM_DIA = auto()
    DENTRO_DO_ENCARGO = auto()
    ENCARGO_NAO_PAGO = auto()
    DIFERENCA_A_MENOR = auto()
    VALOR_A_MAIOR = auto()


@dataclass(frozen=True)
class CreditoEnquadrado:
    enquadramento: Enquadramento
    principal_centavos: int
    encargo_pago_centavos: int
    encargo_previsto_centavos: int
    vencimento_efetivo: date

    @property
    def fecha(self) -> bool:
        return self.enquadramento in (
            Enquadramento.EM_DIA,
            Enquadramento.DENTRO_DO_ENCARGO,
            Enquadramento.ENCARGO_NAO_PAGO,
        )

    def descrever(self) -> str:
        principal = formatar_reais(self.principal_centavos)
        previsto = formatar_reais(self.encargo_previsto_centavos)
        efetivo = self.vencimento_efetivo.strftime("%d/%m/%Y")
        match self.enquadramento:
            case Enquadramento.EM_DIA:
                return f"pago até o Vencimento efetivo {efetivo}, sem Encargo"
            case Enquadramento.DENTRO_DO_ENCARGO:
                return (
                    f"pago após o Vencimento efetivo {efetivo}: principal {principal} e "
                    f"Encargo {formatar_reais(self.encargo_pago_centavos)} (Encargo previsto {previsto})"
                )
            case Enquadramento.ENCARGO_NAO_PAGO:
                return f"pago após o Vencimento efetivo {efetivo} só pelo valor original; Encargo não pago ({previsto})"
            case Enquadramento.DIFERENCA_A_MENOR:
                return f"Diferença a menor em relação ao valor do Título, {principal}"
            case Enquadramento.VALOR_A_MAIOR:
                return (
                    f"Valor a maior: acima do valor do Título, {principal}, somado ao Encargo previsto {previsto} "
                    f"para o Vencimento efetivo {efetivo}"
                )


def enquadrar(titulo: Titulo, valor_centavos: int, data: date, parametros: ParametrosDeEncargo) -> CreditoEnquadrado:
    efetivo = vencimento_efetivo(titulo.vencimento)
    dias_de_atraso = (data - efetivo).days
    previsto = _encargo_previsto(titulo.valor_centavos, dias_de_atraso, parametros) if dias_de_atraso > 0 else 0
    diferenca = valor_centavos - titulo.valor_centavos
    if diferenca < 0:
        enquadramento = Enquadramento.DIFERENCA_A_MENOR
    elif diferenca == 0:
        enquadramento = Enquadramento.ENCARGO_NAO_PAGO if dias_de_atraso > 0 else Enquadramento.EM_DIA
    elif dias_de_atraso > 0 and diferenca <= previsto + parametros.tolerancia_centavos:
        enquadramento = Enquadramento.DENTRO_DO_ENCARGO
    else:
        enquadramento = Enquadramento.VALOR_A_MAIOR
    return CreditoEnquadrado(
        enquadramento=enquadramento,
        principal_centavos=titulo.valor_centavos,
        encargo_pago_centavos=max(diferenca, 0),
        encargo_previsto_centavos=previsto,
        vencimento_efetivo=efetivo,
    )


def multa_e_juros(
    valor_centavos: int, vencimento: date, data: date, parametros: ParametrosDeEncargo
) -> tuple[int, int]:
    dias_de_atraso = (data - vencimento_efetivo(vencimento)).days
    if dias_de_atraso <= 0:
        return 0, 0
    return _multa_e_juros(valor_centavos, dias_de_atraso, parametros)


def _encargo_previsto(valor_centavos: int, dias_de_atraso: int, parametros: ParametrosDeEncargo) -> int:
    return sum(_multa_e_juros(valor_centavos, dias_de_atraso, parametros))


def _multa_e_juros(valor_centavos: int, dias_de_atraso: int, parametros: ParametrosDeEncargo) -> tuple[int, int]:
    valor = Decimal(valor_centavos)
    multa = valor * parametros.multa_percentual / 100
    juros = valor * parametros.juros_ao_mes_percentual / 100 * dias_de_atraso / _DIAS_DO_MES_COMERCIAL
    return _centavos(multa), _centavos(juros)


def _centavos(valor: Decimal) -> int:
    return int(valor.quantize(Decimal(1), rounding=ROUND_HALF_UP))
