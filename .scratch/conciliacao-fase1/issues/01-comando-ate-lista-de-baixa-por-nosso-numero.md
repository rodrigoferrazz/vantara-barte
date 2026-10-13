# 01: Do comando à Lista de baixa por nosso número

**What to build:** Um comando lê uma pasta com a exportação do Protheus e um Extrato do Itaú do jeito que vêm e gera um workbook Excel com Resumo, Lista de baixa, Fila de exceções e Fora do escopo. Crédito com nosso número de um Título e valor exato vai para a Lista com a explicação do match; débitos vão para Fora do escopo; todo o resto vai para a Fila com um Motivo provisório. O banco e a conta de cada Extrato vêm de uma configuração que associa padrão de nome de arquivo a banco + conta. O estado fica num SQLite local. Estrutura do projeto Python e pytest entram aqui.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Rodar o comando sobre uma pasta com Protheus e Extrato Itaú gera o workbook com as quatro abas e o Resumo no topo
- [x] Liquidação com nosso número e valor exato vai para a Lista com explicação legível citando nosso número e valor
- [x] Débitos e tarifas vão para Fora do escopo
- [x] Conferência de soma: lançamentos do Extrato = Lista + Fila + Fora do escopo; se não fechar, a execução para e diz por quê
- [x] Créditos têm chave natural (banco + conta + data + valor + histórico + documento + ordinal entre idênticos do dia): reimportar período sobreposto não duplica, e duas linhas idênticas no mesmo dia viram dois Créditos
- [x] Banco e conta do Extrato vêm da configuração por nome de arquivo; a pasta não precisa de subpastas
- [x] Testes pelo ponto principal (execução da conciliação sobre pasta + SQLite temporário), com arquivos de teste próprios, sem valores da amostra no código de produção

Spec: `.scratch/conciliacao-fase1/spec.md`
