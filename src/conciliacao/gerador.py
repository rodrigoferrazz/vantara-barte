import math
import random
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from pathlib import Path

from conciliacao.calendario import eh_dia_util, vencimento_efetivo
from conciliacao.configuracao import ContaDeExtrato
from conciliacao.dominio import Destino, MotivoDeNaoIdentificacao, Natureza
from conciliacao.encargo import ParametrosDeEncargo
from conciliacao.normalizacao import nome_normalizado

_MAXIMO_DE_TITULOS_POR_FRANQUEADO = 14
_LARGURA_DO_NOME_NO_EXTRATO = 20
_CONTAS = 4
_PROTHEUS, _OMIE = "Protheus", "Omie"

_TIPOS = (
    "Padaria", "Confeitaria", "Panificadora", "Empório", "Doceria", "Cafeteria",
    "Casa do Pão", "Rede", "Mercearia", "Pastelaria", "Bistrô", "Lanchonete",
)  # fmt: skip
_PRIMEIRAS = (
    "Aurora", "Primavera", "Horizonte", "Bela Vista", "Vila Nova", "Santa Clara", "São Jorge", "Trigo",
    "Girassol", "Jardim", "Estrela", "Recanto", "Pomar", "Colina", "Alvorada", "Bom Gosto", "Fornalha",
    "Ipê", "Cantinho", "Sabor", "Ouro", "Lua", "Serra", "Lagoa", "Moinho", "Sol", "Vale", "Monte",
    "Ribeira", "Canela", "Palmeira", "Tradição", "Família", "Pioneira", "Imperial", "Real", "Oásis",
)  # fmt: skip
_SEGUNDAS = (
    "Dourada", "Mineiro", "Paulista", "do Sul", "Nobre", "Central", "Feliz", "Doce", "Prime", "Gourmet",
    "Brasil", "Norte", "Azul", "Verde", "Nova", "Antiga", "Fina", "Rústica", "Caseira", "Artesanal",
)  # fmt: skip
_SUFIXOS = ("Ltda", "ME", "S.A.", "Eireli", "Comércio de Alimentos Ltda", "& Cia Ltda", "EPP")
_SUFIXOS_DO_OMIE = ("LTDA", "S/A", "EIRELI", "COM LTDA", "ME")
_UNIDADES = ("SP-Capital", "SP-Interior", "MG", "RJ", "PR", "SC", "RS", "BA")
_TIPOS_DE_TITULO = ("Produto", "Royalty", "Serviço")
_DEPOSITOS = ("DEPOSITO NAO IDENTIFICADO", "DEPOSITO EM DINHEIRO", "DEPOSITO ENVELOPE")
_DEBITOS = ("TARIFA PACOTE COBRANCA", "TARIFA PIX EMISSAO", "TED ENVIADA FORNECEDOR", "PAGAMENTO DE SALARIOS")
_LIQUIDACAO = "LIQUIDACAO COBRANCA SIMPLES"
_TARIFA_DO_FIM_DO_MES = "TARIFA MANUTENCAO CONTA"


class ConfiguracaoDoGeradorInvalida(ValueError):
    pass


class Caso(StrEnum):
    BOLETO_EM_DIA = "boleto em dia"
    MULTA = "multa"
    ENCARGO_NAO_PAGO = "Encargo não pago"
    PARCIAL = "parcial"
    CNPJ_NO_HISTORICO = "CNPJ no histórico"
    SOMA_DE_TITULOS = "soma de Títulos"
    NOME_TRUNCADO = "nome truncado"
    NOME_ABREVIADO = "nome abreviado"
    NOME_INVERTIDO = "nome invertido"
    DEPOSITO_SEM_NOME = "depósito sem nome"
    ANTECIPACAO = "antecipação"
    DEBITO = "débito"


@dataclass(frozen=True)
class Proporcoes:
    """Frações do número de Títulos; unidade_norte é fração dos Franqueados, só no Omie."""

    nome_truncado: float = 0.06
    nome_abreviado: float = 0.02
    nome_invertido: float = 0.02
    cnpj_no_historico: float = 0.08
    soma_de_titulos: float = 0.02
    parcial: float = 0.02
    multa: float = 0.04
    encargo_nao_pago: float = 0.04
    deposito_sem_nome: float = 0.02
    sem_pagamento: float = 0.08
    duplicidade_entre_sistemas: float = 0.01
    antecipacao: float = 0.01
    debitos: float = 0.03
    unidade_norte: float = 0.10


