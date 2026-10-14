# 17: Aceitação da amostra de julho

**What to build:** Teste de aceitação que roda a plataforma sobre a amostra de julho e compara, lançamento por lançamento, com o resultado validado pelo usuário (tabela em Further Notes da spec), além de uma verificação de que nenhum nome, valor ou número de nota da amostra aparece no código de produção.

**Blocked by:** 07, 08, 09, 10

**Status:** ready-for-agent

- [x] Com Data de referência 31/07: Lista com 6 Créditos (156.658,00), Fila com 9 (159.150,50), Fora do escopo com 3 débitos (20.229,00)
- [ ] Destino, Título e Motivo de cada lançamento iguais à tabela da spec
- [x] IA chamada em exatamente 2 casos (DOCE PONTO COM ALIME e SABOR CIA), usando a IA falsa
- [x] Um item de Possível duplicidade (Grao Nobre, Omie x Protheus)
- [ ] Lista de cobrança com 1 Título (Norte Panificados, 8.120,00) e 9 em análise
- [x] Valores esperados ficam só na fixture do teste; verificação automática falha se algum valor ou nome da amostra aparecer no código de produção
- [ ] Confirmar com o usuário que o teste pode ler a pasta da amostra

Spec: `.scratch/conciliacao-fase1/spec.md`
