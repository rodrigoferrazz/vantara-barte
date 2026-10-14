"""Conjunto de avaliação do Parecerista de nome com pares fictícios.

Uso: uv run python -m tests.avaliacao_parecerista [modelo ...]
Sem modelo, usa o do conciliacao.toml.
"""

import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

from conciliacao.configuracao import ConfiguracaoDaIa, carregar_configuracao
from conciliacao.dominio import Resposta
from conciliacao.parecerista import VERSAO_DO_PROMPT, PareceristaDeNome, PareceristaOllama


@dataclass(frozen=True)
class Par:
    nome_do_extrato: str
    nomes_do_franqueado: tuple[str, ...]
    pertence: bool


PARES = (
    Par("LANCH ESTRELA DO SUL", ("Lanchonete Estrela do Sul Ltda",), True),
    Par("MERC SAO JORGE", ("Mercearia São Jorge ME",), True),
    Par("SORVETES GELO BOM", ("Gelo Bom Sorvetes Ltda",), True),
    Par("AURORA E FILHOS DIST", ("Aurora & Filhos Distribuidora Ltda",), True),
    Par("MOINHO DOURADO COM F", ("Moinho Dourado Comercio de Farinhas Eireli",), True),
    Par("CAFE ARCO IRIS", ("Café Arco-Íris Ltda",), True),
    Par("J R SILVA LANCHES", ("J.R. Silva Lanches ME",), True),
    Par("DIST PEIXE AZUL", ("Distribuidora Peixe Azul Ltda", "PEIXE AZUL DISTRIBUICAO"), True),
    Par("PIZZARIA MONTE VERDE", ("Monte Verde Pizzaria e Restaurante Ltda",), True),
    Par("CONFEIT LUA CHEIA", ("Confeitaria Lua Cheia Eireli",), True),
    Par("FARMACIA SANTA LUZIA", ("Drogaria e Farmácia Santa Luzia Ltda",), True),
    Par("SOL NASC RESTAURANTE", ("Restaurante Sol Nascente Ltda",), True),
    Par("TAVARES IRMAOS", ("Irmãos Tavares Comércio de Bebidas Ltda",), True),
    Par("OLIVEIRA CIA", ("Oliveira & Cia Materiais Ltda",), True),
    Par("LANCH ESTRELA DO MAR", ("Lanchonete Estrela do Sul Ltda",), False),
    Par("MERC SAO PEDRO", ("Mercearia São Jorge ME",), False),
    Par("GELO FINO SORVETES", ("Gelo Bom Sorvetes Ltda",), False),
    Par("AURORA MATERIAIS", ("Aurora & Filhos Distribuidora Ltda",), False),
    Par("CAFE ARCO VELHO", ("Café Arco-Íris Ltda",), False),
    Par("J R SOUZA LANCHES", ("J.R. Silva Lanches ME",), False),
    Par("PEIXE DOURADO DIST", ("Distribuidora Peixe Azul Ltda", "PEIXE AZUL DISTRIBUICAO"), False),
    Par("PIZZARIA MONTE ALTO", ("Monte Verde Pizzaria e Restaurante Ltda",), False),
    Par("CONFEIT LUA NOVA", ("Confeitaria Lua Cheia Eireli",), False),
    Par("FARMACIA SANTA RITA", ("Drogaria e Farmácia Santa Luzia Ltda",), False),
    Par("MARIA APARECIDA SOUZ", ("Restaurante Sol Nascente Ltda",), False),
    Par("TAVARES MOVEIS", ("Irmãos Tavares Comércio de Bebidas Ltda",), False),
    Par("OLIVEIRA E SANTOS", ("Oliveira & Cia Materiais Ltda",), False),
    Par("MERCADO BOA ESPERANC", ("Mercado Boa Sorte Ltda",), False),
)


@dataclass(frozen=True)
class Avaliacao:
    acertos: int
    falsos_positivos: tuple[Par, ...]
    falsos_negativos: tuple[Par, ...]
    indisponiveis: tuple[Par, ...]
    segundos_por_chamada: float

    def __str__(self) -> str:
        linhas = [
            f"acertos {self.acertos}/{len(PARES)}, falsos positivos {len(self.falsos_positivos)}, "
            f"falsos negativos {len(self.falsos_negativos)}, indisponíveis {len(self.indisponiveis)}, "
            f"{self.segundos_por_chamada:.1f} s por chamada"
        ]
        linhas += [f"  falso positivo: {p.nome_do_extrato} x {p.nomes_do_franqueado[0]}" for p in self.falsos_positivos]
        linhas += [f"  falso negativo: {p.nome_do_extrato} x {p.nomes_do_franqueado[0]}" for p in self.falsos_negativos]
        return "\n".join(linhas)


def avaliar(parecerista: PareceristaDeNome) -> Avaliacao:
    respostas = []
    inicio = time.monotonic()
    for par in PARES:
        respostas.append((par, parecerista.dar_parecer(par.nome_do_extrato, par.nomes_do_franqueado).resposta))
    segundos = (time.monotonic() - inicio) / len(PARES)
    return Avaliacao(
        acertos=sum(r is (Resposta.SIM if p.pertence else Resposta.NAO) for p, r in respostas),
        falsos_positivos=tuple(p for p, r in respostas if r is Resposta.SIM and not p.pertence),
        falsos_negativos=tuple(p for p, r in respostas if r is Resposta.NAO and p.pertence),
        indisponiveis=tuple(p for p, r in respostas if r is Resposta.INDISPONIVEL),
        segundos_por_chamada=segundos,
    )


def _ia_do_projeto() -> ConfiguracaoDaIa:
    ia = carregar_configuracao(Path(__file__).parent.parent / "conciliacao.toml").ia
    assert ia is not None
    return ia


if __name__ == "__main__":
    ia = _ia_do_projeto()
    for modelo in sys.argv[1:] or [ia.modelo]:
        parecerista = PareceristaOllama(replace(ia, modelo=modelo))
        parecerista.dar_parecer("AQUECIMENTO", ("Aquecimento Ltda",))
        print(f"{modelo} com {VERSAO_DO_PROMPT}: {avaliar(parecerista)}", flush=True)
