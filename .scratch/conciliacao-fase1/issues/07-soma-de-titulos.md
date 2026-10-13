# 07: Soma de Títulos e combinações

**What to build:** Crédito que fecha exatamente com uma única combinação de Títulos em aberto do mesmo Franqueado (1:N) vai para a Lista, desde que o pagador esteja identificado por CNPJ/CPF ou por Pagador conhecido já confirmado; com nome só por prefixo ou semelhança vai para a Fila como qualquer nome não confirmado. Mais de uma combinação, limite de busca atingido, pagamento parcial (N:1) e N:M vão para a Fila.

**Blocked by:** 03, 06

**Status:** ready-for-agent

- [ ] Soma exata e única com pagador identificado por documento vai para a Lista com a soma na explicação
- [ ] Soma exata e única com nome não confirmado vai para a Fila como 'pagador provável, primeira vez' com a combinação sugerida
- [ ] Duas ou mais combinações que fecham o valor vão para a Fila como 'mais de uma combinação possível'
- [ ] A busca considera só Títulos do mesmo Franqueado e tem limite configurável; atingido o limite, vai para a Fila como 'mais de uma combinação possível'
- [ ] Crédito que paga parte de um Título vai para a Fila como 'valor não fecha'
- [ ] Vários Créditos para vários Títulos nunca vão para a Lista

Spec: `.scratch/conciliacao-fase1/spec.md`
