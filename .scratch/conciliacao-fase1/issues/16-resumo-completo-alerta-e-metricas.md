# 16: Resumo completo, alerta de queda e métricas

**What to build:** O Resumo no topo das saídas passa a mostrar tudo: arquivos lidos e recusados, quanto foi resolvido sozinho (quantidade e valor), se a IA estava funcionando, conta que segura a Data de referência e conflitos. Ele avisa quando a parte resolvida sozinha cai além de um limite configurável em relação à execução anterior. Um relatório mostra taxa de rejeição por tipo de evidência e acerto da primeira sugestão da IA, sem rebaixar regra automaticamente.

**Blocked by:** 08, 12

**Status:** ready-for-agent

- [x] Resumo mostra lidos, recusados, % resolvido sozinho, estado da IA, conta atrasada e conflitos
- [x] Queda do % automático acima do limite configurável gera aviso no Resumo
- [x] Relatório de taxa de rejeição por tipo de evidência
- [x] Relatório de acerto da primeira sugestão da IA
- [x] Nenhuma regra muda de comportamento por causa das métricas

Spec: `.scratch/conciliacao-fase1/spec.md`
