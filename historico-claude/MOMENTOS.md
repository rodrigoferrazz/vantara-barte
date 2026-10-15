# Histórico das sessões de IA

Transcripts do Claude Code sem edição, um arquivo `.jsonl` por sessão:

`construcao/`: implementação dos tickets das duas fases, correções e reformulação da tela.

## Momentos que importaram

1. **A IA propôs o CNAB como fonte principal da conciliação.** Na sessão de especificação, pedi a arquitetura da leitura dos pagamentos e a IA colocou o retorno CNAB do boleto como fonte principal. Contestei, porque o CNAB só cobre boleto e os casos difíceis são Pix e TED. O extrato virou a fonte principal e o retorno de cobrança passou só a enriquecer (ADR 0001).

2. **A IA ajustou uma regra para o exemplo passar (erro).** Ao definir a identificação pelo nome cortado do banco, a IA mudou a regra de prefixo para que um caso da amostra desse certo. Recusei, porque isso é ajustar a regra ao dado de teste, e exigi comparar o nome com todos os nomes do franqueado nos dois ERPs. Também proibi qualquer valor da amostra no código, e um teste passou a verificar isso.

3. **Os testes passavam, mas a entrega não seguia a spec (erro).** Depois da implementação da fase 1, pedi uma revisão do código contra a spec. Ela achou desvios: 14 faturas "em análise" em vez de 9 e motivos de fila diferentes do especificado. Além disso, o modelo de IA escolhido respondia "não" para os dois nomes que deveria reconhecer. Mandei corrigir seguindo a spec e testar outros modelos de 3 a 4B com exemplos fictícios. A IA mediu 16 combinações de prompt e modelo e o `qwen3:4b` foi escolhido pelos números (`docs/decisoes-implementacao.md`, "Correção: prompt e modelo da IA").