@dataclass(frozen=True)
class ConfiguracaoDoGerador:
    semente: int
    ano: int = 2026
    mes: int = 8
    titulos: int = 1_900
    franqueados: int = 210
    proporcoes: Proporcoes = Proporcoes()
    encargo: ParametrosDeEncargo = ParametrosDeEncargo()


@dataclass(frozen=True)
class LancamentoEsperado:
    conta: str
    data: date
    historico: str
    documento: str
    valor_centavos: int
    natureza: Natureza
    caso: Caso
    destino: Destino
    titulos: frozenset[tuple[str, str]]
    motivo: MotivoDeNaoIdentificacao | None
    pagador: str | None = None
    nome_no_extrato: str | None = None


@dataclass(frozen=True)
class DadosSinteticos:
    arquivos: dict[str, str]
    contas: tuple[ContaDeExtrato, ...]
    gabarito: tuple[LancamentoEsperado, ...]
    nomes_dos_franqueados: dict[str, tuple[str, ...]]
    duplicidades: frozenset[frozenset[tuple[str, str]]]

    def escrever(self, pasta: Path) -> None:
        pasta.mkdir(parents=True, exist_ok=True)
        for nome, conteudo in self.arquivos.items():
            (pasta / nome).write_text(conteudo, encoding="utf-8")


def gerar_dados_sinteticos(configuracao: ConfiguracaoDoGerador) -> DadosSinteticos:
    _validar(configuracao)
    return _Gerador(configuracao).gerar()


_FRACOES_QUE_CONSOMEM_TITULOS = (
    "nome_truncado", "nome_abreviado", "nome_invertido", "cnpj_no_historico", "soma_de_titulos",
    "parcial", "multa", "encargo_nao_pago", "deposito_sem_nome", "sem_pagamento", "duplicidade_entre_sistemas",
)  # fmt: skip


def _validar(configuracao: ConfiguracaoDoGerador) -> None:
    proporcoes = configuracao.proporcoes
    for campo in fields(proporcoes):
        valor = getattr(proporcoes, campo.name)
        if not 0 <= valor <= 1:
            raise ConfiguracaoDoGeradorInvalida(f"proporção {campo.name} = {valor} fora do intervalo de 0 a 1")
    soma = sum(getattr(proporcoes, nome) for nome in _FRACOES_QUE_CONSOMEM_TITULOS)
    if soma > 1:
        raise ConfiguracaoDoGeradorInvalida(f"as proporções de Títulos somam {soma:.2f}, acima de 1")
    if not configuracao.franqueados <= configuracao.titulos <= configuracao.franqueados * _MAXIMO_DE_TITULOS_POR_FRANQUEADO:
        raise ConfiguracaoDoGeradorInvalida(
            f"{configuracao.titulos} Títulos não cabem em {configuracao.franqueados} Franqueados "
            f"(de 1 a {_MAXIMO_DE_TITULOS_POR_FRANQUEADO} por Franqueado)"
        )


@dataclass
class _Franqueado:
    raiz: str
    tipo: str
    nucleo: str
    nome_protheus: str | None
    nome_omie: str | None
    unidade: str

    @property
    def cnpj(self) -> str:
        return _cnpj(self.raiz + "0001")

    @property
    def cnpj_de_filial(self) -> str:
        return _cnpj(self.raiz + "0002")

    @property
    def nome_principal(self) -> str:
        return self.nome_protheus or self.nome_omie or ""

    @property
    def nomes(self) -> tuple[str, ...]:
        return tuple(nome for nome in (self.nome_protheus, self.nome_omie) if nome)


@dataclass(frozen=True)
class _Titulo:
    sistema: str
    documento: str
    raiz: str
    nosso_numero: str | None
    vencimento: date
    valor_centavos: int
    tipo: str

    @property
    def chave(self) -> tuple[str, str]:
        return (self.sistema, self.documento)


@dataclass(frozen=True)
class _Lancamento:
    conta: str
    data: date
    historico: str
    documento: str
    valor_centavos: int
    natureza: Natureza


