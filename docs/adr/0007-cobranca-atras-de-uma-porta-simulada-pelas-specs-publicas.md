# Cobrança atrás de uma porta, simulada pelas especificações públicas

Não há acesso a um sistema de pagamento real, então a emissão de Cobrança identificada e a leitura do Retorno de cobrança ficam atrás de uma única interface, e a simulação é só um adaptador dela; quando existir o sistema real, troca-se só esse adaptador. A simulação segue a API Pix do Banco Central (`bacen/pix-api`, cobrança com vencimento `cobv` e Pix recebidos) e o retorno CNAB 240 da FEBRABAN (Segmentos T e U), em vez de um formato inventado, para que o adaptador real seja uma variação conhecida e não uma reescrita. As imperfeições simuladas (parcial, atraso com multa, valor a menos, Crédito solto) ficam em proporções configuráveis e respeitam a spec: Pix com txid sempre chega com o valor da cobrança, valor a menos com identificador só vem por boleto com pagamento parcial autorizado, e no Pix só acontece no Crédito solto.

## Consequences

Cada banco real tem variações sobre o CNAB 240 (e o CNAB 400 nem é padrão FEBRABAN), então cada banco entra como um adaptador próprio, como os Extratos na fase 1.
