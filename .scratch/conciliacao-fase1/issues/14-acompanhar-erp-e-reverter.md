# 14: Acompanhar o ERP e reverter decisões

**What to build:** A cada execução, a plataforma compara a fotografia de Títulos com a anterior e com as decisões (ADR 0004): Título proposto que sumiu foi baixado e sai de tudo; não proposto que sumiu é Baixado por fora; baixa de Título diferente do proposto é Divergência de baixa e volta para a Fila; confirmado e ainda aberto fica Aguardando baixa no ERP. O Saldo segue o ERP quando o valor muda e as decisões quando não muda. A Analista pode reverter uma confirmação.

**Blocked by:** 12

**Status:** ready-for-agent

- [x] Título proposto e confirmado que some da exportação sai de todas as saídas
- [x] Título não proposto que some é registrado como Baixado por fora
- [x] Título diferente do proposto baixado gera Divergência de baixa e o caso volta para a Fila
- [x] Confirmado e ainda aberto aparece como Aguardando baixa no ERP e fica fora da cobrança
- [x] Valor que muda entre exportações vira o Saldo sem descontar de novo as decisões; valor igual tem Saldo calculado pelas decisões
- [x] Reversão com Título ainda aberto volta o caso para a Fila
- [x] Reversão com Título já sumido marca Estorno necessário no ERP até ele reaparecer
- [x] Reversão desfaz o Pagador conhecido aprendido naquela decisão

Spec: `.scratch/conciliacao-fase1/spec.md`