@dataclass
class _Gerador:
    configuracao: ConfiguracaoDoGerador
    rng: random.Random = field(init=False)
    franqueados: list[_Franqueado] = field(default_factory=list)
    titulos: list[_Titulo] = field(default_factory=list)
    por_raiz: dict[str, list[_Titulo]] = field(default_factory=dict)
    duplicidades: list[frozenset[tuple[str, str]]] = field(default_factory=list)
    contas: tuple[ContaDeExtrato, ...] = ()
    gabarito: list[LancamentoEsperado] = field(default_factory=list)
    pagos: set[tuple[str, str]] = field(default_factory=set)
    chaves: set[tuple[str, date, str, int]] = field(default_factory=set)
    nomes_de_ia: set[str] = field(default_factory=set)
    _somas: dict[str, Counter[int]] = field(default_factory=dict)
    _nomes_normalizados: list[tuple[str, str]] = field(default_factory=list)
    _por_raiz_do_franqueado: dict[str, _Franqueado] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.configuracao.semente)
        primeiro = date(self.configuracao.ano, self.configuracao.mes, 1)
        proximo = date(primeiro.year + primeiro.month // 12, primeiro.month % 12 + 1, 1)
        self.dias = [primeiro + timedelta(days=n) for n in range((proximo - primeiro).days)]
        self.dias_uteis = [dia for dia in self.dias if eh_dia_util(dia)]

    def quantidade(self, fracao: float) -> int:
        return round(fracao * self.configuracao.titulos)

    def gerar(self) -> DadosSinteticos:
        self._gerar_franqueados()
        self._por_raiz_do_franqueado = {f.raiz: f for f in self.franqueados}
        self._gerar_titulos()
        self._gerar_contas()
        self._nomes_normalizados = [(nome_normalizado(n), f.raiz) for f in self.franqueados for n in f.nomes]
        self._gerar_creditos()
        self._gerar_debitos()
        return DadosSinteticos(
            arquivos=self._arquivos(),
            contas=self.contas,
            gabarito=tuple(sorted(self.gabarito, key=lambda e: (e.conta, e.data, e.historico, e.valor_centavos))),
            nomes_dos_franqueados={f.raiz: f.nomes for f in self.franqueados},
            duplicidades=frozenset(self.duplicidades),
        )

    def _gerar_franqueados(self) -> None:
        quantidade = self.configuracao.franqueados
        do_norte = set(self.rng.sample(range(quantidade), round(self.configuracao.proporcoes.unidade_norte * quantidade)))
        raizes: set[str] = set()
        prefixos: set[str] = set()
        for indice in range(quantidade):
            raiz = self._novo(raizes, lambda: str(self.rng.randrange(10_000_000, 100_000_000)))
            while True:
                tipo, nucleo = self.rng.choice(_TIPOS), self._nucleo()
                prefixo = _como_o_banco_escreve(f"{tipo} {nucleo}")[:_LARGURA_DO_NOME_NO_EXTRATO]
                if prefixo not in prefixos:
                    prefixos.add(prefixo)
                    break
            nome = f"{tipo} {nucleo} {self.rng.choice(_SUFIXOS)}"
            norte = indice in do_norte
            self.franqueados.append(
                _Franqueado(
                    raiz=raiz,
                    tipo=tipo,
                    nucleo=nucleo,
                    nome_protheus=None if norte else nome,
                    nome_omie=_como_o_omie_escreve(f"{tipo} {nucleo} {self.rng.choice(_SUFIXOS_DO_OMIE)}") if norte else None,
                    unidade="Norte" if norte else self.rng.choice(_UNIDADES),
                )
            )

    def _nucleo(self) -> str:
        primeira = self.rng.choice(_PRIMEIRAS)
        return f"{primeira} {self.rng.choice(_SEGUNDAS)}" if self.rng.random() < 0.7 else primeira

    def _novo(self, existentes: set[str], sortear: Callable[[], str]) -> str:
        while (valor := sortear()) in existentes:
            pass
        existentes.add(valor)
        return valor

    def _gerar_titulos(self) -> None:
        duplicadas = self.quantidade(self.configuracao.proporcoes.duplicidade_entre_sistemas)
        originais = self.configuracao.titulos - duplicadas
        contagem = {f.raiz: 1 for f in self.franqueados}
        pesos = {f.raiz: self.rng.uniform(0.3, 2.0) for f in self.franqueados}
        for _ in range(originais - len(self.franqueados)):
            livres = [raiz for raiz in contagem if contagem[raiz] < _MAXIMO_DE_TITULOS_POR_FRANQUEADO]
            contagem[self.rng.choices(livres, [pesos[r] for r in livres])[0]] += 1
        nosso_numero = self.rng.randrange(10**9, 10**10)
        numeros = {_PROTHEUS: self.rng.randrange(100_000, 200_000), _OMIE: 1}
        for franqueado in self.franqueados:
            for _ in range(contagem[franqueado.raiz]):
                sistema = _OMIE if franqueado.nome_protheus is None else _PROTHEUS
                numeros[sistema] += 1
                if sistema == _PROTHEUS:
                    nosso_numero += 1
                self._guardar(
                    _Titulo(
                        sistema=sistema,
                        documento=self._documento(sistema, numeros[sistema]),
                        raiz=franqueado.raiz,
                        nosso_numero=f"{nosso_numero:012d}" if sistema == _PROTHEUS else None,
                        vencimento=self.rng.choice(self.dias),
                        valor_centavos=self._valor(300_00, 150_000_00),
                        tipo=self.rng.choice(_TIPOS_DE_TITULO),
                    )
                )
        do_protheus = [t for t in self.titulos if t.sistema == _PROTHEUS]
        for original in self.rng.sample(do_protheus, min(duplicadas, len(do_protheus))):
            franqueado = self._franqueado(original.raiz)
            if franqueado.nome_omie is None:
                sufixo = self.rng.choice(_SUFIXOS_DO_OMIE)
                franqueado.nome_omie = _como_o_omie_escreve(f"{franqueado.nucleo} {franqueado.tipo} {sufixo}")
            numeros[_OMIE] += 1
            copia = _Titulo(
                _OMIE, self._documento(_OMIE, numeros[_OMIE]), original.raiz, None,
                original.vencimento, original.valor_centavos, original.tipo,
            )  # fmt: skip
            self._guardar(copia)
            self.duplicidades.append(frozenset({original.chave, copia.chave}))

    def _documento(self, sistema: str, numero: int) -> str:
        return f"NF {numero}" if sistema == _PROTHEUS else f"FAT-{self.configuracao.ano}-{numero:04d}"

    def _guardar(self, titulo: _Titulo) -> None:
        self.titulos.append(titulo)
        self.por_raiz.setdefault(titulo.raiz, []).append(titulo)

    def _franqueado(self, raiz: str) -> _Franqueado:
        return self._por_raiz_do_franqueado[raiz]

    def _valor(self, minimo: int, maximo: int) -> int:
        centavos = int(math.exp(self.rng.uniform(math.log(minimo), math.log(maximo))))
        return centavos - centavos % 100 if self.rng.random() < 0.3 else centavos

    def _gerar_contas(self) -> None:
        numeros: set[str] = set()
        competencia = f"{self.configuracao.ano}{self.configuracao.mes:02d}"
        self.contas = tuple(
            ContaDeExtrato(padrao=f"extrato_itau_{conta}_*.csv", banco="itau", conta=conta)
            for conta in (
                self._novo(numeros, lambda: f"{self.rng.randrange(1000, 10000)}-{self.rng.randrange(10)}")
                for _ in range(_CONTAS)
            )
        )
        self.arquivos_dos_extratos = {c.conta: f"extrato_itau_{c.conta}_{competencia}.csv" for c in self.contas}

    def _gerar_creditos(self) -> None:
        proporcoes = self.configuracao.proporcoes
        tentativas: tuple[tuple[Caso | None, float, Callable[[_Titulo], bool]], ...] = (
            (Caso.SOMA_DE_TITULOS, proporcoes.soma_de_titulos, self._soma),
            (Caso.NOME_TRUNCADO, proporcoes.nome_truncado, self._nome_truncado),
            (Caso.NOME_ABREVIADO, proporcoes.nome_abreviado, lambda t: self._nome_para_a_ia(t, Caso.NOME_ABREVIADO)),
            (Caso.NOME_INVERTIDO, proporcoes.nome_invertido, lambda t: self._nome_para_a_ia(t, Caso.NOME_INVERTIDO)),
            (Caso.CNPJ_NO_HISTORICO, proporcoes.cnpj_no_historico, self._cnpj_no_historico),
            (Caso.PARCIAL, proporcoes.parcial, self._parcial),
            (Caso.MULTA, proporcoes.multa, self._multa),
            (Caso.ENCARGO_NAO_PAGO, proporcoes.encargo_nao_pago, self._encargo_nao_pago),
            (Caso.DEPOSITO_SEM_NOME, proporcoes.deposito_sem_nome, self._deposito),
            (None, proporcoes.sem_pagamento, self._sem_pagamento),
        )
        originais = [t for t in self.titulos if not self._eh_copia(t)]
        for caso, fracao, tentar in tentativas:
            faltam = self.quantidade(fracao)
            livres = [t for t in originais if t.chave not in self.pagos]
            self.rng.shuffle(livres)
            for titulo in livres:
                if faltam == 0:
                    break
                if titulo.chave not in self.pagos and tentar(titulo):
                    faltam -= 1
            if faltam:
                nome = caso.value if caso else "sem pagamento"
                raise ConfiguracaoDoGeradorInvalida(f"faltaram Títulos para mais {faltam} casos de {nome}")
        self._antecipacoes(self.quantidade(proporcoes.antecipacao))
        for titulo in originais:
            if titulo.chave not in self.pagos:
                if titulo.nosso_numero:
                    self._boleto(titulo, Caso.BOLETO_EM_DIA, titulo.valor_centavos, self._dias_em_dia(titulo))
                else:
                    self._cnpj_no_historico(titulo)

    def _eh_copia(self, titulo: _Titulo) -> bool:
        return titulo.sistema == _OMIE and self._franqueado(titulo.raiz).nome_protheus is not None

    def _soma(self, titulo: _Titulo) -> bool:
        outros = [t for t in self.por_raiz[titulo.raiz] if t != titulo and t.chave not in self.pagos and not self._eh_copia(t)]
        if not outros:
            return False
        juntos = [titulo, *self.rng.sample(outros, min(len(outros), self.rng.choice((1, 1, 2))))]
        valor = sum(t.valor_centavos for t in juntos)
        if self._opcoes(titulo.raiz, valor) != 1:
            return False
        return self._credito(
            juntos, Caso.SOMA_DE_TITULOS, valor, self.dias_uteis, self._historico_com_cnpj(titulo.raiz),
            Destino.LISTA_DE_BAIXA,
        )  # fmt: skip

    def _nome_truncado(self, titulo: _Titulo) -> bool:
        nome = self._truncar(self._franqueado(titulo.raiz).nome_principal)
        if self._franqueados_do_prefixo(nome) != [titulo.raiz] or self._opcoes(titulo.raiz, titulo.valor_centavos) != 1:
            return False
        return self._credito(
            [titulo], Caso.NOME_TRUNCADO, titulo.valor_centavos, self._dias_em_dia(titulo), self._com_nome(nome),
            Destino.FILA_DE_EXCECOES, MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ, nome,
        )  # fmt: skip

    def _nome_para_a_ia(self, titulo: _Titulo, caso: Caso) -> bool:
        franqueado = self._franqueado(titulo.raiz)
        if caso is Caso.NOME_ABREVIADO:
            nome = self._abreviar(f"{franqueado.tipo} {franqueado.nucleo}")
        else:
            nome = self._truncar(f"{franqueado.nucleo} {franqueado.tipo}")
        if (
            nome in self.nomes_de_ia
            or self._franqueados_do_prefixo(nome)
            or self._opcoes(titulo.raiz, titulo.valor_centavos) != 1
        ):
            return False
        if not self._credito(
            [titulo], caso, titulo.valor_centavos, self._dias_em_dia(titulo), self._com_nome(nome),
            Destino.FILA_DE_EXCECOES, MotivoDeNaoIdentificacao.PAGADOR_PROVAVEL_PRIMEIRA_VEZ, nome,
        ):  # fmt: skip
            return False
        self.nomes_de_ia.add(nome)
        return True

    def _cnpj_no_historico(self, titulo: _Titulo) -> bool:
        if self._opcoes(titulo.raiz, titulo.valor_centavos) != 1:
            return False
        return self._credito(
            [titulo], Caso.CNPJ_NO_HISTORICO, titulo.valor_centavos, self._dias_em_dia(titulo),
            self._historico_com_cnpj(titulo.raiz), Destino.LISTA_DE_BAIXA,
        )  # fmt: skip

    def _parcial(self, titulo: _Titulo) -> bool:
        valor = round(titulo.valor_centavos * self.rng.uniform(0.3, 0.9))
        if titulo.nosso_numero:
            return self._boleto(titulo, Caso.PARCIAL, valor, self._dias_em_dia(titulo))
        if self._opcoes(titulo.raiz, valor) != 0:
            return False
        return self._credito(
            [titulo], Caso.PARCIAL, valor, self._dias_em_dia(titulo), self._historico_com_cnpj(titulo.raiz),
            Destino.FILA_DE_EXCECOES, self._motivo_sem_opcao(titulo.raiz),
        )  # fmt: skip

    def _motivo_sem_opcao(self, raiz: str) -> MotivoDeNaoIdentificacao:
        if len(self.por_raiz[raiz]) == 1:
            return MotivoDeNaoIdentificacao.VALOR_NAO_FECHA
        return MotivoDeNaoIdentificacao.CREDITO_SEM_TITULO_EM_ABERTO

    def _multa(self, titulo: _Titulo) -> bool:
        multa = Decimal(titulo.valor_centavos) * self.configuracao.encargo.multa_percentual / 100
        return self._atrasado(titulo, Caso.MULTA, titulo.valor_centavos + int(multa.quantize(Decimal(1), ROUND_HALF_UP)))

    def _encargo_nao_pago(self, titulo: _Titulo) -> bool:
        return self._atrasado(titulo, Caso.ENCARGO_NAO_PAGO, titulo.valor_centavos)

    def _atrasado(self, titulo: _Titulo, caso: Caso, valor: int) -> bool:
        dias = self._dias_atrasados(titulo)
        if titulo.nosso_numero:
            return self._boleto(titulo, caso, valor, dias)
        if self._opcoes(titulo.raiz, valor) != 1:
            return False
        return self._credito([titulo], caso, valor, dias, self._historico_com_cnpj(titulo.raiz), Destino.LISTA_DE_BAIXA)

    def _deposito(self, titulo: _Titulo) -> bool:
        return self._credito(
            [titulo], Caso.DEPOSITO_SEM_NOME, titulo.valor_centavos, self._dias_em_dia(titulo),
            (self.rng.choice(_DEPOSITOS), ""), Destino.FILA_DE_EXCECOES,
            MotivoDeNaoIdentificacao.SEM_IDENTIFICACAO_DO_PAGADOR,
        )  # fmt: skip

    def _sem_pagamento(self, titulo: _Titulo) -> bool:
        self.pagos.add(titulo.chave)
        return True

    def _antecipacoes(self, quantidade: int) -> None:
        candidatos = list(self.franqueados)
        self.rng.shuffle(candidatos)
        for franqueado in candidatos:
            if quantidade == 0:
                return
            nome = self._truncar(franqueado.nome_principal)
            valor = self._valor(300_00, 150_000_00)
            if self._franqueados_do_prefixo(nome) != [franqueado.raiz] or self._opcoes(franqueado.raiz, valor) != 0:
                continue
            if self._lancar(
                _Lancamento(self._conta_qualquer(), self.rng.choice(self.dias_uteis), *self._com_nome(nome), valor, Natureza.CREDITO),
                Caso.ANTECIPACAO, Destino.FILA_DE_EXCECOES, frozenset(), self._motivo_sem_opcao(franqueado.raiz),
                franqueado.raiz, nome,
            ):  # fmt: skip
                quantidade -= 1
        if quantidade:
            raise ConfiguracaoDoGeradorInvalida(f"faltaram Franqueados para mais {quantidade} casos de antecipação")

    def _boleto(self, titulo: _Titulo, caso: Caso, valor: int, dias: list[date]) -> bool:
        destino = Destino.FILA_DE_EXCECOES if caso is Caso.PARCIAL else Destino.LISTA_DE_BAIXA
        motivo = MotivoDeNaoIdentificacao.VALOR_NAO_FECHA if caso is Caso.PARCIAL else None
        historico = (_LIQUIDACAO, titulo.nosso_numero or "")
        return self._credito([titulo], caso, valor, dias, historico, destino, motivo, conta=self.contas[0].conta)

    def _credito(
        self,
        titulos: list[_Titulo],
        caso: Caso,
        valor: int,
        dias: list[date],
        historico: tuple[str, str],
        destino: Destino,
        motivo: MotivoDeNaoIdentificacao | None = None,
        nome_no_extrato: str | None = None,
        conta: str | None = None,
    ) -> bool:
        if not dias:
            return False
        lancamento = _Lancamento(
            conta or self._conta_qualquer(), self.rng.choice(dias), historico[0], historico[1], valor, Natureza.CREDITO
        )
        chaves = frozenset(t.chave for t in titulos)
        if not self._lancar(lancamento, caso, destino, chaves, motivo, titulos[0].raiz, nome_no_extrato):
            return False
        self.pagos.update(chaves)
        return True

    def _lancar(
        self,
        lancamento: _Lancamento,
        caso: Caso,
        destino: Destino,
        titulos: frozenset[tuple[str, str]],
        motivo: MotivoDeNaoIdentificacao | None,
        pagador: str | None,
        nome_no_extrato: str | None,
    ) -> bool:
        chave = (lancamento.conta, lancamento.data, lancamento.historico, lancamento.valor_centavos)
        if chave in self.chaves:
            return False
        self.chaves.add(chave)
        self.gabarito.append(
            LancamentoEsperado(
                conta=lancamento.conta,
                data=lancamento.data,
                historico=lancamento.historico,
                documento=lancamento.documento,
                valor_centavos=lancamento.valor_centavos,
                natureza=lancamento.natureza,
                caso=caso,
                destino=destino,
                titulos=titulos,
                motivo=motivo,
                pagador=pagador,
                nome_no_extrato=nome_no_extrato,
            )
        )
        return True

    def _gerar_debitos(self) -> None:
        quantidade = self.quantidade(self.configuracao.proporcoes.debitos)
        feitos = 0
        for conta in self.contas[:quantidade]:
            feitos += self._debito(_Lancamento(conta.conta, self.dias_uteis[-1], _TARIFA_DO_FIM_DO_MES, "", self._valor(20_00, 200_00), Natureza.DEBITO))
        while feitos < quantidade:
            historico = self.rng.choice((*_DEBITOS, f"PAGAMENTO FORNECEDOR NF {self.rng.randrange(10_000, 100_000)}"))
            feitos += self._debito(
                _Lancamento(
                    self._conta_qualquer(), self.rng.choice(self.dias_uteis), historico, "",
                    self._valor(10_00, 50_000_00), Natureza.DEBITO,
                )
            )  # fmt: skip

    def _debito(self, lancamento: _Lancamento) -> int:
        return int(self._lancar(lancamento, Caso.DEBITO, Destino.FORA_DO_ESCOPO, frozenset(), None, None, None))

    def _conta_qualquer(self) -> str:
        return self.rng.choice(self.contas).conta

    def _dias_em_dia(self, titulo: _Titulo) -> list[date]:
        efetivo = vencimento_efetivo(titulo.vencimento)
        return [dia for dia in self.dias_uteis if titulo.vencimento - timedelta(days=7) <= dia <= efetivo]

    def _dias_atrasados(self, titulo: _Titulo) -> list[date]:
        efetivo = vencimento_efetivo(titulo.vencimento)
        return [dia for dia in self.dias_uteis if efetivo < dia <= efetivo + timedelta(days=20)]

    def _historico_com_cnpj(self, raiz: str) -> tuple[str, str]:
        franqueado = self._franqueado(raiz)
        cnpj = franqueado.cnpj_de_filial if self.rng.random() < 0.2 else franqueado.cnpj
        return (self.rng.choice((f"PIX RECEBIDO {cnpj}", f"TED RECEBIDA CNPJ {cnpj}")), "")

    def _com_nome(self, nome: str) -> tuple[str, str]:
        return (f"{self.rng.choice(('PIX RECEBIDO', 'TED RECEBIDA'))} {nome}", "")

    def _abreviar(self, nome: str) -> str:
        primeira, *resto = _como_o_banco_escreve(nome).split()
        palavras = [primeira[:3], *(p[:4] if len(p) > 5 and self.rng.random() < 0.5 else p for p in resto)]
        return self._truncar(" ".join(palavras))

    @staticmethod
    def _truncar(nome: str) -> str:
        return _como_o_banco_escreve(nome)[:_LARGURA_DO_NOME_NO_EXTRATO].rstrip()

    def _franqueados_do_prefixo(self, nome: str) -> list[str]:
        normalizado = nome_normalizado(nome)
        return sorted({raiz for nome_do_franqueado, raiz in self._nomes_normalizados if nome_do_franqueado.startswith(normalizado)})

    def _opcoes(self, raiz: str, valor: int) -> int:
        titulos = self.por_raiz[raiz]
        sozinhos = sum(1 for t in titulos if t.valor_centavos <= valor <= t.valor_centavos + self._folga(t.valor_centavos))
        return sozinhos + self._somas_da_raiz(raiz)[valor]

    def _folga(self, valor: int) -> int:
        # Acima do Encargo previsto de qualquer atraso possível dentro do mês, para nunca subestimar o que fecha.
        encargo = self.configuracao.encargo
        percentual = encargo.multa_percentual + encargo.juros_ao_mes_percentual * 40 / 30
        return math.ceil(Decimal(valor) * percentual / 100) + encargo.tolerancia_centavos + 2

    def _somas_da_raiz(self, raiz: str) -> Counter[int]:
        if raiz not in self._somas:
            parciais = [(0, 0)]
            for titulo in self.por_raiz[raiz]:
                parciais += [(soma + titulo.valor_centavos, tamanho + 1) for soma, tamanho in parciais]
            self._somas[raiz] = Counter(soma for soma, tamanho in parciais if tamanho >= 2)
        return self._somas[raiz]

    def _arquivos(self) -> dict[str, str]:
        competencia = f"{self.configuracao.ano}{self.configuracao.mes:02d}"
        protheus = [t for t in self.titulos if t.sistema == _PROTHEUS]
        omie = [t for t in self.titulos if t.sistema == _OMIE]
        arquivos = {
            f"contas_a_receber_protheus_{competencia}.csv": _csv(
                "cliente;cnpj;unidade;documento;nosso_numero;tipo;emissao;vencimento;valor;status",
                [self._linha_protheus(t) for t in protheus],
            ),
            f"titulos_omie_{competencia}.csv": _csv(
                "customer_name,tax_id,invoice_ref,due_date,amount,paid_flag", [self._linha_omie(t) for t in omie]
            ),
        }
        for conta in self.contas:
            do_extrato = sorted(
                (e for e in self.gabarito if e.conta == conta.conta),
                key=lambda e: (e.data, e.natureza, e.historico, e.valor_centavos),
            )
            arquivos[self.arquivos_dos_extratos[conta.conta]] = _csv(
                "data;historico;documento;valor;tipo",
                [
                    ";".join([_data_ptbr(e.data), e.historico, e.documento, _valor_ptbr(e.valor_centavos), e.natureza.value])
                    for e in do_extrato
                ],
            )
        return arquivos

    def _linha_protheus(self, titulo: _Titulo) -> str:
        franqueado = self._franqueado(titulo.raiz)
        return ";".join(
            [
                franqueado.nome_protheus or "",
                _cnpj_pontuado(franqueado.cnpj),
                franqueado.unidade,
                titulo.documento,
                titulo.nosso_numero or "",
                titulo.tipo,
                _data_ptbr(titulo.vencimento - timedelta(days=10)),
                _data_ptbr(titulo.vencimento),
                _valor_ptbr(titulo.valor_centavos),
                "Aberto",
            ]
        )

    def _linha_omie(self, titulo: _Titulo) -> str:
        franqueado = self._franqueado(titulo.raiz)
        reais, centavos = divmod(titulo.valor_centavos, 100)
        return ",".join(
            [
                franqueado.nome_omie or "",
                franqueado.cnpj,
                titulo.documento,
                titulo.vencimento.isoformat(),
                f"{reais}.{centavos:02d}",
                "N",
            ]
        )


def _csv(cabecalho: str, linhas: list[str]) -> str:
    return "\n".join([cabecalho, *linhas]) + "\n"


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _como_o_banco_escreve(nome: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", "", _sem_acento(nome).upper()).split())


def _como_o_omie_escreve(nome: str) -> str:
    return " ".join(_sem_acento(nome).upper().replace("&", "E").split())


def _cnpj(base: str) -> str:
    digitos = [int(d) for d in base]
    for pesos in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        resto = sum(d * p for d, p in zip(digitos, pesos)) % 11
        digitos.append(0 if resto < 2 else 11 - resto)
    return "".join(map(str, digitos))


def _cnpj_pontuado(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def _data_ptbr(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def _valor_ptbr(centavos: int) -> str:
    reais, resto = divmod(centavos, 100)
    return f"{reais:,}".replace(",", ".") + f",{resto:02d}"
