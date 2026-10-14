import csv
from collections import Counter
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol

from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.dominio import ArquivoRecusado, Canal, ChaveNatural, Lancamento, Natureza, Titulo
from conciliacao.normalizacao import (
    FormatoInvalido,
    centavos_de_valor_com_ponto,
    centavos_de_valor_ptbr,
    cnpj,
    cnpj_sem_pontuacao,
    data_iso,
    data_ptbr,
)


class Recusa(Exception):
    pass


@dataclass
class Leitura:
    titulos: list[Titulo] = field(default_factory=list)
    lancamentos: list[Lancamento] = field(default_factory=list)
    arquivos_lidos: list[str] = field(default_factory=list)
    arquivos_recusados: list[ArquivoRecusado] = field(default_factory=list)
    sistemas_exportados: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ConteudoDoArquivo:
    titulos: list[Titulo] = field(default_factory=list)
    lancamentos: list[Lancamento] = field(default_factory=list)
    sistema_exportado: str | None = None


class Adaptador(Protocol):
    nome: str
    cabecalho: tuple[str, ...]
    separador: str

    def ler(self, arquivo: Path, linhas: list[list[str]], configuracao: Configuracao) -> ConteudoDoArquivo: ...


class ProtheusContasAReceber:
    nome = "exportação Protheus"
    sistema_de_origem = "Protheus"
    cabecalho: tuple[str, ...] = ("cliente", "cnpj", "unidade", "documento", "nosso_numero", "tipo", "emissao", "vencimento", "valor", "status")
    separador = ";"

    def ler(self, arquivo: Path, linhas: list[list[str]], configuracao: Configuracao) -> ConteudoDoArquivo:
        titulos = []
        for numero, linha in enumerate(linhas, start=2):
            campos = dict(zip(self.cabecalho, linha))
            if campos["status"] != "Aberto":
                raise Recusa(f"linha {numero}: status '{campos['status']}' desconhecido; só 'Aberto' é aceito")
            titulos.append(
                Titulo(
                    sistema_de_origem=self.sistema_de_origem,
                    documento=campos["documento"],
                    nome_do_franqueado=campos["cliente"],
                    cnpj=_formato(numero, cnpj, campos["cnpj"]),
                    nosso_numero=campos["nosso_numero"] or None,
                    vencimento=_formato(numero, data_ptbr, campos["vencimento"]),
                    valor_centavos=_formato(numero, centavos_de_valor_ptbr, campos["valor"]),
                )
            )
        return ConteudoDoArquivo(titulos=titulos, sistema_exportado=self.sistema_de_origem)


class OmieTitulos:
    nome = "exportação Omie"
    sistema_de_origem = "Omie"
    cabecalho: tuple[str, ...] = ("customer_name", "tax_id", "invoice_ref", "due_date", "amount", "paid_flag")
    separador = ","

    def ler(self, arquivo: Path, linhas: list[list[str]], configuracao: Configuracao) -> ConteudoDoArquivo:
        titulos = []
        for numero, linha in enumerate(linhas, start=2):
            campos = dict(zip(self.cabecalho, linha))
            if campos["paid_flag"] != "N":
                raise Recusa(f"linha {numero}: paid_flag '{campos['paid_flag']}' desconhecido; só 'N' é aceito")
            titulos.append(
                Titulo(
                    sistema_de_origem=self.sistema_de_origem,
                    documento=campos["invoice_ref"],
                    nome_do_franqueado=campos["customer_name"],
                    cnpj=_formato(numero, cnpj_sem_pontuacao, campos["tax_id"]),
                    nosso_numero=None,
                    vencimento=_formato(numero, data_iso, campos["due_date"]),
                    valor_centavos=_formato(numero, centavos_de_valor_com_ponto, campos["amount"]),
                )
            )
        return ConteudoDoArquivo(titulos=titulos, sistema_exportado=self.sistema_de_origem)


