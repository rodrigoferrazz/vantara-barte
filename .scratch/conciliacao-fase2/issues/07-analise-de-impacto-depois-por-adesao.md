# 07: Análise de impacto, o depois por Adesão

**What to build:** A análise de impacto passa a mostrar, para cada Adesão da faixa e com todos os Franqueados migrados, como a mesma pasta se concilia quando os Créditos chegam identificados: mesmo dinheiro, mesma data, mesmo Franqueado, só muda a identificação.

**Blocked by:** 05, 06

**Status:** ready-for-human

- [x] Fonte da verdade, nesta ordem: gabarito; decisões confirmadas da Analista quando um armazenamento é informado; Proposta da Lista ou sugestão da Fila do "antes"; o relatório diz quantos Créditos vieram de cada fonte
- [x] Um único sorteio por Crédito, fixo pela semente; Adesão maior contém a menor
- [x] Crédito que pagou vários Títulos vira um pagamento identificado por Título, no mesmo dia e com o mesmo total
- [x] Crédito com valor que a spec não permite com txid fica solto e é contado como "não identificável pelo valor"; Crédito sem Título conhecido fica solto
- [x] Créditos que já chegavam pelo nosso número continuam identificados
- [x] Emite pela porta simulada, gera o "depois" pelo simulador e concilia com armazenamento temporário novo e o mesmo Parecerista
- [x] Abas Resumo do impacto (soltos e identificados, Fila em quantidade e valor, % resolvido sozinho) e Fila por motivo, para cada Adesão (padrão 50%, 80%, 95%)
- [x] Adesão de 0% dá "depois" igual ao "antes"; o dinheiro do "depois" soma igual ao do "antes"

## Comments

- Implementado. Testes em `tests/test_analise_de_impacto_depois.py` (Adesão 0%, Adesão total, Crédito de vários Títulos, Pix pelo valor da cobrança, parcial em boleto, não identificável pelo valor, Título já pago, gabarito e `--estado` como fonte, sintético com dinheiro igual, Fila que não cresce, Adesão maior contendo a menor e Lista sem divergência do gabarito, semente, workbook, configuração e comando). Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 07").
- Status `ready-for-human`, como nos tickets anteriores: o `triage-labels.md` não tem papel de concluído.
- Novo: `faixa_de_adesao_percentual` em `[analise_de_impacto]`; opção `--estado` no `analisar-impacto` (o arquivo é copiado e nunca alterado); abas Resumo do impacto e Fila por motivo; `Contrafactual` no simulador, que divide com o Plano por proporções a regra de canal e o pagamento identificado; `emitir` separado da seleção de Títulos na emissão.
- O gabarito do gerador só entra pela função `analisar_impacto(..., gabarito=...)`: o gerador não escreve o gabarito na pasta, então o comando usa `--estado` ou as Propostas e sugestões.
- Ordem das razões de ficar solto, decidida antes do sorteio: já identificado, sem Título conhecido, Título sem Cobrança identificada (fora dos em aberto, em Possível duplicidade ou já pago por Crédito anterior), não identificável pelo valor. Assim "não identificável pelo valor" não muda com a Adesão.
- O pagamento identificado vai para a conta de cobrança (primeira conta com lançamentos), porque o arquivo de Pix recebidos tem uma conta só; valor, data e Franqueado não mudam.
- Na amostra de julho, com a configuração do projeto: identificados vão de 5 para 9 (50%) e 10 (80% e 95%) de 15 Créditos, e a Fila de 9 para 6 e 5; 4 ficam "não identificáveis pelo valor" e 1 sem Título conhecido.
- Pontos em aberto: Retornos da pasta base não vão para o "depois"; as proporções do simulador não aparecem em Premissas porque o contrafactual não as usa; a opção de linha de comando para demonstrar o simulador continua de fora.
