# 07: Análise de impacto, o depois por Adesão

**What to build:** A análise de impacto passa a mostrar, para cada Adesão da faixa e com todos os Franqueados migrados, como a mesma pasta se concilia quando os Créditos chegam identificados: mesmo dinheiro, mesma data, mesmo Franqueado, só muda a identificação.

**Blocked by:** 05, 06

**Status:** ready-for-agent

- [ ] Fonte da verdade, nesta ordem: gabarito; decisões confirmadas da Analista quando um armazenamento é informado; Proposta da Lista ou sugestão da Fila do "antes"; o relatório diz quantos Créditos vieram de cada fonte
- [ ] Um único sorteio por Crédito, fixo pela semente; Adesão maior contém a menor
- [ ] Crédito que pagou vários Títulos vira um pagamento identificado por Título, no mesmo dia e com o mesmo total
- [ ] Crédito com valor que a spec não permite com txid fica solto e é contado como "não identificável pelo valor"; Crédito sem Título conhecido fica solto
- [ ] Créditos que já chegavam pelo nosso número continuam identificados
- [ ] Emite pela porta simulada, gera o "depois" pelo simulador e concilia com armazenamento temporário novo e o mesmo Parecerista
- [ ] Abas Resumo do impacto (soltos e identificados, Fila em quantidade e valor, % resolvido sozinho) e Fila por motivo, para cada Adesão (padrão 50%, 80%, 95%)
- [ ] Adesão de 0% dá "depois" igual ao "antes"; o dinheiro do "depois" soma igual ao do "antes"
