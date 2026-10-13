# 06: Análise de impacto, o antes e o Ranking de migração

**What to build:** Um comando de análise de impacto recebe uma pasta base, roda a mesma conciliação da fase 1 com armazenamento temporário e gera um workbook com o Ranking de migração dividido em Ondas de migração e as Premissas. É o esqueleto do relatório antes e depois.

**Blocked by:** fase 1 concluída (`.scratch/conciliacao-fase1/issues/17-aceitacao-da-amostra-de-julho.md`)

**Status:** ready-for-agent

- [ ] Conciliação do "antes" com armazenamento temporário e o Parecerista de nome informado
- [ ] Ranking: Franqueados ordenados pelo número de Créditos na Fila com sem identificação do pagador, nome ambíguo, mais de uma combinação possível ou pagador provável, primeira vez; desempate pelo valor
- [ ] Crédito sem título em aberto, Possível duplicidade entre sistemas e Possível fonte não integrada não entram no ranking
- [ ] Ranking dividido em ondas do tamanho configurado (padrão 10 Franqueados)
- [ ] Workbook com abas Ranking de migração e Premissas (semente, parâmetros de Encargo, tamanho da onda)
- [ ] O workbook diário da fase 1 não muda
