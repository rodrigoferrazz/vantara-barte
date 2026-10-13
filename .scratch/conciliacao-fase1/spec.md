# Spec: Conciliação de contas a receber, fase 1

Status: ready-for-agent

Glossário em `CONTEXT.md`. Decisões de arquitetura em `docs/adr/0001` a `0006`. Rascunho da fase 2 em `docs/fase2-decisoes.md` (relevante para os pontos de extensão).

## Problem Statement

A Analista de conciliação da Vantara passa mais da metade do mês tentando descobrir de quem é cada Crédito que entra nas 4 contas bancárias: Pix com nome cortado, TED sem referência, depósito não identificado, boleto liquidado por valor diferente. Os Títulos de 210 Franqueados estão espalhados em sistemas nunca integrados (Protheus na operação principal, Omie na unidade Norte, planilhas numa terceira unidade), com nomes escritos de formas diferentes para o mesmo Franqueado.

Enquanto um Crédito não é identificado, o Título continua em aberto: a cobrança liga para Franqueado que já pagou, o DSO fica em 62 dias contra 41 do contrato e o fechamento leva 12 dias úteis. O Protheus só permite leitura e exportação, e nenhum dado pode sair do ambiente do cliente.

## Solution

Uma plataforma local, em Python, executada por um comando que lê uma pasta com as exportações do Protheus, do Omie e os Extratos bancários do jeito que vêm, sem limpeza manual. Ela guarda estado entre execuções num arquivo local e entrega à Analista, todo dia:

1. **Resumo**: o que foi lido, o que foi recusado e por quê, quanto foi resolvido sozinho, se a IA estava funcionando, que banco está segurando a Data de referência, e alerta se a parte automática caiu muito.
2. **Lista de baixa**: Propostas de baixa prontas para confirmar, cada uma com a explicação do match.
3. **Fila de exceções**: o que precisa de decisão dela, com sugestão, evidência e Motivo de não identificação.
4. **Lista de cobrança**: quem realmente deve na Data de referência, para o time de cobrança.
5. **Relatório de causa raiz**: por que cada Crédito não foi identificado e quais Franqueados concentram o problema.
6. **Fora do escopo**: lançamentos que não são Crédito de Franqueado.

O que dá para resolver com regra (nosso número, CNPJ, valor, soma de Títulos, Encargo) é resolvido com regra. A LLM local (Ollama) só dá parecer quando o nome do Extrato não é Nome por prefixo de nenhum nome do Franqueado. A plataforma nunca dá baixa: a Analista confirma (por Excel ou por uma tela local no navegador) e baixa no Protheus, e a plataforma acompanha pela exportação seguinte.

## User Stories

### Entrada de arquivos

1. As a Analista de conciliação, I want to run a single command pointing at a folder of exported files, so that I get all outputs without preparing anything by hand.
2. As a Analista de conciliação, I want the platform to read the Protheus export exactly as it comes (semicolon separator, comma decimal, pt-BR dates), so that I never clean files before running.
3. As a Analista de conciliação, I want the platform to read the Omie export exactly as it comes (comma separator, dot decimal, ISO dates, CNPJ without punctuation, upper-case names), so that the unidade Norte enters the same reconciliation.
4. As a Analista de conciliação, I want the platform to read the Extrato of each bank in its own layout, so that all 4 accounts are reconciled together.
5. As a Analista de conciliação, I want a file with an unknown layout, an unexpected column, a strange format or an unknown bank to be refused on its own with the reason, so that one bad file never blocks the rest.
6. As a Analista de conciliação, I want the platform to never guess a layout, so that I can trust nothing was misread silently.
7. As a Analista de conciliação, I want re-importing an Extrato with an overlapping period to not duplicate Créditos, so that I can export generous date ranges without worrying.
8. As a Analista de conciliação, I want two identical Créditos on the same day (same value, same histórico) to be kept as two Créditos, so that legitimate repeated payments are not lost.
9. As a developer, I want each Sistema de origem and each bank to be a separate adapter, so that the planilha of the third unit and the other banks can be added later without touching the matching engine.
9a. As a Analista de conciliação, I want a configuration that says which bank and account each Extrato file belongs to by its file name, so that the folder works exactly as it comes, without moving files into subfolders.

