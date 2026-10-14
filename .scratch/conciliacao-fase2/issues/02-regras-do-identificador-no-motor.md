# 02: Regras do identificador no motor

**What to build:** O Identificador de cobrança passa a seguir todas as regras de valor do nosso número da fase 1 e os casos de borda da spec, para que a Analista nunca receba na Lista um Crédito identificado com valor errado nem perca um pagamento duplicado.

**Blocked by:** 01

**Status:** ready-for-human

- [x] Valor dentro do Encargo vai para a Lista com principal, multa e juros (de `componentesValor` quando o Retorno separa)
- [x] Atraso pago pelo valor original vai para a Lista como Encargo não pago
- [x] Valor fora dessas regras vai para a Fila com "valor não fecha", com o Título apontado
- [x] Identificador de Título já baixado vai para a Fila com "Crédito sem título em aberto"
- [ ] Identificador desconhecido vai para a Fila com "Possível fonte não integrada" (não feito por decisão do usuário: segue a fase 1, ver Comments)
- [x] Identificador vale mais que o pagador: QR pago por sócio ou filial vai para o Título do vínculo
- [x] Pagar Cobrança identificada nunca cria Pagador conhecido
- [x] O motor não procura soma para Crédito identificado
- [x] Crédito solto de Franqueado migrado tem exatamente o resultado da fase 1

## Comments

- Implementado. Testes em `tests/test_regras_do_identificador.py`; decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 02"). Os ajudantes de Pix recebidos e da configuração de migração foram para `tests/arquivos.py`.
- Status `ready-for-human`, como no ticket 01: o `triage-labels.md` não tem papel de concluído.
- O caso "valor não fecha" já vinha do ticket 01; aqui entram o Encargo com os componentes do Retorno, o Encargo não pago, o Valor a maior, o Título fora dos em aberto, o identificador desconhecido, o pagador, o Pagador conhecido, a soma e o Crédito solto.
- Decisão do usuário: identificador desconhecido ou que aponta Título fora dos em aberto não recebe "Possível fonte não integrada" do motor. Esse Motivo continua só classificação da Analista; o identificador desconhecido segue o caminho da fase 1 (a explicação só cita o txid sem vínculo) e o de Título fora dos em aberto vai para "Crédito sem título em aberto".
- Fora do ticket, decidido por coerência com o nosso número: proposta do identificador rejeitada pela Analista segue a fase 1 sem o Título rejeitado.
- Ponto em aberto: as colunas de componentes entram na tabela de Retornos do ticket 01 sem migração; banco criado com o código do ticket 01 e `[migracao]` ligada precisa ser recriado.
