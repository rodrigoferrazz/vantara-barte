import csv
from collections import Counter
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Protocol

from conciliacao.configuracao import Configuracao, ContaDeExtrato
from conciliacao.dominio import ArquivoRecusado, ChaveNatural, Lancamento, Natureza, Titulo
from conciliacao.normalizacao import FormatoInvalido, centavos_de_valor_ptbr, data_ptbr


class Recusa(Exception):
    pass


@dataclass
class Leitura:
    titulos: list[Titulo] = field(default_factory=list)
    lancamentos: list[Lancamento] = field(default_factory=list)
    arquivos_lidos: list[str] = field(default_factory=list)
    arquivos_recusados: list[ArquivoRecusado] = field(default_factory=list)


@dataclass(frozen=True)
class ConteudoDoArquivo:
    titulos: list[Titulo] = field(default_factory=list)
    lancamentos: list[Lancamento] = field(default_factory=list)


class Adaptador(Protocol):
    cabecalho: tuple[str, ...]
    separador: str

    def ler(self, arquivo: Path, linhas: list[list[str]], configuracao: Configuracao) -> ConteudoDoArquivo: ...


class ProtheusContasAReceber:
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
                    sistema_de_origem="Protheus",
                    documento=campos["documento"],
                    cliente=campos["cliente"],
                    cnpj=campos["cnpj"],
                    nosso_numero=campos["nosso_numero"] or None,
                    vencimento=_formato(numero, data_ptbr, campos["vencimento"]),
                    valor_centavos=_formato(numero, centavos_de_valor_ptbr, campos["valor"]),
                )
            )
        return ConteudoDoArquivo(titulos=titulos)


class ExtratoItau:
    banco = "itau"
    cabecalho: tuple[str, ...] = ("data", "historico", "documento", "valor", "tipo")
    separador = ";"

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


ADAPTADORES: tuple[Adaptador, ...] = (ProtheusContasAReceber(), ExtratoItau())


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
    return leitura


def _ler_arquivo(arquivo: Path, configuracao: Configuracao) -> ConteudoDoArquivo:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Recusa("o arquivo não é texto UTF-8") from None
    for adaptador in ADAPTADORES:
        linhas = list(csv.reader(texto.splitlines(), delimiter=adaptador.separador))
        if linhas and tuple(linhas[0]) == adaptador.cabecalho:
            corpo = [linha for linha in linhas[1:] if linha]
            for numero, linha in enumerate(corpo, start=2):
                if len(linha) != len(adaptador.cabecalho):
                    raise Recusa(f"linha {numero}: {len(linha)} colunas, o layout tem {len(adaptador.cabecalho)}")
            return adaptador.ler(arquivo, corpo, configuracao)
    raise Recusa("cabeçalho não corresponde a nenhum layout conhecido")


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
