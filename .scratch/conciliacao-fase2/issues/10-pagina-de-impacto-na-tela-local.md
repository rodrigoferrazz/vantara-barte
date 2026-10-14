# 10: Página de impacto na tela local

**What to build:** A tela local da fase 1 ganha uma página de impacto que mostra a última análise de impacto: o antes e depois, a faixa de Adesão e as Ondas de migração. Para isso, a análise de impacto passa a gravar o resultado no armazenamento, além do workbook, e a página só lê esse resultado, como a tela faz com a execução diária. As páginas da fase 1 não mudam; só ganham o acesso à página nova.

**Blocked by:** 08; fase 1 `.scratch/conciliacao-fase1/issues/15-tela-local-e-conflito.md`

**Status:** ready-for-human

- [x] A análise de impacto grava o resultado no armazenamento (tabela nova, migração só aditiva), com data, pasta base, semente e premissas
- [x] A página lê o resultado gravado da última análise e não recalcula nada; totais batem com o workbook da mesma análise
- [x] Antes e depois lado a lado para cada Adesão: Créditos soltos e identificados (quantidade e valor), Fila (quantidade e valor), % resolvido sozinho e "não identificável pelo valor"
- [x] Gráfico da Fila por Adesão e gráfico da queda da Fila por Onda de migração acumulada, para cada Adesão, desenhados no servidor sem biblioteca nem recurso externo (funciona offline)
- [x] Fila por Motivo de não identificação no antes e em cada Adesão
- [x] Ranking de migração com a onda de cada Franqueado
- [x] Premissas visíveis na página: fonte da verdade (quantos Créditos de cada fonte), semente, proporções, parâmetros de Encargo e tamanho da onda
- [x] Sem análise gravada, a página diz que não há análise; nenhum dado de exemplo ou placeholder
- [x] A página é só leitura; rodar a análise continua sendo pelo comando (ADR 0006)
- [x] Os testes da tela da fase 1 passam sem alteração; teste fino via HTTP confere que a página mostra os mesmos totais do workbook

## Comments

- Implementado. Página em `GET /impacto` da `conciliar-tela` (`renderizar_impacto` em `pagina.py`), relatório gravado na tabela nova `analises_de_impacto` (`registrar_analise_de_impacto` e `ultima_analise_de_impacto` no armazenamento). Testes em `tests/test_pagina_de_impacto.py`. Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 10").
- Workbook e página saem do mesmo `RelatorioDeImpacto` (`AnaliseDeImpacto.relatorio`), então os totais não divergem; o teste via HTTP compara célula por célula as abas Resumo do impacto (transposta), Ondas, Fila por motivo, Ranking de migração e Premissas.
- Mudança de interface do `analisar-impacto`: `--estado` agora tem padrão `conciliacao.sqlite`, é lido para as decisões quando existe e recebe o resultado (o arquivo é criado se faltar). Antes era opcional, só leitura, e um caminho inexistente dava erro. Dois testes da fase 2 foram ajustados por isso; os testes da fase 1 não mudaram.
- Critério "proporções" nas Premissas: a análise não usa proporções do simulador (Plano contrafactual, ticket 07). A aba e a página dizem isso numa linha nova ("Proporções do simulador: não se aplicam ..."), em vez de mostrar números que não entraram no cálculo.
- `PorQueFicaSolto` mudou de `impacto.py` para `dominio.py`, porque o relatório gravado depende dela; três testes da fase 2 só tiveram o import ajustado.
- Conferido localmente: `conciliar data`, `analisar-impacto data` e `conciliar-tela` sobre o mesmo estado; a página mostra os números de julho do ticket 09 (Fila de 9 para 6 e 5 Créditos, Ranking com 6 Franqueados numa onda).
