from collections.abc import Iterable, Sequence, Set
from dataclasses import dataclass

from conciliacao.dominio import (
    ConfirmacaoEmVigor,
    ConfirmacaoRevertida,
    SituacaoNoErp,
    Titulo,
    TituloConfirmado,
    TituloNoAcompanhamento,
)
from conciliacao.normalizacao import formatar_reais

type ChaveDoTitulo = tuple[str, str]


def chave_do_titulo(titulo: Titulo) -> ChaveDoTitulo:
    return (titulo.sistema_de_origem, titulo.documento)


@dataclass(frozen=True)
class Divergencia:
    confirmacao: ConfirmacaoEmVigor
    baixado: Titulo
    explicacao: str


@dataclass(frozen=True)
class Acompanhamento:
    saldos: dict[ChaveDoTitulo, int]
    divergencias: tuple[Divergencia, ...]
    situacoes: tuple[TituloNoAcompanhamento, ...]


def saldos(titulos: Iterable[Titulo], confirmacoes: Iterable[ConfirmacaoEmVigor]) -> dict[ChaveDoTitulo, int]:
    confirmados = [confirmado for confirmacao in confirmacoes for confirmado in confirmacao.titulos]
    return {
        chave_do_titulo(titulo): max(
            titulo.valor_centavos
            - sum(confirmado.principal_centavos for confirmado in _pendentes(titulo, confirmados)),
            0,
        )
        for titulo in titulos
    }


def acompanhar_o_erp(
    atuais: Sequence[Titulo],
    anteriores: Sequence[Titulo],
    confirmacoes: Sequence[ConfirmacaoEmVigor],
    revertidas: Sequence[ConfirmacaoRevertida],
    propostos: Set[ChaveDoTitulo],
    cancelados: Set[ChaveDoTitulo],
) -> Acompanhamento:
    por_chave = {chave_do_titulo(titulo): titulo for titulo in atuais}
    confirmados = {chave_do_titulo(c.titulo) for confirmacao in confirmacoes for c in confirmacao.titulos}
    sumidos = [
        titulo
        for chave, titulo in {chave_do_titulo(t): t for t in anteriores}.items()
        if chave not in por_chave and chave not in confirmados and chave not in cancelados
    ]
    divergencias: list[Divergencia] = []
    baixados_por_fora: list[Titulo] = []
    for sumido in sumidos:
        afetadas = [
            (confirmacao, aguardando)
            for confirmacao in confirmacoes
            if (aguardando := _aguardando_do_mesmo_franqueado(confirmacao, sumido, por_chave))
        ]
        divergencias.extend(
            Divergencia(confirmacao, sumido, _explicar_divergencia(sumido, confirmacao.item, aguardando))
            for confirmacao, aguardando in afetadas
        )
        if not afetadas and chave_do_titulo(sumido) not in propostos:
            baixados_por_fora.append(sumido)
    divergentes = {divergencia.confirmacao.decisao for divergencia in divergencias}
    em_vigor = [confirmacao for confirmacao in confirmacoes if confirmacao.decisao not in divergentes]
    saldo = saldos(atuais, em_vigor)
    return Acompanhamento(
        saldos=saldo,
        divergencias=tuple(divergencias),
        situacoes=(
            *_aguardando_baixa(atuais, em_vigor, saldo),
            *(
                TituloNoAcompanhamento(
                    SituacaoNoErp.BAIXADO_POR_FORA,
                    titulo,
                    None,
                    f"Sumiu da exportação do {titulo.sistema_de_origem} sem Proposta de baixa da plataforma.",
                )
                for titulo in baixados_por_fora
            ),
            *(
                TituloNoAcompanhamento(
                    SituacaoNoErp.DIVERGENCIA_DE_BAIXA,
                    divergencia.baixado,
                    divergencia.confirmacao.item,
                    divergencia.explicacao,
                )
                for divergencia in divergencias
            ),
            *(
                TituloNoAcompanhamento(
                    SituacaoNoErp.ESTORNO_NECESSARIO_NO_ERP,
                    titulo,
                    revertida.item,
                    f"A confirmação do item {revertida.item} foi revertida pela Analista ({revertida.motivo}), mas o "
                    f"Título já foi baixado no {titulo.sistema_de_origem}; estorne a baixa no ERP.",
                )
                for revertida in revertidas
                for titulo in revertida.sem_reaparecer
                if chave_do_titulo(titulo) not in por_chave
            ),
        ),
    )


def _pendentes(titulo: Titulo, confirmados: Iterable[TituloConfirmado]) -> list[TituloConfirmado]:
    return [
        confirmado
        for confirmado in confirmados
        if chave_do_titulo(confirmado.titulo) == chave_do_titulo(titulo)
        and not confirmado.absorvido_pelo_erp(titulo.valor_centavos)
    ]


def _aguardando_do_mesmo_franqueado(
    confirmacao: ConfirmacaoEmVigor, sumido: Titulo, por_chave: dict[ChaveDoTitulo, Titulo]
) -> list[Titulo]:
    return [
        atual
        for confirmado in confirmacao.titulos
        if (atual := por_chave.get(chave_do_titulo(confirmado.titulo))) is not None
        and atual.sistema_de_origem == sumido.sistema_de_origem
        and atual.franqueado == sumido.franqueado
        and not confirmado.absorvido_pelo_erp(atual.valor_centavos)
    ]


def _explicar_divergencia(sumido: Titulo, item: str, aguardando: list[Titulo]) -> str:
    documentos = ", ".join(titulo.documento for titulo in aguardando)
    return (
        f"Divergência de baixa: o Título {sumido.documento} sumiu da exportação do {sumido.sistema_de_origem} sem "
        f"Proposta de baixa, enquanto {documentos}, do mesmo Franqueado e confirmado(s) no item {item}, continua(m) em "
        "aberto; confira qual Título foi baixado no ERP."
    )


def _aguardando_baixa(
    atuais: Sequence[Titulo], confirmacoes: Sequence[ConfirmacaoEmVigor], saldo: dict[ChaveDoTitulo, int]
) -> list[TituloNoAcompanhamento]:
    situacoes = []
    for titulo in sorted(atuais, key=lambda t: (t.vencimento, t.sistema_de_origem, t.documento)):
        itens = [
            (confirmacao.item, confirmado)
            for confirmacao in confirmacoes
            for confirmado in _pendentes(titulo, confirmacao.titulos)
        ]
        if not itens:
            continue
        pagos = formatar_reais(sum(confirmado.principal_centavos for _, confirmado in itens))
        restante = saldo[chave_do_titulo(titulo)]
        falta = f"falta a baixa parcial no ERP, Saldo {formatar_reais(restante)}." if restante else "falta dar a baixa no ERP."
        situacoes.append(
            TituloNoAcompanhamento(
                SituacaoNoErp.AGUARDANDO_BAIXA_NO_ERP,
                titulo,
                ", ".join(dict.fromkeys(item for item, _ in itens)),
                f"Confirmado na plataforma ({pagos} de principal) e ainda em aberto no {titulo.sistema_de_origem}; {falta}",
                restante,
            )
        )
    return situacoes
