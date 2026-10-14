# 09: Aceitação em julho e nos 1.900 sintéticos, e README

**What to build:** A análise de impacto roda sobre a amostra de julho e sobre os dados sintéticos de volume real, com testes de aceitação, e o README registra os próximos passos depois da fase 2.

**Blocked by:** 08

**Status:** ready-for-human

- [x] Teste de aceitação da análise sobre `data/` com semente fixa e Parecerista falso; números esperados só na fixture do teste, nunca no código de produção
- [x] Teste sobre o gerador sintético da fase 1 (~1.900 Títulos, 4 bancos): nenhum item da Lista do "depois" diverge do gabarito
- [x] Nos dois conjuntos: dinheiro do "depois" igual ao do "antes" e Fila que nunca cresce com mais Adesão ou onda
- [x] Aba Premissas deixa claro que a verdade de julho vem de Propostas e sugestões
- [x] Execução no volume sintético termina em tempo aceitável no MacBook Air M2 com a IA falsa
- [x] README com conta virtual por Franqueado e Pix Automático para royalty como próximos passos, sem implementação

## Comments

- Implementado. Testes em `tests/test_aceitacao_analise_de_impacto.py` (julho com IA falsa e, com `-m integracao`, com o Ollama; sintético de cerca de 1.900 Títulos). README novo na raiz. Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 09").
- Status `ready-for-human`, como nos tickets anteriores: o `triage-labels.md` não tem papel de concluído.
- Julho, configuração do projeto (semente 1), faixa trocada só no teste por 0, 50, 80, 95 e 100%: identificados vão de 5 para 9 (50%) e 10 (80% em diante) de 15 Créditos; a Fila vai de 9 (R$ 159.150,50) para 6 e 5 (R$ 133.900,50). Com toda a Adesão ficam na Fila Doce Ponto, a Liquidação de 16/07, Cantinho Mineiro, Sabor Cia e o Pix de 30/07 sem Título. 4 Créditos são "não identificáveis pelo valor" e 1 fica sem Título conhecido. O Ollama dá os mesmos números.
- Aba Premissas: nova linha "Limite da fonte da verdade" ("15 de 15 Créditos não têm gabarito nem decisão confirmada da Analista..."), escrita para qualquer pasta.
- Sintético: o teste usa ondas de 50 Franqueados (3 ondas, cerca de 40 s) em vez das de 10 do padrão (14 ondas, 45 conciliações, cerca de 2,5 min no M2, medido e registrado no README). Confere a Lista de todo depois contra o gabarito, inclusive os pagamentos identificados, e a Fila e o dinheiro em toda onda e Adesão. Os "4 bancos" do critério são as 4 contas do gerador, todas no layout do Itaú: os layouts dos outros 3 bancos continuam ponto em aberto da fase 1.
- Correção separada (commit `correção: ...`): ponto em aberto do ticket 04. Retorno que chega depois de a Analista encerrar o Crédito agora é ligado a ele pelo par conta, data e valor, sem mudar a decisão, e sai do Resumo. Não afetava a aceitação (a análise usa armazenamento sem decisões), mas era ruído permanente no uso diário, porque a confirmação é a decisão mais comum.
- Fora do escopo, documentado no README: opção de linha de comando para demonstrar o simulador por proporções e as proporções no `conciliacao.toml`. Nenhum critério deste ticket depende delas.