### Identificação do Franqueado

10. As a Analista de conciliação, I want Títulos from Protheus and Omie to be linked to the same Franqueado by the raiz do CNPJ, so that a Franqueado with names written differently in each system is treated as one.
11. As a Analista de conciliação, I want every name a Franqueado has in any Sistema de origem to count as one of its names, so that an Extrato name that is a prefix of any of them is recognized.
12. As a Analista de conciliação, I want a Crédito whose histórico carries a CNPJ or CPF of a Pagador conhecido to be identified by it, including the CNPJ on the Franqueado's own Títulos, so that payments with a document number are resolved by rule.
13. As a Analista de conciliação, I want CNPJs of filiais, CPFs of sócios and truncated Extrato names that I confirmed to become Pagadores conhecidos, so that the same case is resolved by rule next time.

### Regras de match

14. As a Analista de conciliação, I want a liquidação with a nosso número matching a Título and value exact or within the Encargo to go to the Lista de baixa, so that boleto payments need no investigation.
15. As a Analista de conciliação, I want a Crédito from an identified Pagador conhecido whose value is a Valor único among that payer's open Títulos to go to the Lista de baixa, so that identified Pix and TED are resolved by rule.
16. As a Analista de conciliação, I want a Crédito from an identified payer that equals the exact sum of a single combination of that Franqueado's open Títulos to go to the Lista de baixa with the sum shown, so that one payment covering several Títulos is resolved by rule.
17. As a Analista de conciliação, I want a Crédito whose payer was matched only by name similarity and never confirmed to go to the Fila de exceções, even when the value or sum closes, so that nothing enters the Lista on an unconfirmed name.
18. As a Analista de conciliação, I want a Crédito matched only by value to go to the Fila with the suggested Título, so that I decide unidentified deposits.
19. As a Analista de conciliação, I want a Crédito below the Título value (Diferença a menor, including partial payment of one Título) to go to the Fila, so that discounts, retentions and partials are always my decision.
20. As a Analista de conciliação, I want a late payment that came with only the original value to be treated as on time, with the explanation saying the Encargo was not paid, so that it is not mistaken for a Diferença a menor.
21. As a Analista de conciliação, I want a Crédito above the Título value plus the expected Encargo (Valor a maior) to go to the Fila, so that overpayments are investigated.
22. As a Analista de conciliação, I want late payments with multa and juros within the contract Encargo and tolerance to go to the Lista with principal and Encargo shown separately, so that I know how much was revenue from charges.
23. As a Analista de conciliação, I want Encargo and lateness to be computed from the Vencimento efetivo (next business day when the due date falls on a weekend or national bank holiday), so that nobody is charged multa for paying on the first business day.
24. As a Analista de conciliação, I want several Créditos paying several Títulos together (N:M) to go to the Fila, so that complex combinations are never decided by the machine.
25. As a Analista de conciliação, I want a sum where more than one combination of Títulos closes the value to go to the Fila, so that the platform never picks between equally valid options.
26. As a Analista de conciliação, I want sums to be searched only among open Títulos of the same Franqueado, so that the search stays fast with 1.900 Títulos and never mixes Franqueados.
27. As a Analista de conciliação, I want a Crédito from an identified Franqueado with no candidate Título to go to the Fila as Crédito sem título em aberto and be retried on every new import, so that an advance payment matches when its Título appears.
28. As a Analista de conciliação, I want Títulos of the same Franqueado, value and due date in different Sistemas de origem to be flagged as Possível duplicidade entre sistemas in the Fila, so that I decide whether they are the same debt.
29. As a Analista de conciliação, I want debits and bank fees to go to Fora do escopo, so that they never pollute the Fila.

### IA local

