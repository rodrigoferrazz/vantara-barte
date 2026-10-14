# 05: Simulador por proporções e contrato da Porta de cobrança

**What to build:** A Porta de cobrança simulada traz os Retornos como arquivos nos formatos públicos, e o simulador de pagamentos gera, a partir das Cobranças emitidas e de proporções configuráveis, Extrato e Retornos imperfeitos como a realidade, com gabarito. Um fluxo completo (emitir, simular, conciliar) é verificável contra o gabarito.

**Blocked by:** 02, 03, 04

**Status:** ready-for-human

- [x] Plano por proporções: em dia, atraso com multa, atraso sem Encargo, parcial em boleto autorizado e Crédito solto (Pix, TED ou depósito, com a bagunça de nome do gerador da fase 1)
- [x] Extrato gerado nos layouts de banco já aceitos pelos adaptadores da fase 1
- [x] Pix com txid sempre com o valor da cobrança (com ou sem multa e juros); valor a menos com identificador só em boleto parcial autorizado
- [x] Mesma semente gera exatamente os mesmos arquivos; gabarito com destino, Título(s) e Motivo de cada Crédito
- [x] Teste de contrato da porta: emitir duas vezes não duplica, identificadores únicos e no formato, arquivos trazidos aceitos pelos adaptadores de Retorno
- [x] Proporções respeitadas dentro de uma tolerância em volume
- [x] Teste ponta a ponta: nenhum item da Lista de baixa diverge do gabarito

## Comments

- Implementado. Testes em `tests/test_simulador.py` (proporções em volume, restrições da spec, gabarito, semente e ponta a ponta) e `tests/test_contrato_da_porta.py` (contrato, rodado contra o adaptador simulado); cenário comum em `tests/simulacao.py`. Decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 05").
- Status `ready-for-human`, como nos tickets anteriores: o `triage-labels.md` não tem papel de concluído.
- Novo: `trazer_retornos` na Porta de cobrança (Pix recebidos da API Pix e retorno CNAB 240), `emitir` idempotente e recusa de pagamento que a spec não permite; módulo `simulador` com o Plano por proporções, o Extrato no layout do Itaú e o gabarito (destino, Título, Motivo, desfecho, canal e bagunça de cada Crédito).
- O Encargo agora vai para o adaptador da porta, como combinado no ticket 01: é ele que calcula o valor da `cobv` (com multa e juros) na data do pagamento. O comando `emitir-cobrancas` passa o `[encargo]` da configuração.
- O ponta a ponta usa os Títulos do gerador da fase 1 (300 Títulos, sem duplicidade entre sistemas, todos os Franqueados migrados): emite, simula, traz os Retornos e concilia. Além da Lista de baixa, destino e Motivo de todos os Créditos batem com o gabarito.
- O canal sai da regra e não do desfecho: atraso sem Encargo e parcial de Título que só tem Pix (os do Protheus) chegam como Crédito solto. O gabarito guarda o desfecho sorteado, e as proporções são medidas sobre ele.
- Pontos em aberto: (1) a emissão não diz se o boleto autoriza pagamento parcial, e o simulador trata todo boleto da plataforma como autorizado; (2) o simulador não paga pelo boleto do Protheus; (3) a opção de linha de comando para demonstração e as proporções no `conciliacao.toml` ficaram para quando a análise de impacto usar o simulador.
- Os dois testes de falha da porta (tickets 01 e 03) passaram a estender `PortaSimulada`, porque a interface ganhou `trazer_retornos`. Nenhum teste da fase 1 mudou; o gerador da fase 1 teve funções extraídas para o simulador sem mudar o que gera.
