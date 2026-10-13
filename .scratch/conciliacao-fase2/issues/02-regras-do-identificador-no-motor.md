# 02: Regras do identificador no motor

**What to build:** O Identificador de cobrança passa a seguir todas as regras de valor do nosso número da fase 1 e os casos de borda da spec, para que a Analista nunca receba na Lista um Crédito identificado com valor errado nem perca um pagamento duplicado.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Valor dentro do Encargo vai para a Lista com principal, multa e juros (de `componentesValor` quando o Retorno separa)
- [ ] Atraso pago pelo valor original vai para a Lista como Encargo não pago
- [ ] Valor fora dessas regras vai para a Fila com "valor não fecha", com o Título apontado
- [ ] Identificador de Título já baixado vai para a Fila com "Crédito sem título em aberto"
- [ ] Identificador desconhecido vai para a Fila com "Possível fonte não integrada"
- [ ] Identificador vale mais que o pagador: QR pago por sócio ou filial vai para o Título do vínculo
- [ ] Pagar Cobrança identificada nunca cria Pagador conhecido
- [ ] O motor não procura soma para Crédito identificado
- [ ] Crédito solto de Franqueado migrado tem exatamente o resultado da fase 1