30. As a Analista de conciliação, I want the LLM to be called only when the Extrato name is not a Nome por prefixo of any of the candidate Franqueado's names (abbreviations, inverted words, missing words), so that the AI is used only where rules cannot decide.
31. As a Analista de conciliação, I want the LLM to say whether the name belongs to that Franqueado and explain why, so that I decide with a readable justification.
32. As a Analista de conciliação, I want every item that went through the LLM to go to the Fila with its opinion, never to the Lista, so that the AI never causes a baixa by itself.
33. As a Analista de conciliação, I want an item the LLM rejected to stay in the Fila with the value suggestion and motive "sem identificação do pagador", so that I still see the candidate.
34. As a Analista de conciliação, I want the run to continue when Ollama is down, sending those items to the Fila marked "IA indisponível" and showing it in the Resumo, so that an AI outage never stops reconciliation.
35. As the client, I want the LLM to run locally via Ollama with no data leaving the environment, so that the data residency constraint holds.
36. As a developer, I want the model and prompt version recorded with every LLM opinion, so that decisions are auditable and model changes can be compared.

### Fila de exceções e causa raiz

37. As a Analista de conciliação, I want every Fila item to have exactly one Motivo de não identificação, so that the causa raiz report adds up to 100%.
38. As a Analista de conciliação, I want the motives to be: sem identificação do pagador; nome ambíguo; valor não fecha; Crédito sem título em aberto; mais de uma combinação possível; Possível duplicidade entre sistemas; Possível fonte não integrada; pagador provável, primeira vez, so that the categories are stable month to month.
39. As a Analista de conciliação, I want overlapping motives resolved by a fixed precedence (valor não fecha, then Crédito sem título em aberto, then nome ambíguo, then pagador provável, primeira vez), so that the same case always gets the same motive.
40. As a Analista de conciliação, I want "pagador provável, primeira vez" used only when the item is in the Fila solely because the name was not yet confirmed, so that this motive measures what learning will fix.
41. As a gestor financeiro, I want the causa raiz report aggregated by Franqueado, by bank and by channel (Pix, TED, boleto, depósito), so that I know which Franqueados to approach first.
42. As a Analista de conciliação, I want each Fila item to show the suggested Título(s), the evidence found, what is missing and the LLM opinion when there is one, so that I decide quickly.

### Lista de cobrança

43. As a time de cobrança, I want a list of Títulos overdue on the Data de referência with Saldo open and no candidate Crédito, so that I never call a Franqueado who already paid.
44. As a Analista de conciliação, I want the Data de referência to be the earliest of the last dates across the 4 Extratos, not the computer's date, so that a late export never sends a payer to cobrança.
45. As a Analista de conciliação, I want the Resumo to show which bank is holding the Data de referência back, so that I know which export to refresh.
46. As a time de cobrança, I want Títulos with a candidate Crédito in the Fila shown apart as "em análise", so that I know they are not to be called yet.
47. As a time de cobrança, I want Títulos flagged as Possível duplicidade kept out of cobrança, so that nobody is charged twice.
48. As a time de cobrança, I want boletos within 2 business days after the Vencimento efetivo kept out of cobrança, so that clearing time is respected.
49. As a time de cobrança, I want only the Saldo of a Título with a confirmed partial payment to appear, so that the amount charged is correct.

### Decisões da Analista

