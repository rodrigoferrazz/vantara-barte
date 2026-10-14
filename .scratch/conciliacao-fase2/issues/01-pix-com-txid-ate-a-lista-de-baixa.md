# 01: Pix com txid até a Lista de baixa

**What to build:** Com um Franqueado declarado como migrado na configuração, o comando de emissão gera um txid para cada Título em aberto dele (só Pix nesta fatia), grava o vínculo Identificador-Título no armazenamento e envia pela Porta de cobrança simulada só Título, valor, vencimento e CNPJ do Franqueado. Na conciliação seguinte, um arquivo de Pix recebidos no formato da API Pix na pasta de entrada enriquece o Crédito do Extrato com o txid (par único por conta, data e valor), e o Crédito com valor exato vai para a Lista de baixa com a explicação do identificador. Spec: `.scratch/conciliacao-fase2/spec.md`.

**Blocked by:** fase 1 concluída (`.scratch/conciliacao-fase1/issues/17-aceitacao-da-amostra-de-julho.md`)

**Status:** ready-for-human

- [x] Sem configuração de migração, nada da fase 2 executa e a suíte da fase 1 passa sem alteração
- [x] Emissão só considera Títulos em aberto de Franqueados migrados, sem Cobrança identificada e com Vencimento efetivo maior ou igual à Data de referência
- [x] txid alfanumérico de 26 a 35 caracteres, único, nunca reaproveitado
- [x] Vínculo gravado antes de chamar a porta; emitir de novo não duplica
- [x] A porta recebe só Título, valor, vencimento, CNPJ do Franqueado e os identificadores
- [x] Adaptador de Pix recebidos aceita o formato da resposta de `/pix` da API Pix, identificado pelo conteúdo, com banco e conta pela configuração por nome de arquivo
- [x] Retorno só enriquece Crédito existente, nunca cria Crédito (ADR 0001)
- [x] Crédito com txid de Título em aberto e valor exato vai para a Lista de baixa, com o tipo e a origem do identificador na explicação

## Comments

- Implementado. Testes em `tests/test_pix_com_txid.py`; decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 01"). Novo comando `emitir-cobrancas`; `[migracao]` e a `[[contas]]` do arquivo de Pix ficam comentadas no `conciliacao.toml`.
- Status `ready-for-human`: o `triage-labels.md` não tem papel de concluído; o ticket fica para revisão humana dos pontos abaixo.
- Adiantado de outros tickets por ser a mesma regra: valor fora do nosso número leva à Fila com "valor não fecha" (ticket 02), e os Retornos e as ligações ficam guardados e são retentados (parte do ticket 04), senão o Crédito perderia o txid na execução seguinte.
- Ponto em aberto: Títulos numa Possível duplicidade ainda não decidida são emitidos os dois, como a spec manda (a regra de emissão não os exclui). Isso pode cobrar duas vezes a mesma dívida; a Lista de cobrança da fase 1 os deixa de fora. Decidir se a emissão também deve deixá-los de fora.
- Ponto em aberto para o ticket 02: a spec manda o identificador desconhecido para a Fila com "Possível fonte não integrada", mas a correção "Possível fonte não integrada classificada pela Analista" diz que o motor não atribui esse Motivo sozinho. Neste ticket o identificador desconhecido segue o caminho da fase 1.
- Decisão do usuário sobre o ponto em aberto da Possível duplicidade: a emissão exclui os Títulos envolvidos em Possível duplicidade ainda não decidida, com o mesmo critério e o mesmo código da Lista de cobrança; decidida a duplicidade, eles voltam à emissão. Ver "Correção: emissão de Pix exclui Títulos em Possível duplicidade não decidida" em `docs/decisoes-implementacao.md`.
