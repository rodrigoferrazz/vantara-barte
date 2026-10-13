import json
import urllib.request
from collections.abc import Sequence
from typing import Protocol

from conciliacao.configuracao import ConfiguracaoDaIa
from conciliacao.dominio import Parecer, Resposta

VERSAO_DO_PROMPT = "nome-v1"

_INSTRUCOES = (
    "Você confere pagamentos recebidos por uma franqueadora. O extrato bancário mostra o nome do pagador cortado "
    "num limite de caracteres, às vezes abreviado, com palavras invertidas ou faltando, sem acento e sem pontuação.\n"
    "Decida se o nome do extrato é de uma empresa com algum dos nomes do franqueado informados.\n"
    "Primeiro compare palavra por palavra: cada palavra do extrato precisa ser igual a uma palavra do nome do "
    "franqueado ou ser o começo dela (abreviação). Palavras genéricas como LTDA, ME, EIRELI, CIA ou COMERCIO não "
    "identificam a empresa sozinhas.\n"
    "Responda pertence = true só quando as palavras que distinguem a empresa aparecem nos dois nomes. Se o extrato "
    "tem uma palavra distintiva que não existe no nome do franqueado, responda pertence = false.\n"
    "Na explicacao, diga em uma frase curta, em português, quais palavras correspondem ou quais não correspondem."
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
        nomes = "\n".join(f"- {nome}" for nome in nomes_do_franqueado)
        pedido = {
            "model": self._configuracao.modelo,
            "stream": False,
            "format": _FORMATO,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": _INSTRUCOES},
                {
                    "role": "user",
                    "content": f"Nome no extrato: {nome_do_extrato}\nNomes do franqueado:\n{nomes}\n"
                    "O nome do extrato é desse franqueado?",
                },
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


class SemIaConfigurada:
    def dar_parecer(self, nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> Parecer:
        return Parecer(Resposta.INDISPONIVEL, "falta a seção [ia] na configuração", "", VERSAO_DO_PROMPT)


def parecerista_da_configuracao(ia: ConfiguracaoDaIa | None) -> PareceristaDeNome:
    return PareceristaOllama(ia) if ia else SemIaConfigurada()