50. As a Analista de conciliação, I want to confirm the Lista de baixa as a batch with everything pre-selected and the option to unselect items, so that the common case takes one action.
51. As a Analista de conciliação, I want an unselected Lista item to count as a rejection with a mandatory reason, so that every rejection is explained.
52. As a Analista de conciliação, I want a rejected Crédito-Título pair to never be proposed again, so that I don't see the same wrong suggestion every day.
53. As a Analista de conciliação, I want a confirmed batch to produce a list for me to do the baixa manually in Protheus, so that I have everything in one place without the platform ever writing to Protheus.
54. As a Analista de conciliação, I want to resolve a Fila item by choosing the Título(s), classifying a Crédito sem título (antecipação, devolução, erro), marking Conciliado fora, or deciding a duplicidade, so that every kind of exception has a resolution.
55. As a Analista de conciliação, I want a confirmation that identified the payer by name to create a Pagador conhecido with one confirmation, so that the next Crédito with that histórico goes to the Lista when the value is unique.
56. As a Analista de conciliação, I want a histórico confirmed for two different Franqueados to stop being a Pagador conhecido, so that ambiguous names always go back to the Fila.
57. As a Analista de conciliação, I want value or sum matches to never become rules, so that the platform only learns who pays, not how much.
58. As a Analista de conciliação, I want to mark a duplicidade as "mesma dívida" choosing the official Título, so that the other one leaves cobrança permanently and appears in a list to be cancelled at the source.
59. As a Analista de conciliação, I want to attribute a Crédito to a Franqueado and a free reference as Conciliado fora, so that payments of the unintegrated unit leave the Fila and still count in the report.
60. As a Analista de conciliação, I want to revert any confirmation, so that my mistakes are fixable.
61. As a Analista de conciliação, I want a reverted confirmation whose Título already left the ERP export to be flagged Estorno necessário no ERP until it reappears, so that I don't forget to fix Protheus.
62. As a Analista de conciliação, I want reverting a confirmation to also undo the Pagador conhecido learned from it, so that a wrong decision doesn't keep teaching the engine.
63. As a Analista de conciliação, I want to work in an Excel workbook with one sheet per output, record decisions in it and have the next run read them back, so that I can work in the tool I already use.
64. As a Analista de conciliação, I want a simple local browser screen showing everything with one-click confirm or reject, so that I can work faster than in Excel.
64a. As a Analista de conciliação, I want the local screen to be the platform's visualization, reading the same stored data of the latest execution as the Excel, so that both always show the same thing.
64b. As a Analista de conciliação, I want the screen to show the Resumo of the execution, the Lista de baixa and the Fila de exceções with the explanation of each item, so that I decide without opening anything else.
64c. As a Analista de conciliação, I want the LLM opinion highlighted on the items that have one, so that I see at a glance which suggestions came from the AI.
64d. As a time de cobrança, I want the screen to show the Lista de cobrança separate from the Títulos em análise, so that nobody calls a Franqueado whose payment is being analyzed.
64e. As a gestor financeiro, I want the causa raiz report on the screen with a simple chart, so that I see which Motivos and Franqueados concentrate the problem.
64f. As a Analista de conciliação, I want the screen to show only what the platform generated, with explicit empty states and no placeholder or invented data, so that I can trust every number on it.
65. As a Analista de conciliação, I want Excel and the screen to read and write decisions in the same place, so that both stay consistent.
66. As a Analista de conciliação, I want an item decided both in Excel and on the screen to be reported as a conflict and not applied, so that the platform never picks one of my decisions on its own.
67. As an auditor, I want every decision to record who, when, the evidence shown, the rule that produced the proposal and, if applicable, the model and prompt version, so that every baixa can be traced.

### Acompanhamento do ERP

68. As a Analista de conciliação, I want a proposed Título that disappears from the next export to be considered baixado and leave every list, so that I don't see work already done.
69. As a Analista de conciliação, I want a confirmed Título still open in the export to show as Aguardando baixa no ERP, out of cobrança, so that I remember to do the baixa.
70. As a Analista de conciliação, I want a Título that disappears without any proposal to be recorded as Baixado por fora, so that I know someone else settled it.
71. As a Analista de conciliação, I want a baixa of a Título different from the one proposed to raise a Divergência de baixa and send the case back to the Fila, so that ERP mistakes are caught.
72. As a Analista de conciliação, I want the Saldo of a Título to follow the ERP value when it changes between exports and to be computed from my confirmed decisions when it doesn't, so that partial payments are never discounted twice.

### Segurança da execução

73. As a Analista de conciliação, I want each run to check that the sum of every Extrato lançamento equals Lista de baixa plus Fila de exceções plus Fora do escopo, and to stop if it doesn't, so that no money is ever lost between lists.
74. As a Analista de conciliação, I want the Resumo to warn me when the share resolved automatically drops sharply compared with the previous run, so that I notice a broken export or rule early.
75. As a Analista de conciliação, I want the Resumo at the top of every output, so that I see the health of the run before the lists.