class ExtratoItau:
    nome = "Extrato Itaú"
    banco = "itau"
    cabecalho: tuple[str, ...] = ("data", "historico", "documento", "valor", "tipo")
    separador = ";"
    historicos_com_nome_do_pagador: tuple[str, ...] = ("PIX RECEBIDO ", "TED RECEBIDA ")
    canais_pelo_inicio_do_historico: tuple[tuple[str, Canal], ...] = (
        ("PIX RECEBIDO", Canal.PIX),
        ("TED RECEBIDA", Canal.TED),
        ("LIQUIDACAO COBRANCA", Canal.BOLETO),
        ("DEPOSITO", Canal.DEPOSITO),
    )

    def canal(self, historico: str) -> Canal:
        return next(
            (canal for inicio, canal in self.canais_pelo_inicio_do_historico if historico.startswith(inicio)),
            Canal.NAO_IDENTIFICADO,
        )

    def nome_do_pagador(self, historico: str) -> str | None:
        for inicio in self.historicos_com_nome_do_pagador:
            if historico.startswith(inicio) and historico[len(inicio) :].strip():
                return historico[len(inicio) :].strip()
        return None

    def ler(self, arquivo: Path, linhas: list[list[str]], configuracao: Configuracao) -> ConteudoDoArquivo:
        conta = _conta_do_extrato(arquivo, configuracao)
        if conta.banco != self.banco:
            raise Recusa(f"layout de Extrato do Itaú, mas a configuração diz que o arquivo é do banco '{conta.banco}'")
        ocorrencias: Counter[ChaveNatural] = Counter()
        lancamentos = []
        for numero, linha in enumerate(linhas, start=2):
            campos = dict(zip(self.cabecalho, linha))
            try:
                natureza = Natureza(campos["tipo"])
            except ValueError:
                raise Recusa(f"linha {numero}: tipo '{campos['tipo']}' desconhecido; só C ou D é aceito") from None
            sem_ordinal = Lancamento(
                banco=conta.banco,
                conta=conta.conta,
                data=_formato(numero, data_ptbr, campos["data"]),
                historico=campos["historico"],
                documento=campos["documento"],
                valor_centavos=_formato(numero, centavos_de_valor_ptbr, campos["valor"]),
                natureza=natureza,
                ordinal=0,
            )
            ocorrencias[sem_ordinal.chave_natural] += 1
            lancamentos.append(replace(sem_ordinal, ordinal=ocorrencias[sem_ordinal.chave_natural]))
        return ConteudoDoArquivo(lancamentos=lancamentos)


EXTRATOS: tuple[ExtratoItau, ...] = (ExtratoItau(),)
ADAPTADORES: tuple[Adaptador, ...] = (ProtheusContasAReceber(), OmieTitulos(), *EXTRATOS)


def nome_do_pagador(lancamento: Lancamento) -> str | None:
    extratos = [extrato for extrato in EXTRATOS if extrato.banco == lancamento.banco]
    return extratos[0].nome_do_pagador(lancamento.historico) if extratos else None


def canal_do_credito(lancamento: Lancamento) -> Canal:
    extratos = [extrato for extrato in EXTRATOS if extrato.banco == lancamento.banco]
    return extratos[0].canal(lancamento.historico) if extratos else Canal.NAO_IDENTIFICADO


def ler_pasta(pasta: Path, configuracao: Configuracao) -> Leitura:
    leitura = Leitura()
    for arquivo in sorted(p for p in pasta.iterdir() if p.is_file() and not p.name.startswith(".")):
        try:
            conteudo = _ler_arquivo(arquivo, configuracao)
        except Recusa as recusa:
            leitura.arquivos_recusados.append(ArquivoRecusado(nome=arquivo.name, motivo=str(recusa)))
        else:
            leitura.arquivos_lidos.append(arquivo.name)
            leitura.titulos.extend(conteudo.titulos)
            leitura.lancamentos.extend(conteudo.lancamentos)
            if conteudo.sistema_exportado is not None:
                leitura.sistemas_exportados.add(conteudo.sistema_exportado)
    return leitura


