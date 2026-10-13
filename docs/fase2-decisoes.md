# Fase 2 - Cobrança identificada (rascunho de decisões)

Base para a spec da fase 2. Termos já estão no `CONTEXT.md` (seção Cobrança) e as decisões de arquitetura nos ADRs 0001 (Retorno de cobrança só enriquece), 0007 (porta e simulação pelas specs públicas) e 0008 (vínculo Identificador-Título na plataforma). A numeração abaixo é estável porque a spec da fase 1 cita as decisões 5 e 10. Spec da fase 2 em `.scratch/conciliacao-fase2/spec.md`.

## Objetivo

A fase 1 trata o sintoma (Crédito sem identificação). A fase 2 ataca a causa: cada Título passa a ter uma cobrança com identificador próprio (Pix com txid e boleto com nosso número), para que o pagamento já chegue dizendo qual Título paga. O entregável principal é mostrar o impacto: antes e depois em julho e nos dados sintéticos de 1.900 Títulos.

## Pesquisa: as especificações públicas servem para a simulação

- **API Pix do Banco Central** (`github.com/bacen/pix-api`, OpenAPI 3.0, Apache 2.0, v2.10.0). Cobre `cobv` (cobrança com vencimento, com multa, juros, desconto e devedor por CNPJ), `/pix` (Pix recebidos com `endToEndId`, `txid`, `valor`, `componentesValor`), webhook de recebimento e já inclui Pix Automático (`/rec`, `/cobr`). O `txid` é escolhido pelo recebedor (`PUT /cobv/{txid}`, `[a-zA-Z0-9]{26,35}`). Ressalva: a spec descreve a interface entre recebedor e seu PSP, não o Extrato.
- **CNAB 240 FEBRABAN** (público via leiaute dos bancos, por exemplo Banrisul v10.3). O retorno de cobrança tem Segmento T (nosso número) e U (valor pago, acréscimos de juros e multa, data do crédito). Ressalvas: cada banco tem variações sobre o padrão, e o CNAB 400 não é padronizado pela FEBRABAN. A simulação segue o 240 puro e o banco real entra como outro adaptador.

## Decisões

1. **Simulação isolada atrás de uma porta.** O resto da plataforma só conhece uma interface de cobrança (emitir cobrança, ler retornos). O simulador é um adaptador dessa porta; o sistema real substitui só ele.
2. **Saída para emissão é mínima:** Título (Sistema de origem + documento), valor, vencimento e CNPJ do Franqueado.
3. **A plataforma gera os identificadores e guarda o vínculo.** txid e nosso número são criados pela plataforma antes da emissão (a API Pix permite txid do recebedor; nosso número sai da faixa do beneficiário). O vínculo identificador-Título fica no armazenamento da plataforma; o Protheus continua só leitura.
4. **ADR 0001 vale para a fase 2.** Crédito continua nascendo só do Extrato. Retorno CNAB e Pix recebidos só enriquecem um Crédito existente. Ligação por conta + data do crédito + valor; sem par ou com mais de um par, não enriquece e o Crédito segue o caminho da fase 1. Retorno sem Crédito no Extrato não cria Crédito.
5. **Mesmo motor, mesma regra de valor.** Identificador da cobrança é evidência do mesmo nível do nosso número na fase 1: valor exato ou dentro do Encargo vai para a Lista de baixa; fora disso vai para a Fila de exceções com o motivo de valor. Identificador de Título inexistente ou já baixado vai para a Fila.
6. **Pagamento identificado não ensina Pagador conhecido.** Quem pagou o QR ou o boleto não vira Pagador conhecido automaticamente; continua valendo que só a confirmação da Analista cria o vínculo.
7. **Imperfeições configuráveis e reproduzíveis.** Proporções de pagamento parcial, atraso com multa, valor a menos e Crédito solto ficam em configuração, com semente fixa.
8. **Encargo na simulação.** Multa de 2% (assumida na fase 1) e juros parametrizáveis. Continua ponto aberto do contrato.
9. **Causa raiz vira ordem de migração.** O ranking considera só os motivos que a cobrança identificada resolve (sem identificação do pagador, nome ambíguo, mais de uma combinação, pagador provável primeira vez). Crédito sem título em aberto, Possível duplicidade e Possível fonte não integrada não entram, porque identificador não resolve.
10. **Fase 1 intocada.** Sem retorno de cobrança, o motor dá exatamente o resultado da fase 1; a suíte da fase 1 roda sem alteração.
11. **Próximo passo (só README):** conta virtual por Franqueado e Pix Automático para royalty, este já coberto pela mesma spec (`/rec`, `/cobr`).
12. **Boleto existente é mantido.** Título com nosso número do Protheus fica com esse boleto e a plataforma emite só o Pix (txid). Título sem nosso número (Omie, por exemplo) ganha boleto e Pix da plataforma. Nenhum Título fica com dois boletos registrados.
13. **Antes e depois com o mesmo dinheiro, em faixa de adesão.** Em julho, os Créditos reais (valor, data, Franqueado) são mantidos; a simulação só decide se cada um chega com identificador, conforme a taxa de Crédito solto. O resultado é mostrado para uma faixa de adesão (por exemplo 50%, 80%, 95%), porque "chegariam identificados" é premissa, não previsão. Nos 1.900 Títulos sintéticos vale o mesmo método, com o gabarito do gerador como fonte da verdade; o simulador por proporções fica para o fluxo ponta a ponta.
14. **Imperfeições seguem a spec.** Pix com txid (cobv) chega sempre com o valor da cobrança, com ou sem multa. Valor a menos com identificador só vem por boleto com pagamento parcial autorizado (campo 42.3P do CNAB 240). No Pix, valor a menos só acontece no Crédito solto.
15. **Migração em ondas pelo ranking.** A configuração diz quais Franqueados migraram. O antes e depois mostra o total com todos migrados e quanto a Fila cai a cada onda do ranking de causa raiz.
