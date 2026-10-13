# 12: Confirmar e rejeitar a Lista de baixa pelo Excel

**What to build:** A Lista de baixa sai no Excel com a decisão 'confirmar' pré-preenchida. Na execução seguinte, a plataforma lê o workbook de volta: itens confirmados geram uma lista para a Analista dar baixa manualmente no Protheus (não é arquivo de importação, ADR 0002); itens desmarcados são rejeições com motivo obrigatório, e o par Crédito-Título rejeitado nunca mais é proposto.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Cada linha do workbook tem identificador estável do item
- [ ] Execução seguinte lê as decisões do workbook e as registra no armazenamento
- [ ] Confirmação gera lista legível para baixa manual no Protheus, com Título, Sistema de origem, valor principal e Encargo
- [ ] Rejeição sem motivo é sinalizada no Resumo e não é aplicada
- [ ] Par rejeitado não volta a ser proposto em execuções futuras; o Crédito vai para a Fila
- [ ] Toda decisão registra quem, quando, evidência mostrada e regra que gerou a proposta

Spec: `.scratch/conciliacao-fase1/spec.md`
