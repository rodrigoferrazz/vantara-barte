# 08: Ondas de migração no relatório

**What to build:** A análise de impacto mostra quanto a Fila cai a cada Onda de migração acumulada, na ordem do Ranking, para cada Adesão, para o gestor planejar a implantação.

**Blocked by:** 07

**Status:** ready-for-human

- [x] Para cada onda acumulada e cada Adesão, só os Créditos dos Franqueados já migrados podem chegar identificados
- [x] Aba Ondas com Fila em quantidade e valor e % resolvido sozinho por onda e Adesão
- [x] A Fila em quantidade e em valor nunca aumenta quando a onda ou a Adesão aumentam

## Comments

- Implementado. Testes em `tests/test_ondas_de_migracao.py` (cada onda só identifica Créditos dos Franqueados migrados, uma linha por Adesão em cada onda, sintético com a Fila que nunca aumenta com a onda ou a Adesão e identificados que só crescem, aba Ondas). Os testes que listam as abas da análise passaram a incluir Ondas, e o teste da amostra de julho confere que a única onda dá os mesmos números do Resumo. Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 08").
- Status `ready-for-human`, como nos tickets anteriores.
- Novo: `OndaAcumulada` e `AnaliseDeImpacto.ondas` e `.franqueados`; razão "Franqueado não migrado" em `PorQueFicaSolto`; aba Ondas com o "antes", cada onda acumulada por Adesão e todos os Franqueados por Adesão.
- O Crédito é do Franqueado dos Títulos que paga (pela fonte da verdade), não do Franqueado do Ranking: quem chega identificado é o pagamento da Cobrança do Título. Só os Títulos dos migrados recebem Cobrança identificada.
- As razões que não dependem da onda são decididas uma vez, com todos migrados; por isso a Fila não cresce quando a onda aumenta.
- Amostra de julho, configuração do projeto: uma onda com os 6 Franqueados do Ranking, mesmos números de todos os Franqueados (Fila de 9 para 6 com 50% e 5 com 80% e 95%).
- Sintético de 1.900 Títulos, configuração padrão: 11 ondas; com 95% a Fila vai de 285 para 248 na onda 1 e 117 na 11; com todos os 210 Franqueados, 70. A diferença vem dos Franqueados fora do Ranking.
- Ponto em aberto: cada onda e Adesão é uma conciliação inteira; no sintético de 1.900 Títulos são 36 conciliações, cerca de 2 minutos. Pode pesar no ticket 09.