### Métricas

76. As the developer, I want a report of rejection rate by evidence type and of LLM first-suggestion accuracy, so that I decide which rules to tighten.
77. As the developer, I want rules to never be demoted automatically, so that behavior changes only by deliberate decision.

### Dados de teste

78. As the developer, I want a seeded synthetic data generator producing Protheus, Omie and 4-bank Extrato files with the same mess as the sample, so that the platform is tested on data it has never seen.
79. As the developer, I want the generator to produce about 1.900 Títulos per month across 4 banks with configurable proportions of each case (truncated, abbreviated and inverted names, CNPJ in histórico, sums, partials, multa, missing multa, duplicidade between systems, unidentified deposits, advance payments, debits), so that volume and variety match reality.
80. As the developer, I want the generator to output the expected destination of every Crédito, so that tests measure precision without hand labeling.
81. As the developer, I want no name, value or invoice number from the sample written in production code, so that the platform cannot be overfitted to the sample.

## Implementation Decisions

### Forma geral

- Python, executado localmente sem servidor. Estado em um arquivo SQLite. LLM via Ollama na mesma máquina (ADR 0006).
- Dois comandos de linha: um que executa a conciliação sobre uma pasta de entrada e gera as saídas; outro que abre a tela local no navegador. Ambos usam o mesmo armazenamento.
- Execução em etapas, nesta ordem: ler e validar arquivos (recusando por arquivo); aplicar decisões registradas desde a última execução (Excel e tela), detectando conflitos; atualizar o estado com o que mudou no ERP; rodar o motor; fazer a conferência de soma (para se falhar); gerar saídas e Resumo.

### Módulos

