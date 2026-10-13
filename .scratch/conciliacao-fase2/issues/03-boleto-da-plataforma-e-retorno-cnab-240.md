# 03: Boleto da plataforma e retorno CNAB 240

**What to build:** Título sem nosso número no Protheus (por exemplo, do Omie) passa a receber boleto e Pix na emissão; Título com nosso número do Protheus continua só com Pix. O retorno CNAB 240 FEBRABAN na pasta de entrada enriquece o Crédito, e o boleto da plataforma é resolvido como um boleto do Protheus.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Nosso número gerado dentro da faixa configurada do beneficiário por conta, único, nunca reaproveitado
- [ ] Nenhum Título fica com dois boletos registrados
- [ ] Adaptador CNAB 240 lê cabeçalhos de arquivo e lote e Segmentos T e U; só movimento de liquidação vira Retorno, os demais são ignorados
- [ ] Boleto da plataforma liquidado com nosso número no Extrato vai para a Lista com a mesma regra de valor do nosso número da fase 1
- [ ] Parcial de boleto com pagamento parcial autorizado vai para a Fila como Diferença a menor, com o Título apontado
- [ ] Multa e juros do Segmento U aparecem separados na explicação
- [ ] A regra de nosso número do Protheus da fase 1 continua igual
