# 06: Análise de impacto, o antes e o Ranking de migração

**What to build:** Um comando de análise de impacto recebe uma pasta base, roda a mesma conciliação da fase 1 com armazenamento temporário e gera um workbook com o Ranking de migração dividido em Ondas de migração e as Premissas. É o esqueleto do relatório antes e depois.

**Blocked by:** fase 1 concluída (`.scratch/conciliacao-fase1/issues/17-aceitacao-da-amostra-de-julho.md`)

**Status:** ready-for-human

- [x] Conciliação do "antes" com armazenamento temporário e o Parecerista de nome informado
- [x] Ranking: Franqueados ordenados pelo número de Créditos na Fila com sem identificação do pagador, nome ambíguo, mais de uma combinação possível ou pagador provável, primeira vez; desempate pelo valor
- [x] Crédito sem título em aberto, Possível duplicidade entre sistemas e Possível fonte não integrada não entram no ranking
- [x] Ranking dividido em ondas do tamanho configurado (padrão 10 Franqueados)
- [x] Workbook com abas Ranking de migração e Premissas (semente, parâmetros de Encargo, tamanho da onda)
- [x] O workbook diário da fase 1 não muda

## Comments

- Implementado. Testes em `tests/test_analise_de_impacto.py` (ranking pela execução e pelo domínio, motivos excluídos, desempate, ondas, armazenamento temporário, Parecerista, workbook, configuração, comando, sintético e amostra de julho). Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 06").
- Status `ready-for-human`, como nos tickets anteriores: o `triage-labels.md` não tem papel de concluído.
- Novo: comando `analisar-impacto <pasta base>` (módulo `impacto`), `RankingDeMigracao` no domínio e a seção opcional `[analise_de_impacto]` (`semente`, `tamanho_da_onda`) no `conciliacao.toml`. O workbook diário e os testes da fase 1 não mudaram; a causa raiz só passou a usar a mesma função de nome do Franqueado que o ranking.
- Desvio da spec: semente e tamanho da onda ficam em `[analise_de_impacto]`, não em `[migracao]` (módulo 1), porque a análise precisa rodar na amostra de julho sem ligar a fase 2. A faixa de Adesão do ticket 07 deve ir para a mesma seção.
- Crédito da Fila sem Franqueado identificado conta para o Franqueado dos Títulos sugeridos quando são de um só; o resto fica numa linha "sem Franqueado", fora das ondas. Sem isso, quase todo "sem identificação do pagador" ficaria fora do ranking. Na amostra de julho, o depósito não identificado entra assim.
- "Possível fonte não integrada" nunca aparece no "antes", porque só a Analista o atribui e o armazenamento temporário não tem decisões; a exclusão está testada no domínio. Pelo mesmo motivo "Possível duplicidade entre sistemas" não é motivo de Crédito no motor; também fica excluída.
- A semente ainda não é usada: vai para Premissas agora e fixa o sorteio por Crédito do ticket 07. O `--estado` com decisões confirmadas da Analista (fonte da verdade) também fica para o ticket 07.
