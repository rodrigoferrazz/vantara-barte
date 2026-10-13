# 15: Tela local de visualização, decisões e conflito com o Excel

**What to build:** A tela local no navegador vira a visualização da plataforma. Ela lê o resultado persistido da última execução, o mesmo que gerou o Excel, e mostra: o Resumo da execução; a Lista de baixa e a Fila de exceções com a explicação de cada item e o parecer da IA destacado quando houver; a Lista de cobrança separada dos Títulos em análise; o relatório de causa raiz com um gráfico simples; e Fora do escopo. Na mesma tela, a Analista confirma o lote, rejeita com motivo e resolve itens da Fila com um clique, gravando pelo mesmo caminho do Excel. Item decidido nas duas origens desde a última execução é conflito: nenhuma decisão é aplicada e o conflito aparece no Resumo e na tela. Só aparece o que a plataforma gerou, nada inventado.

**Blocked by:** 08, 09, 10, 13, 16

**Status:** ready-for-agent

- [ ] Um comando abre a tela local, sem servidor externo, sem build de frontend e sem recursos externos (funciona offline)
- [ ] A tela lê o resultado persistido da última execução e não recalcula nada; totais e itens batem com o workbook da mesma execução
- [ ] Resumo da execução no topo: lidos, recusados, resolvido sozinho, estado da IA, conta que segura a Data de referência, conflitos
- [ ] Lista de baixa e Fila mostram, por item, Crédito, Título(s), evidência, explicação e Motivo
- [ ] Itens com parecer da IA têm o parecer destacado visualmente, com a explicação e a marcação "IA indisponível" quando for o caso
- [ ] Lista de cobrança aparece separada dos Títulos em análise
- [ ] Causa raiz com gráfico de barras simples por Motivo (quantidade e valor), desenhado no servidor sem biblioteca externa, mais a agregação por Franqueado
- [ ] Sem execução, a tela diz que não há execução; lista vazia aparece como vazia; nenhum dado de exemplo ou placeholder
- [ ] Confirmar o lote, rejeitar com motivo e resolver itens da Fila gravam no mesmo armazenamento usado pela leitura do Excel
- [ ] Item decidido no Excel e na tela vira conflito, mesmo com decisões iguais, e nada é aplicado
- [ ] Testes finos via HTTP: a tela grava pelo mesmo caminho e mostra os mesmos totais do workbook; a lógica de conflito é testada no ponto principal

Spec: `.scratch/conciliacao-fase1/spec.md`
