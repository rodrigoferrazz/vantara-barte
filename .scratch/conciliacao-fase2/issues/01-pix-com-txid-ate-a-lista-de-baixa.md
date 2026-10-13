# 01: Pix com txid até a Lista de baixa

**What to build:** Com um Franqueado declarado como migrado na configuração, o comando de emissão gera um txid para cada Título em aberto dele (só Pix nesta fatia), grava o vínculo Identificador-Título no armazenamento e envia pela Porta de cobrança simulada só Título, valor, vencimento e CNPJ do Franqueado. Na conciliação seguinte, um arquivo de Pix recebidos no formato da API Pix na pasta de entrada enriquece o Crédito do Extrato com o txid (par único por conta, data e valor), e o Crédito com valor exato vai para a Lista de baixa com a explicação do identificador. Spec: `.scratch/conciliacao-fase2/spec.md`.

**Blocked by:** fase 1 concluída (`.scratch/conciliacao-fase1/issues/17-aceitacao-da-amostra-de-julho.md`)

**Status:** ready-for-agent

- [ ] Sem configuração de migração, nada da fase 2 executa e a suíte da fase 1 passa sem alteração
- [ ] Emissão só considera Títulos em aberto de Franqueados migrados, sem Cobrança identificada e com Vencimento efetivo maior ou igual à Data de referência
- [ ] txid alfanumérico de 26 a 35 caracteres, único, nunca reaproveitado
- [ ] Vínculo gravado antes de chamar a porta; emitir de novo não duplica
- [ ] A porta recebe só Título, valor, vencimento, CNPJ do Franqueado e os identificadores
- [ ] Adaptador de Pix recebidos aceita o formato da resposta de `/pix` da API Pix, identificado pelo conteúdo, com banco e conta pela configuração por nome de arquivo
- [ ] Retorno só enriquece Crédito existente, nunca cria Crédito (ADR 0001)
- [ ] Crédito com txid de Título em aberto e valor exato vai para a Lista de baixa, com o tipo e a origem do identificador na explicação