1. **Adaptadores de fonte.** Um por layout: exportação Protheus, exportação Omie, Extrato de cada banco (hoje só o layout Itaú da amostra). Cada um declara o layout exato que aceita (colunas, separador, formato de data e número) e devolve Títulos ou lançamentos normalizados, ou uma recusa com motivo legível. Nenhum adaptador tenta inferir layout. A identificação de qual adaptador serve um arquivo é pelo conteúdo (cabeçalho), não pelo nome do arquivo. Interface estável para a planilha da terceira unidade e os outros bancos entrarem depois. O banco e a conta de cada Extrato vêm de uma configuração que associa padrões de nome de arquivo a banco + conta; a pasta é lida como vem, sem subpastas. Extrato cujo nome não casa com nenhum padrão é recusado com motivo.
2. **Normalização.** Dinheiro em centavos inteiros; CNPJ só dígitos com raiz de 8; nomes em maiúsculas, sem acento e com pontuação e símbolos normalizados para a comparação de prefixo. Regras de normalização não contêm nenhum nome da amostra.
3. **Calendário.** Feriados bancários nacionais, Vencimento efetivo e contagem de dias úteis. Feriado municipal fora.
4. **Parâmetros de Encargo.** Multa percentual, juros ao mês pro rata e tolerância fixa em configuração, com multa padrão de 2% (premissa ainda não confirmada pelo contrato).
5. **Motor de conciliação.** Módulo puro e determinístico, o coração do sistema. Recebe Títulos abertos com Franqueado, Créditos novos e vivos, Pagadores conhecidos, pares rejeitados, Data de referência, calendário, parâmetros de Encargo e um Parecerista de nome. Devolve, para cada Crédito, um destino (Lista de baixa, Fila de exceções, Fora do escopo), os Títulos propostos, a evidência, a explicação legível e, na Fila, um Motivo de não identificação; além dos itens de Título da Fila (Possível duplicidade) e da Lista de cobrança com os "em análise". A evidência é um conjunto aberto de tipos (nosso número, CNPJ/CPF, Pagador conhecido, nome por prefixo, parecer de LLM, só valor), para que a fase 2 acrescente "identificador de cobrança" no mesmo nível do nosso número sem mudar o resto (`docs/fase2-decisoes.md`, decisões 5 e 10).
6. **Parecerista de nome.** Porta com uma operação: dado o nome do Extrato e os nomes de um Franqueado candidato, responde sim/não e uma explicação, ou "indisponível". Implementação Ollama com saída estruturada, modelo de 3 a 4B quantizado (cabe no M2 de 8 GB). A resposta registra modelo e versão do prompt. A LLM só vê o Franqueado já filtrado por valor; nunca escolhe valor nem Título.
7. **Armazenamento.** SQLite com: Créditos (chave natural: banco + conta + data + valor + histórico + documento + ordinal entre idênticos do dia), fotografias de Títulos por execução, Franqueados e seus nomes por Sistema de origem, Pagadores conhecidos (com origem na decisão que os criou), Propostas, decisões (com autor, momento, evidência, regra, modelo e prompt), pares rejeitados, marcações de duplicidade, execuções (com totais, para o alerta de queda e as métricas).
8. **Acompanhamento do ERP.** Compara a fotografia atual de Títulos com a anterior e com as Propostas: Título proposto que sumiu é baixado; não proposto que sumiu é Baixado por fora; baixa de Título diferente do proposto é Divergência de baixa e volta para a Fila; mudança de valor vira o novo Saldo; confirmado e ainda aberto é Aguardando baixa no ERP; revertido e já sumido é Estorno necessário no ERP (ADR 0004).
9. **Saídas.** O resultado de cada execução é persistido no armazenamento e é a única origem das saídas: o workbook e a tela local leem dele. Um workbook Excel com abas Resumo, Lista de baixa, Fila de exceções, Lista de cobrança (com "em análise" à parte), Causa raiz, Fora do escopo e Arquivos recusados, mais a lista do lote confirmado para a Analista dar baixa manualmente no Protheus (não é arquivo de importação: importar seria escrever no Protheus, ADR 0002). Cada linha tem um identificador estável do item para a leitura de volta. A Lista de baixa vem com a decisão "confirmar" pré-preenchida.
10. **Registro de decisões.** Um único caminho de escrita usado pelo leitor do Excel e pela tela. Uma decisão sobre um item que já tem decisão de outra origem desde a última execução é marcada como conflito, nenhuma das duas é aplicada e o conflito aparece no Resumo e na tela.
11. **Tela local.** Servidor HTTP local leve, sem build de frontend e sem recursos externos (funciona offline), que é a visualização da plataforma: lê o resultado persistido da última execução, o mesmo que gerou o Excel, sem recalcular nada. Mostra o Resumo, a Lista de baixa e a Fila com a explicação de cada item e o parecer da LLM destacado quando houver, a Lista de cobrança separada dos Títulos em análise, a causa raiz com um gráfico de barras simples (desenhado no servidor, sem biblioteca externa) e Fora do escopo. Permite confirmar o lote, rejeitar com motivo e resolver itens da Fila com um clique. Nenhum dado inventado: sem execução, a tela diz que não há execução; lista vazia aparece como vazia.
12. **Gerador sintético.** Com semente fixa e proporções em configuração. Produz os arquivos nos mesmos layouts dos adaptadores e um gabarito com o destino esperado de cada Crédito.

### Regras do motor (resumo normativo)

