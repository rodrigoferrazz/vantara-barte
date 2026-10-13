# 05: Omie e nomes do Franqueado entre sistemas

**What to build:** Entra o adaptador da exportação do Omie. Títulos do Protheus e do Omie do mesmo Franqueado (raiz do CNPJ) passam a ser tratados juntos, e o Franqueado guarda todos os nomes que tem em cada Sistema de origem. Títulos do mesmo Franqueado, valor e vencimento em sistemas diferentes viram um item de Título na Fila como Possível duplicidade entre sistemas, sem Crédito.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Exportação Omie (vírgula, ponto decimal, data ISO, CNPJ sem pontuação) é lida como vem
- [ ] Crédito identificado por CNPJ casa com Título do Omie do mesmo jeito que com Título do Protheus
- [ ] Valor único considera os Títulos em aberto do Franqueado em todos os Sistemas de origem
- [ ] Mesmo Franqueado, valor e vencimento em Protheus e Omie gera item de Possível duplicidade na Fila
- [ ] O item de duplicidade não interfere na conferência de soma dos Créditos

Spec: `.scratch/conciliacao-fase1/spec.md`
