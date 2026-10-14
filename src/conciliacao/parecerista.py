import json
import urllib.request
from collections.abc import Sequence
from typing import Protocol

from conciliacao.configuracao import ConfiguracaoDaIa
from conciliacao.dominio import Parecer, Resposta

VERSAO_DO_PROMPT = "nome-v2"

_INSTRUCOES = (
    "Você confere pagamentos recebidos por uma franqueadora. O extrato bancário mostra o nome do pagador sem "
    "acento e sem pontuação, cortado num limite de caracteres (a última palavra pode estar pela metade), às vezes "
    "abreviado, com palavras em outra ordem ou faltando, e com \"&\" escrito como \"E\" ou omitido.\n"
    "Decida se o nome do extrato é de uma empresa com algum dos nomes do franqueado informados.\n"
    "Regra: cada palavra do extrato precisa corresponder a uma palavra do nome do franqueado, igual ou como o "
    "começo dela (abreviação), em qualquer ordem. Palavras do nome do franqueado podem faltar no extrato. "
    "Palavras genéricas como LTDA, ME, EIRELI, CIA, E, DE, DO, COM ou COMERCIO não identificam a empresa.\n"
    "Responda pertence = false se o extrato tiver uma palavra distintiva que não corresponde a nenhuma palavra do "
    "nome do franqueado, se for o nome de outra pessoa ou empresa, ou se você tiver dúvida.\n"
    "Na explicacao, diga em uma frase curta, em português, quais palavras correspondem ou quais não correspondem."
)

_EXEMPLOS = (
    (
        "SORV PINGUIM ALEGRE",
        ("Sorveteria Pinguim Alegre Ltda",),
        "SORV abrevia Sorveteria; PINGUIM e ALEGRE são iguais.",
        True,
    ),
    (
        "SORV PINGUIM FELIZ",
        ("Sorveteria Pinguim Alegre Ltda",),
        "FELIZ não corresponde a nenhuma palavra do nome; o franqueado é Pinguim Alegre.",
        False,
    ),
    (
        "BARBOSA E FILHOS TRAN",
        ("Transportes Barbosa & Filhos Ltda",),
        "BARBOSA e FILHOS são iguais, E é o &, TRAN é o começo de Transportes, em outra ordem.",
        True,
    ),
    (
        "BARBOSA COSTA TRANSP",
        ("Transportes Barbosa & Filhos Ltda",),
        "COSTA não corresponde a nenhuma palavra do nome; só BARBOSA e TRANSP coincidem.",
        False,
    ),
    (
        "GIRASSOL COM DE BEBI",
        ("Girassol Comercio de Bebidas Eireli", "GIRASSOL BEBIDAS"),
        "GIRASSOL é igual, COM abrevia Comercio e BEBI é Bebidas cortado no limite.",
        True,
    ),
    (
        "GIRASSOL TECIDOS",
        ("Girassol Comercio de Bebidas Eireli", "GIRASSOL BEBIDAS"),
        "TECIDOS não corresponde a nenhuma palavra do nome; o franqueado vende bebidas.",
        False,
    ),
    (
        "ACOUGUE SAO BENTO",
        ("Açougue e Mercearia São Bento ME",),
        "ACOUGUE, SAO e BENTO são iguais sem acento; falta só Mercearia.",
        True,
    ),
    (
        "JOSE CARLOS PRADO",
        ("Hortifruti Campo Limpo Ltda",),
        "JOSE CARLOS PRADO é nome de pessoa e nenhuma palavra corresponde ao nome do franqueado.",
        False,
    ),
)

_FORMATO = {
    "type": "object",
    "properties": {"explicacao": {"type": "string"}, "pertence": {"type": "boolean"}},
    "required": ["explicacao", "pertence"],
}


class PareceristaDeNome(Protocol):
    def dar_parecer(self, nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> Parecer: ...


class PareceristaOllama:
    def __init__(self, configuracao: ConfiguracaoDaIa) -> None:
        self._configuracao = configuracao

    def dar_parecer(self, nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> Parecer:
        pedido = {
            "model": self._configuracao.modelo,
            "stream": False,
            "think": False,
            "format": _FORMATO,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": _INSTRUCOES},
                *_mensagens_dos_exemplos(),
                {"role": "user", "content": _pergunta(nome_do_extrato, nomes_do_franqueado)},
            ],
        }
        requisicao = urllib.request.Request(
            f"{self._configuracao.endereco.rstrip('/')}/api/chat",
            data=json.dumps(pedido).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=self._configuracao.tempo_limite_segundos) as resposta:
                conteudo = json.loads(json.load(resposta)["message"]["content"])
            pertence, explicacao = conteudo["pertence"], conteudo["explicacao"]
        except (OSError, ValueError, KeyError, TypeError) as erro:
            return self._parecer(Resposta.INDISPONIVEL, f"Ollama em {self._configuracao.endereco} não respondeu: {erro}")
        if not isinstance(pertence, bool) or not isinstance(explicacao, str):
            return self._parecer(Resposta.INDISPONIVEL, f"resposta fora do formato pedido: {conteudo}")
        return self._parecer(Resposta.SIM if pertence else Resposta.NAO, explicacao.strip())

    def _parecer(self, resposta: Resposta, explicacao: str) -> Parecer:
        return Parecer(resposta, explicacao, self._configuracao.modelo, VERSAO_DO_PROMPT)


def _pergunta(nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> str:
    nomes = "\n".join(f"- {nome}" for nome in nomes_do_franqueado)
    return f"Nome no extrato: {nome_do_extrato}\nNomes do franqueado:\n{nomes}\nO nome do extrato é desse franqueado?"


def _mensagens_dos_exemplos() -> list[dict[str, str]]:
    mensagens = []
    for nome_do_extrato, nomes_do_franqueado, explicacao, pertence in _EXEMPLOS:
        mensagens.append({"role": "user", "content": _pergunta(nome_do_extrato, nomes_do_franqueado)})
        resposta = json.dumps({"explicacao": explicacao, "pertence": pertence}, ensure_ascii=False)
        mensagens.append({"role": "assistant", "content": resposta})
    return mensagens


class SemIaConfigurada:
    def dar_parecer(self, nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> Parecer:
        return Parecer(Resposta.INDISPONIVEL, "falta a seção [ia] na configuração", "", VERSAO_DO_PROMPT)


def parecerista_da_configuracao(ia: ConfiguracaoDaIa | None) -> PareceristaDeNome:
    return PareceristaOllama(ia) if ia else SemIaConfigurada()
