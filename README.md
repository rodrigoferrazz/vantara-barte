# Conciliação de contas a receber - Vantara

Liga cada Crédito do Extrato aos Títulos dos Franqueados exportados do Protheus e do Omie. O que fecha vai para a Lista de baixa; o resto vai para a Fila de exceções com um Motivo de não identificação, para a Analista de conciliação decidir. A plataforma nunca dá baixa no ERP e nunca escreve no Protheus nem no Omie.

A fase 1 concilia o que chega. A fase 2 ataca a causa: cada Título de um Franqueado migrado ganha uma Cobrança identificada (Pix com txid e, quando falta, boleto com nosso número), para o pagamento já chegar dizendo qual Título paga. Sem sistema de pagamento real, a emissão e os Retornos de cobrança passam por uma Porta de cobrança simulada pelas specs públicas (API Pix do Banco Central e retorno CNAB 240 da FEBRABAN).

Glossário em `CONTEXT.md`, decisões de arquitetura em `docs/adr/`, decisões de implementação em `docs/decisoes-implementacao.md` e specs em `.scratch/conciliacao-fase1/spec.md` e `.scratch/conciliacao-fase2/spec.md`.

## Instalação

Precisa de Python 3.13 e [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

O parecer de nome usa um LLM local pelo Ollama (seção `[ia]` do `conciliacao.toml`, modelo `qwen3:4b`). Sem o Ollama, os itens que precisariam de parecer ficam marcados "IA indisponível" e o resto funciona igual.

## Uso

Todos os comandos leem `conciliacao.toml` (opção `--configuracao`), que diz o banco e a conta de cada arquivo de Extrato, o Encargo, a IA e os parâmetros da fase 2.

| Comando | O que faz |
| --- | --- |
| `uv run conciliar <pasta>` | Concilia as exportações e os Extratos da pasta e gera `conciliacao.xlsx`; o estado fica em `conciliacao.sqlite` |
| `uv run conciliar-tela` | Abre a tela local com o resultado da última execução, onde a Analista decide os itens |
| `uv run emitir-cobrancas` | Emite Cobrança identificada para os Títulos em aberto dos Franqueados migrados (precisa de `[migracao]`) |
| `uv run analisar-impacto <pasta>` | Gera `analise_de_impacto.xlsx` com o antes e o depois da Cobrança identificada |

Exemplo com a amostra de julho:

```sh
uv run conciliar data
uv run analisar-impacto data
```

## Análise de impacto

Concilia a pasta base como ela é (o "antes"), monta o Ranking de migração com os Créditos da Fila que um Identificador de cobrança resolveria e, para cada Adesão da faixa e cada Onda de migração acumulada, refaz a mesma conciliação com os pagamentos que chegariam identificados (o "depois"). O dinheiro é sempre o mesmo do antes: só muda se cada Crédito chega com identificador. Tudo roda em armazenamento temporário; nada é gravado na pasta base nem no `conciliacao.sqlite`.

Semente, tamanho da onda e faixa de Adesão ficam em `[analise_de_impacto]`. A verdade sobre qual Título cada Crédito paga vem, nesta ordem, do gabarito do gerador sintético (só pelos testes), das decisões confirmadas da Analista (opção `--estado` com um `conciliacao.sqlite`, que só é lido) ou das Propostas e sugestões do próprio antes. Na amostra de julho não há decisões confirmadas, então a verdade são as Propostas e sugestões, e a aba Premissas diz isso.

Cada combinação de onda e Adesão é uma conciliação inteira. Nos dados sintéticos de volume real (cerca de 1.900 Títulos em 4 contas), a configuração padrão (ondas de 10 Franqueados e Adesões de 50%, 80% e 95%) dá 14 ondas e 45 conciliações quando a IA reconhece os nomes do gabarito, e leva cerca de 2,5 minutos num MacBook Air M2 com a IA falsa. Com ondas de 50 Franqueados são 3 ondas e cerca de 40 segundos, que é o que o teste de aceitação roda.

## Testes

```sh
uv run pytest                 # suíte sem serviços externos
uv run pytest -m integracao   # com o Ollama real (pula se ele não estiver rodando)
uv run mypy                   # tipagem estrita de src e tests
```

Os testes de aceitação estão em `tests/test_aceitacao_amostra_julho.py` (fase 1) e `tests/test_aceitacao_analise_de_impacto.py` (fase 2, julho e o sintético de 1.900 Títulos). Os números esperados da amostra vivem só nos testes, nunca no código de produção.

## Fora do escopo da fase 2

- Integração com banco ou PSP real: o adaptador real da Porta de cobrança entra no lugar do simulado quando existir o sistema.
- Remessa CNAB, CNAB 400 e variações de banco; BR Code, QR e boleto em PDF; envio da cobrança ao Franqueado.
- Cancelamento ou reemissão de cobrança quando o Título muda de valor ou é baixado.
- Opção de linha de comando para demonstrar o simulador por proporções e as proporções no `conciliacao.toml`: hoje o simulador por proporções só é usado pelos testes ponta a ponta, com as proporções em código.

## Próximos passos

Nenhum destes está implementado; ficam registrados como o caminho depois da fase 2.

### Conta virtual por Franqueado

Cada Franqueado recebe uma conta virtual (subconta ou número de conta próprio no mesmo banco) para depositar e transferir. Qualquer pagamento que entra por ela, inclusive TED, depósito e Pix por chave, já diz de qual Franqueado é, sem depender do nome no histórico. Ataca o que a Cobrança identificada não resolve: o Crédito solto que chega por TED ou depósito sem nome, hoje "sem identificação do pagador". O Título continua decidido pelas regras da fase 1 (valor, Valor único e soma), agora com o Franqueado certo. Depende de o banco oferecer contas virtuais e de o Extrato trazer a conta virtual de cada Crédito.

### Pix Automático para royalty

O royalty é recorrente, então pode ser cobrado pelo Pix Automático: o Franqueado autoriza uma vez e cada cobrança é debitada no vencimento, com txid, sem ele precisar pagar. A API Pix que a fase 2 já segue cobre isso em `/rec` (recorrência autorizada) e `/cobr` (cobrança de cada ciclo), então o Retorno chega como um Pix recebido com txid, pelo mesmo adaptador. Reduz atraso, pagamento parcial e Crédito solto no Título que mais se repete. Depende do PSP real e da autorização de cada Franqueado, e as regras de agendamento e de nova tentativa do Pix Automático precisam de spec própria.
