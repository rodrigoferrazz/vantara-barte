# 05: Simulador por proporções e contrato da Porta de cobrança

**What to build:** A Porta de cobrança simulada traz os Retornos como arquivos nos formatos públicos, e o simulador de pagamentos gera, a partir das Cobranças emitidas e de proporções configuráveis, Extrato e Retornos imperfeitos como a realidade, com gabarito. Um fluxo completo (emitir, simular, conciliar) é verificável contra o gabarito.

**Blocked by:** 02, 03, 04

**Status:** ready-for-agent

- [ ] Plano por proporções: em dia, atraso com multa, atraso sem Encargo, parcial em boleto autorizado e Crédito solto (Pix, TED ou depósito, com a bagunça de nome do gerador da fase 1)
- [ ] Extrato gerado nos layouts de banco já aceitos pelos adaptadores da fase 1
- [ ] Pix com txid sempre com o valor da cobrança (com ou sem multa e juros); valor a menos com identificador só em boleto parcial autorizado
- [ ] Mesma semente gera exatamente os mesmos arquivos; gabarito com destino, Título(s) e Motivo de cada Crédito
- [ ] Teste de contrato da porta: emitir duas vezes não duplica, identificadores únicos e no formato, arquivos trazidos aceitos pelos adaptadores de Retorno
- [ ] Proporções respeitadas dentro de uma tolerância em volume
- [ ] Teste ponta a ponta: nenhum item da Lista de baixa diverge do gabarito
