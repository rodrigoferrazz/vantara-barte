# 10: Relatório de causa raiz

**What to build:** Aba de causa raiz com todos os Créditos da Fila agregados por Motivo de não identificação, por Franqueado, por banco e por canal (Pix, TED, boleto, depósito), somando 100% em quantidade e valor, para mostrar quais Franqueados concentram o problema.

**Blocked by:** 06

**Status:** ready-for-agent

- [x] Cada Crédito da Fila conta em exatamente um Motivo; a soma dá 100% em quantidade e valor
- [x] Agregação por Franqueado ordenada por concentração
- [x] Agregação por banco e por canal, com canal inferido do histórico
- [x] Possível fonte não integrada aparece como categoria própria
- [x] Créditos sem Franqueado aparecem como grupo próprio

Spec: `.scratch/conciliacao-fase1/spec.md`
