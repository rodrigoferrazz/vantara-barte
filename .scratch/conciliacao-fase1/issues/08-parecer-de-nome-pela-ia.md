# 08: Parecer de nome pela IA local

**What to build:** Quando o nome do Extrato não é Nome por prefixo de nenhum nome do Franqueado candidato (já filtrado por valor), a plataforma pede à LLM local via Ollama um parecer: o nome é ou não desse Franqueado, e por quê. O item vai para a Fila com o parecer, nunca para a Lista (ADR 0003). Parecer negativo muda o Motivo para 'sem identificação do pagador'. Ollama fora do ar não para a execução: o item vai sem parecer, marcado 'IA indisponível'.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] O Parecerista de nome é uma interface com implementação Ollama e uma falsa determinística para os testes
- [ ] A LLM só é chamada para nomes que não são prefixo de nenhum nome do Franqueado; nomes por prefixo não a chamam
- [ ] Resposta estruturada com sim/não e explicação, exibida no item da Fila
- [ ] Parecer negativo resulta em Motivo 'sem identificação do pagador' mantendo a sugestão por valor
- [ ] Com Ollama indisponível a execução termina, os itens ficam marcados 'IA indisponível' e o Resumo mostra isso
- [ ] Cada parecer registra modelo e versão do prompt
- [ ] Um teste de integração chama o Ollama real e é pulado se ele não estiver rodando
- [ ] Modelo padrão cabe num MacBook Air M2 de 8 GB

Spec: `.scratch/conciliacao-fase1/spec.md`
