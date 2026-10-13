# 06: Nome por prefixo e Motivos da Fila

**What to build:** Crédito sem documento cujo nome do Extrato, normalizado, é prefixo de algum nome do Franqueado em qualquer Sistema de origem, com Valor único, vai para a Fila com a sugestão de Título e Motivo 'pagador provável, primeira vez'. Todos os Motivos de não identificação passam a existir, um único por item, com a precedência acordada: valor não fecha, Crédito sem título em aberto, nome ambíguo, pagador provável primeira vez.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Nome truncado que é prefixo de um nome do Franqueado em qualquer sistema gera sugestão na Fila
- [ ] Nome por prefixo nunca leva à Lista enquanto não houver Pagador conhecido confirmado
- [ ] Nome que é prefixo de nomes de mais de um Franqueado e o valor não desempata vai como 'nome ambíguo'
- [ ] Crédito sem nome nem documento que só bate por valor vai como 'sem identificação do pagador' com a sugestão
- [ ] Cada item da Fila tem exatamente um Motivo, seguindo a precedência
- [ ] Itens da Fila mostram Título sugerido, evidência encontrada e o que falta

Spec: `.scratch/conciliacao-fase1/spec.md`