def _ler_arquivo(arquivo: Path, configuracao: Configuracao) -> ConteudoDoArquivo:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Recusa("o arquivo não é texto UTF-8") from None
    if not texto.strip():
        raise Recusa("o arquivo está vazio")
    for adaptador in ADAPTADORES:
        linhas = _linhas(texto, adaptador)
        if tuple(linhas[0]) == adaptador.cabecalho:
            corpo = [linha for linha in linhas[1:] if linha]
            for numero, linha in enumerate(corpo, start=2):
                if len(linha) != len(adaptador.cabecalho):
                    raise Recusa(f"linha {numero}: {len(linha)} colunas, o layout tem {len(adaptador.cabecalho)}")
            return adaptador.ler(arquivo, corpo, configuracao)
    raise Recusa(_motivo_do_cabecalho_desconhecido(arquivo, texto, configuracao))


def _linhas(texto: str, adaptador: Adaptador) -> list[list[str]]:
    return list(csv.reader(texto.splitlines(), delimiter=adaptador.separador))


def _motivo_do_cabecalho_desconhecido(arquivo: Path, texto: str, configuracao: Configuracao) -> str:
    bancos_com_adaptador = {extrato.banco for extrato in EXTRATOS}
    contas = [conta for conta in configuracao.contas if fnmatch(arquivo.name, conta.padrao)]
    if len(contas) == 1 and contas[0].banco not in bancos_com_adaptador:
        conta = contas[0]
        return f"Extrato do banco '{conta.banco}' (conta {conta.conta}), que não tem adaptador; nenhum layout dele é aceito"
    em_comum = {adaptador: _colunas_em_comum(_linhas(texto, adaptador)[0], adaptador) for adaptador in ADAPTADORES}
    maior = max(em_comum.values())
    mais_proximos = [adaptador for adaptador, quantidade in em_comum.items() if quantidade == maior]
    if maior == 0 or len(mais_proximos) > 1:
        return "cabeçalho não corresponde a nenhum layout conhecido"
    adaptador = mais_proximos[0]
    return f"cabeçalho difere do layout {adaptador.nome}: {_diferenca(_linhas(texto, adaptador)[0], adaptador.cabecalho)}"


def _colunas_em_comum(cabecalho: list[str], adaptador: Adaptador) -> int:
    return len(set(cabecalho) & set(adaptador.cabecalho))


def _diferenca(encontrado: list[str], esperado: tuple[str, ...]) -> str:
    faltam = list((Counter(esperado) - Counter(encontrado)).elements())
    a_mais = list((Counter(encontrado) - Counter(esperado)).elements())
    partes = []
    if faltam:
        partes.append(f"falta {_colunas(faltam)}")
    if a_mais:
        partes.append(f"a mais {_colunas(a_mais)}")
    if not partes:
        partes.append(f"colunas fora da ordem ({_colunas(encontrado)}); a ordem esperada é {_colunas(list(esperado))}")
    return "; ".join(partes)


def _colunas(colunas: list[str]) -> str:
    return ", ".join(f"'{coluna}'" for coluna in colunas)


def _conta_do_extrato(arquivo: Path, configuracao: Configuracao) -> ContaDeExtrato:
    contas = [conta for conta in configuracao.contas if fnmatch(arquivo.name, conta.padrao)]
    if not contas:
        raise Recusa("nome do arquivo não casa com nenhuma conta da configuração")
    if len(contas) > 1:
        padroes = ", ".join(conta.padrao for conta in contas)
        raise Recusa(f"nome do arquivo casa com mais de uma conta da configuração ({padroes})")
    return contas[0]


def _formato[T](numero: int, conversor: "Conversor[T]", texto: str) -> T:
    try:
        return conversor(texto)
    except FormatoInvalido as erro:
        raise Recusa(f"linha {numero}: {erro}") from None


class Conversor[T](Protocol):
    def __call__(self, texto: str, /) -> T: ...
