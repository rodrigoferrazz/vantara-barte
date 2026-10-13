# 09: Lista de cobrança e Data de referência

**What to build:** A Data de referência passa a ser a menor entre as últimas datas dos Extratos das contas configuradas, e o Resumo mostra qual conta está segurando a data. A aba Lista de cobrança traz os Títulos vencidos pelo Vencimento efetivo na Data de referência, com Saldo em aberto e sem Crédito candidato, e mostra à parte os 'em análise'.

**Blocked by:** 04, 05

**Status:** ready-for-agent

- [ ] Data de referência é a menor das últimas datas entre os Extratos, nunca a data do computador
- [ ] Resumo mostra a conta que segura a Data de referência
- [ ] Título com Crédito candidato na Lista ou na Fila não entra na cobrança e aparece como 'em análise'
- [ ] Título marcado como Possível duplicidade não entra na cobrança
- [ ] Boleto dentro de 2 dias úteis após o Vencimento efetivo não entra na cobrança
- [ ] Título com pagamento parcial confirmado entra só pelo Saldo

Spec: `.scratch/conciliacao-fase1/spec.md`
