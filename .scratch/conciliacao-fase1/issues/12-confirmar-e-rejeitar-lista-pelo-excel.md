# 12: Confirmar e rejeitar a Lista de baixa pelo Excel

**What to build:** A Lista de baixa sai no Excel com a decisão 'confirmar' pré-preenchida. Na execução seguinte, a plataforma lê o workbook de volta: itens confirmados geram uma lista para a Analista dar baixa manualmente no Protheus (não é arquivo de importação, ADR 0002); itens desmarcados são rejeições com motivo obrigatório, e o par Crédito-Título rejeitado nunca mais é proposto.

**Blocked by:** 01

**Status:** ready-for-agent

- [x] Cada linha do workbook tem identificador estável do item
- [x] Execução seguinte lê as decisões do workbook e as registra no armazenamento
- [x] Confirmação gera lista legível para baixa manual no Protheus, com Título, Sistema de origem, valor principal e Encargo
- [x] Rejeição sem motivo é sinalizada no Resumo e não é aplicada
- [x] Par rejeitado não volta a ser proposto em execuções futuras; o Crédito vai para a Fila
- [x] Toda decisão registra quem, quando, evidência mostrada e regra que gerou a proposta

Spec: `.scratch/conciliacao-fase1/spec.md`
