from dataclasses import dataclass, field
from html.parser import HTMLParser

_VAZIOS = {"meta", "br", "hr", "img", "input", "link"}


@dataclass
class Elemento:
    tag: str
    atributos: dict[str, str]
    filhos: list["Elemento | str"] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return " ".join(" ".join(parte.split()) for parte in self._textos() if parte.strip())

    @property
    def classes(self) -> set[str]:
        return set(self.atributos.get("class", "").split())

    def _textos(self) -> list[str]:
        textos: list[str] = []
        for filho in self.filhos:
            textos.extend([filho] if isinstance(filho, str) else filho._textos())
        return textos

    def todos(self, tag: str | None = None, classe: str | None = None) -> list["Elemento"]:
        encontrados: list[Elemento] = []
        for filho in self.filhos:
            if isinstance(filho, str):
                continue
            if (tag is None or filho.tag == tag) and (classe is None or classe in filho.classes):
                encontrados.append(filho)
            encontrados.extend(filho.todos(tag, classe))
        return encontrados

    def por_id(self, identificador: str) -> "Elemento":
        [elemento] = [e for e in self.todos() if e.atributos.get("id") == identificador]
        return elemento

    def tem_id(self, identificador: str) -> bool:
        return any(e.atributos.get("id") == identificador for e in self.todos())

    def linhas(self) -> list[list[str]]:
        return [[celula.texto for celula in linha.filhos if isinstance(celula, Elemento)] for linha in self.todos("tr")]


class _Construtor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.raiz = Elemento("documento", {})
        self._pilha = [self.raiz]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        elemento = Elemento(tag, {nome: valor or "" for nome, valor in attrs})
        self._pilha[-1].filhos.append(elemento)
        if tag not in _VAZIOS:
            self._pilha.append(elemento)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VAZIOS:
            return
        assert self._pilha[-1].tag == tag, f"</{tag}> fecha <{self._pilha[-1].tag}>"
        self._pilha.pop()

    def handle_data(self, data: str) -> None:
        self._pilha[-1].filhos.append(data)


def ler_pagina(html: str) -> Elemento:
    construtor = _Construtor()
    construtor.feed(html)
    construtor.close()
    assert construtor._pilha == [construtor.raiz], "elementos sem fechar"
    return construtor.raiz
