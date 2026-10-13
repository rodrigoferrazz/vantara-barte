# 10: Página de impacto na tela local

**What to build:** A tela local da fase 1 ganha uma página de impacto que mostra a última análise de impacto: o antes e depois, a faixa de Adesão e as Ondas de migração. Para isso, a análise de impacto passa a gravar o resultado no armazenamento, além do workbook, e a página só lê esse resultado, como a tela faz com a execução diária. As páginas da fase 1 não mudam; só ganham o acesso à página nova.

**Blocked by:** 08; fase 1 `.scratch/conciliacao-fase1/issues/15-tela-local-e-conflito.md`

**Status:** ready-for-agent

- [ ] A análise de impacto grava o resultado no armazenamento (tabela nova, migração só aditiva), com data, pasta base, semente e premissas
- [ ] A página lê o resultado gravado da última análise e não recalcula nada; totais batem com o workbook da mesma análise
- [ ] Antes e depois lado a lado para cada Adesão: Créditos soltos e identificados (quantidade e valor), Fila (quantidade e valor), % resolvido sozinho e "não identificável pelo valor"
- [ ] Gráfico da Fila por Adesão e gráfico da queda da Fila por Onda de migração acumulada, para cada Adesão, desenhados no servidor sem biblioteca nem recurso externo (funciona offline)
- [ ] Fila por Motivo de não identificação no antes e em cada Adesão
- [ ] Ranking de migração com a onda de cada Franqueado
- [ ] Premissas visíveis na página: fonte da verdade (quantos Créditos de cada fonte), semente, proporções, parâmetros de Encargo e tamanho da onda
- [ ] Sem análise gravada, a página diz que não há análise; nenhum dado de exemplo ou placeholder
- [ ] A página é só leitura; rodar a análise continua sendo pelo comando (ADR 0006)
- [ ] Os testes da tela da fase 1 passam sem alteração; teste fino via HTTP confere que a página mostra os mesmos totais do workbook
