# 02: Arquivo desconhecido é recusado sem bloquear os demais

**What to build:** Cada arquivo da pasta é reconhecido pelo conteúdo do cabeçalho e lido por um adaptador que declara exatamente o layout que aceita. Arquivo com coluna diferente, formato estranho, banco desconhecido ou Extrato cujo nome não casa com nenhuma conta configurada é recusado sozinho, com o motivo, e o resto é processado normalmente. A plataforma nunca tenta adivinhar layout (ADR 0005).

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Arquivo com coluna a mais, a menos ou renomeada é recusado com motivo que cita a diferença
- [ ] Arquivo com data ou número em formato inesperado é recusado com motivo, sem processar parcialmente
- [ ] Extrato de banco sem adaptador ou com nome fora da configuração de contas é recusado com motivo
- [ ] Os demais arquivos da mesma pasta são processados e a conferência de soma considera só os aceitos
- [ ] Aba Arquivos recusados no workbook e contagem de lidos e recusados no Resumo

Spec: `.scratch/conciliacao-fase1/spec.md`
