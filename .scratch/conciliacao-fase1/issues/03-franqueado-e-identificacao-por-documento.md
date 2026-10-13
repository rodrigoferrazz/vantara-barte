# 03: Franqueado e identificação por CNPJ/CPF

**What to build:** O Franqueado passa a ser identificado pela raiz do CNPJ dos seus Títulos. Crédito cujo histórico traz CNPJ ou CPF de um Pagador conhecido (o CNPJ dos próprios Títulos conta) e cujo valor é Valor único entre os Títulos em aberto daquele pagador vai para a Lista de baixa. Crédito de Franqueado identificado sem nenhum Título candidato vai para a Fila como Crédito sem título em aberto e é retentado a cada nova importação.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] CNPJ no histórico (com ou sem pontuação) identifica o Franqueado pela raiz, incluindo filiais
- [x] Identificado + Valor único vai para a Lista com explicação citando o documento
- [x] Identificado com valor que bate com mais de um Título vai para a Fila
- [x] Identificado sem Título candidato vai para a Fila como Crédito sem título em aberto
- [x] Crédito sem título em aberto de uma execução casa com Título novo que aparece numa execução seguinte

Spec: `.scratch/conciliacao-fase1/spec.md`