- Lista de baixa: nosso número + valor exato ou dentro do Encargo; CNPJ/CPF de Pagador conhecido + Valor único; nome igual a Pagador conhecido confirmado + Valor único; 1:N com pagador identificado por CNPJ/CPF ou por Pagador conhecido já confirmado, soma exata e uma única combinação, mesmo Franqueado. Atraso pago pelo valor original entra como Encargo não pago.
- Fila de exceções: nome só por semelhança nunca confirmado (inclusive 1:N); só valor; Diferença a menor; N:1 parcial; N:M; mais de uma combinação; Valor a maior; Crédito sem título em aberto; tudo que passou pela LLM; Possível duplicidade (item de Título, fora da cobrança).
- LLM: só quando o nome não é Nome por prefixo de nenhum nome do Franqueado em nenhum Sistema de origem, depois do filtro por valor. Negativa vira "sem identificação do pagador"; indisponível vira "IA indisponível".
- Um Motivo por item, com a precedência das histórias 39 e 40.
- Lista de cobrança: vencidos pelo Vencimento efetivo na Data de referência, com Saldo, sem Crédito candidato confirmado ou em análise, sem duplicidade, fora da janela de 2 dias úteis de compensação do boleto.
- Data de referência: a menor entre as últimas datas dos Extratos.
- Conferência de soma: lançamentos do Extrato = Lista + Fila + Fora do escopo; senão a execução para sem gerar saídas parciais como se fossem completas (ADR 0005).
- A plataforma nunca dá baixa (ADR 0002) e a LLM nunca alimenta a Lista (ADR 0003).

## Testing Decisions

- Bons testes exercitam comportamento externo: arquivos entram, saídas e estado saem. Nenhum teste depende de funções internas do motor, da forma das tabelas SQLite ou do texto exato do prompt.
- **Ponto de teste principal: a execução da conciliação.** Recebe uma pasta de arquivos, o armazenamento (SQLite temporário) e um Parecerista de nome; devolve o resultado completo (Resumo, Lista de baixa, Fila de exceções, Lista de cobrança, Causa raiz, Fora do escopo, Arquivos recusados). Quase todos os testes passam por aqui:
  - teste de aceitação com a amostra de julho (`data/`), comparando com o resultado validado pelo usuário. Os valores esperados vivem apenas na fixture do teste, nunca no código de produção;
  - testes de volume com o gerador sintético: nenhum item da Lista de baixa diverge do gabarito (precisão de 100% na Lista), a conferência de soma sempre fecha, todo item da Fila tem exatamente um Motivo;
  - cenários de várias execuções seguidas: decisões lidas do Excel, Pagador conhecido aprendido e usado na execução seguinte, par rejeitado não reproposto, reversão, Baixado por fora, Divergência de baixa, mudança de Saldo, Crédito sem título casando com Título novo, conflito entre Excel e tela, alerta de queda da parte automática;
  - robustez: arquivo com coluna diferente, formato estranho e banco desconhecido são recusados um a um enquanto o resto é processado; reimportação sobreposta não duplica Créditos.
- **Ponto auxiliar 1: Parecerista de nome.** Os testes usam uma implementação falsa e determinística. Um único teste de integração chama o Ollama de verdade e é pulado quando ele não está rodando.
- **Ponto auxiliar 2: tela local via HTTP.** Testes finos contra o mesmo armazenamento: a tela grava decisões pelo mesmo caminho do Excel, e os totais e itens que ela mostra são os mesmos do workbook da mesma execução. A lógica de conflito é testada no ponto principal.
- A suíte da fase 1 precisa continuar passando sem alteração quando a fase 2 for implementada (`docs/fase2-decisoes.md`, decisão 10).
- Não há testes anteriores no repo; pytest como runner.

## Out of Scope

- Fase 2: cobrança identificada, txid, simulação de emissão (rascunho em `docs/fase2-decisoes.md`).
- Leitura da planilha da terceira unidade; seus Créditos aparecem como Possível fonte não integrada e podem ser marcados Conciliado fora.
- Contas a pagar (`data/04_caixa_de_entrada_contas_a_pagar.txt`) e qualquer débito do Extrato.
- Retorno CNAB, mesmo como enriquecimento (ADR 0001).
- Baixa automática ou qualquer escrita no Protheus ou no Omie.
- Layouts dos outros 3 bancos enquanto não houver amostra; até lá, seus arquivos são recusados com motivo.
- Múltiplas analistas, aprovação em dois níveis, autenticação na tela local.
- Deploy no servidor do cliente e agendamento automático.
- Rebaixamento automático de regra por taxa de rejeição.
- Feriados municipais e percentual de retenção de imposto por tipo de Título.

## Further Notes

