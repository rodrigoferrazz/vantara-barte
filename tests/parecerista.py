from collections.abc import Iterable, Sequence

from conciliacao.dominio import Parecer, Resposta

MODELO_FALSO = "modelo-falso"
VERSAO_DO_PROMPT_FALSA = "prompt-falso-1"


class PareceristaFalso:
    def __init__(self, sim_para: Iterable[tuple[str, str]] = (), indisponivel: bool = False) -> None:
        self._sim_para = set(sim_para)
        self._indisponivel = indisponivel
        self.chamadas: list[tuple[str, tuple[str, ...]]] = []

    def dar_parecer(self, nome_do_extrato: str, nomes_do_franqueado: Sequence[str]) -> Parecer:
        self.chamadas.append((nome_do_extrato, tuple(nomes_do_franqueado)))
        if self._indisponivel:
            return self._parecer(Resposta.INDISPONIVEL, "Ollama fora do ar")
        for nome in nomes_do_franqueado:
            if (nome_do_extrato, nome) in self._sim_para:
                return self._parecer(Resposta.SIM, f"'{nome_do_extrato}' abrevia '{nome}'")
        return self._parecer(Resposta.NAO, f"'{nome_do_extrato}' não lembra nenhum nome do Franqueado")

    @staticmethod
    def _parecer(resposta: Resposta, explicacao: str) -> Parecer:
        return Parecer(resposta=resposta, explicacao=explicacao, modelo=MODELO_FALSO, versao_do_prompt=VERSAO_DO_PROMPT_FALSA)