- Pontos abertos com o cliente: percentuais de multa e juros do contrato e a tolerância (premissa: multa de 2%); se existe retenção de imposto em Título de Serviço (hoje tratada como Diferença a menor); limiar de "queda grande" da parte automática (deixar configurável); layouts dos outros 3 bancos; confirmar com o usuário que o teste de aceitação pode ler `data/` (a restrição dele é sobre valores no código).
- Resultado validado da amostra, com Data de referência 31/07: Lista com 6 Créditos (156.658,00), Fila com 9 Créditos (159.150,50), Fora do escopo com 3 débitos (20.229,00); LLM chamada em 2 casos (DOCE PONTO COM ALIME, SABOR CIA); 1 item de Título por Possível duplicidade (Grao Nobre, Omie x Protheus); Lista de cobrança com 1 Título (Norte Panificados, 8.120,00) e 9 em análise. Detalhe por lançamento, base da fixture do teste de aceitação:

  | Data | Lançamento | Valor | Destino | Título | Motivo / nota |
  |---|---|---|---|---|---|
  | 10/07 | Liquidação NN ...678 | 18.450,00 | Lista | NF 104521 | Nosso número + valor exato |
  | 10/07 | PIX PADARIA VILA NOVA LT | 3.200,00 | Fila | sug. NF 104522 | Pagador provável, primeira vez |
  | 13/07 | Liquidação NN ...701 | 9.870,00 | Lista | NF 104540 | Nosso número + valor exato |
  | 14/07 | TED DOCE PONTO COM ALIME | 47.630,50 | Fila | sug. NF 104533 + NF 104588 | Pagador provável, primeira vez; LLM; Encargo não pago na 104533 |
  | 15/07 | Liquidação NN ...712 | 66.300,00 | Lista | NF 104551 | Nosso número + valor exato |
  | 15/07 | TARIFA PACOTE COBRANCA | 1.240,00 D | Fora do escopo | - | Débito |
  | 16/07 | Liquidação NN ...720 | 62.500,00 | Fila | sug. NF 104560 | Valor não fecha (N:1 parcial) |
  | 17/07 | PIX CANTINHO MINEIRO FRA | 14.820,00 | Fila | sug. NF 104571 | Valor não fecha |
  | 20/07 | PAGAMENTO FORNECEDOR NF 88231 | 18.900,00 D | Fora do escopo | - | Débito |
  | 21/07 | Liquidação NN ...740 | 31.250,00 | Lista | NF 104580 | Encargo não pago |
  | 22/07 | PIX 11222333000166 | 7.430,00 | Lista | NF 104595 | CNPJ + Valor único; Encargo não pago |
  | 23/07 | TED CNPJ 66777888000199 | 23.358,00 | Lista | NF 104601 | CNPJ; 22.900 + 458 de multa |
  | 24/07 | PIX SABOR CIA | 7.100,00 | Fila | sug. NF 104552 | Pagador provável, primeira vez; LLM |
  | 27/07 | PIX NORTE PANIFICADOS EI | 12.980,00 | Fila | sug. FAT-2026-0332 | Pagador provável, primeira vez |
  | 28/07 | DEPOSITO NAO IDENTIFICADO | 5.670,00 | Fila | sug. FAT-2026-0340 | Sem identificação do pagador |
  | 29/07 | PIX EMPORIO BELA VISTA A | 3.400,00 | Fila | sug. FAT-2026-0335 | Pagador provável, primeira vez (prefixo do nome no Protheus, sem LLM) |
  | 30/07 | PIX PADARIA VILA NOVA LT | 1.850,00 | Fila | - | Crédito sem título em aberto |
  | 31/07 | TARIFA PIX EMISSAO | 89,00 D | Fora do escopo | - | Débito |
- Interpretação literal adotada: qualquer item decidido nas duas origens é conflito, mesmo que as decisões coincidam.
- Volume real: ~1.900 Títulos/mês em 4 bancos. A busca de somas por Franqueado precisa de limite explícito de combinações para não explodir; quando o limite é atingido, o item vai para a Fila como "mais de uma combinação possível".
