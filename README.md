# Conciliação de contas a receber - Vantara

## O que é

Os franqueados da Vantara pagam por Pix, TED, depósito e boleto, e o pagamento entra no banco sem dizer a qual fatura pertence. Alguém precisa descobrir isso à mão, e enquanto não descobre a cobrança liga para franqueado que já pagou.

- **Conciliação Assistida**: lê o extrato do banco e as faturas em aberto dos ERPs, liga sozinha o que as regras conseguem provar e deixa o resto numa fila para a analista decidir, explicando o motivo de cada caso.
- **Cobrança Endereçada**: emite cada fatura com um Pix ou boleto próprio, para que o pagamento já chegue dizendo qual fatura paga.

## Pré-requisitos

- **macOS** com [Homebrew](https://brew.sh) (os comandos abaixo são para Mac).
- **Python 3.13**: se não estiver instalado, o `uv` baixa sozinho no primeiro `uv sync`.
- **[uv](https://docs.astral.sh/uv/)**, gerenciador de pacotes Python.
- **[Ollama](https://ollama.com)** com o modelo `qwen3:4b`, que ocupa cerca de 2,5 GB de disco e roda num Mac com 8 GB de memória. É opcional: sem ele tudo roda, só a parte da IA fica desligada.

Nenhuma chave de API ou conta é necessária. Tudo roda local e offline depois da instalação.

## Instalação

Todos os comandos são rodados na pasta do projeto.

1. Instale o `uv` e as dependências do projeto:

   ```sh
   brew install uv
   uv sync
   ```

2. Instale e inicie o Ollama, e baixe o modelo:

   ```sh
   brew install ollama
   brew services start ollama
   ollama pull qwen3:4b
   ```

3. Confira que o modelo responde:

   ```sh
   ollama list                                     # deve listar qwen3:4b
   ollama run qwen3:4b --think=false "diga oi"     # deve responder em menos de um minuto
   ```

Sem o Ollama, a conciliação roda igual e os pagamentos que precisariam da IA ficam marcados "IA indisponível" na fila, para a analista decidir sem o parecer.

## Rodar com o data pack

O data pack está em `data/`. Só três arquivos entram na conciliação:

- `data/01_contas_a_receber_protheus_jul2026.csv`: faturas em aberto do Protheus (ERP da operação principal)
- `data/02_titulos_unidade_norte_omie_jul2026.csv`: faturas em aberto do Omie (ERP da unidade adquirida)
- `data/03_extrato_bancario_jul2026.csv`: extrato do Itaú de julho

### Pela tela

1. Suba a tela:

   ```sh
   uv run conciliar-tela
   ```

   O navegador abre sozinho em http://127.0.0.1:8765/. Se não abrir, abra esse endereço. Se a porta 8765 estiver ocupada, use outra com `uv run conciliar-tela --porta 8766`. A tela fica no ar até você apertar Ctrl+C no terminal.

2. Na aba **Conciliação Assistida > Analista**, clique no seletor de arquivos (**Escolher arquivos**), selecione os três arquivos acima e clique em **Enviar arquivos**. Eles aparecem na lista como novos.
3. Clique em **Conciliar**. A página recarrega com o resultado em alguns segundos (a primeira chamada à IA carrega o modelo e pode levar até meio minuto).

### Pelo comando

```sh
uv run conciliar data
```

Faz a mesma conciliação sobre a pasta inteira e gera o mesmo Excel. Os arquivos `00_LEIA-ME.md` e `04_caixa_de_entrada_contas_a_pagar.txt` aparecem como recusados, porque não são extrato nem exportação de ERP. Depois, `uv run conciliar-tela` mostra o resultado.

## O que esperar

Com o data pack e o Ollama funcionando:

| | Resultado |
| --- | --- |
| Lista de baixa (pagamentos ligados a uma fatura pelas regras, prontos para a analista confirmar) | 6 pagamentos, R$ 156.658,00 |
| Fila de exceções (casos que a analista decide) | 9 pagamentos, R$ 159.150,50, e 1 fatura que parece estar lançada duas vezes, no Protheus e no Omie |
| Fora do escopo (saídas de dinheiro: tarifas e um pagamento a fornecedor) | 3 lançamentos, R$ 20.229,00 |
| Resolvido sozinho | 6 de 15 pagamentos (40,0%), 49,6% do valor |
| Faturas a cobrar | 1, R$ 8.120,00, com 3 dias de atraso |
| Faturas que não devem ser cobradas ainda (há um pagamento que pode ser delas em análise) | 9, R$ 220.580,50 |
| Chamadas à IA | 2 (`TED RECEBIDA DOCE PONTO COM ALIME` e `PIX RECEBIDO SABOR CIA`), as duas com "sim"; ficam na fila como "pagador provável, primeira vez" |

Na tela, cada aba mostra:

- **Conciliação Assistida > Analista**: envio dos arquivos, resumo, Lista de baixa com Confirmar e Rejeitar, a fila em cartões com o motivo e a sugestão, e o botão **Baixar o Excel**.
- **Conciliação Assistida > Cobrança**: quem cobrar, com os dias de atraso, e quem não cobrar ainda, com o motivo.
- **Conciliação Assistida > Gestão**: quanto foi resolvido sozinho e por que o resto não se identifica, em gráfico.
- **Cobrança Endereçada > Emissão**: as cobranças emitidas e se já foram pagas.
- **Cobrança Endereçada > Migração**: quanto da fila sumiria com a Cobrança Endereçada (precisa do `analisar-impacto`, abaixo).
- **Cobrança Endereçada > Demonstração**: emissão e pagamentos simulados de ponta a ponta.

Os arquivos gerados ficam na pasta do projeto:

- `conciliacao.xlsx`: o resultado completo em Excel, uma aba por lista.
- `conciliacao.sqlite`: o estado entre execuções (pagamentos, decisões e histórico). Apague-o para começar do zero.
- `entrada/`: os arquivos enviados pela tela.

As saídas geradas a partir do data pack estão em `exemplos-de-saida/`.

## Demonstração da Cobrança Endereçada

Depois de conciliar pela tela:

1. Em **Cobrança Endereçada > Demonstração**, clique em **Emitir cobranças**. A plataforma emite, por um banco simulado, um Pix com identificador para cada uma das 15 faturas em aberto e um boleto para as que não têm. Elas aparecem em **Emissão** como "Emitida".
2. Clique em **Simular pagamentos**. A plataforma grava na entrada da analista um extrato e um arquivo de retorno do banco simulados. Só 1 fatura é paga: as outras 14 já têm um pagamento real no extrato de julho, e pagá-las de novo criaria pagamento em dobro. A paga é a única que estava "a cobrar" (NORTE PANIFICADOS, R$ 8.120,00).
3. Clique em **Ver na Conciliação Assistida** e depois em **Conciliar**. A Lista de baixa passa a ter 7 pagamentos, e o novo aparece em verde com "Pagamento endereçado: o boleto já dizia a fatura". Em **Cobrança**, "A cobrar" cai para 0, e em **Emissão** a fatura aparece como paga.
4. Clique em **Zerar demonstração** para voltar ao estado de antes da emissão.

Na segunda conciliação o resumo mostra o aviso "Decisões não aplicadas": o Excel da primeira conciliação não foi editado, então não há decisão nele para aplicar. É esperado.

Para a aba **Migração**, rode em outro terminal:

```sh
uv run analisar-impacto data
```

O comando simula quanto da fila sumiria se parte dos franqueados pagasse pela Cobrança Endereçada. Leva cerca de 30 segundos, gera `analise_de_impacto.xlsx` e grava o resultado para a tela; recarregue a aba Migração. Com o data pack, a fila cai de 9 para 6 pagamentos se metade dos pagamentos vier pela Cobrança Endereçada e para 5 com 80% ou mais. Os 5 que sobram não se resolvem com uma cobrança por fatura: 4 não batem com o valor de uma única fatura (pagamento parcial ou de várias faturas juntas) e 1 não tem fatura correspondente. Como o cálculo funciona: [`docs/analise-de-impacto.md`](docs/analise-de-impacto.md).

## Onde a IA atua e onde não atua

A IA (o modelo `qwen3:4b` rodando no Ollama, na própria máquina) só dá parecer sobre um ponto: se o nome do pagador no extrato pertence a um franqueado, quando as regras não conseguem identificar pelo nome e o valor bate com faturas desse franqueado. Ela responde sim ou não com uma explicação, que aparece destacada no cartão da fila.

- Tudo que passa pela IA vai para a fila, nunca direto para a Lista de baixa. Quem decide é a analista.
- Valores, datas, multa, identificação por boleto, Pix e CNPJ são regras determinísticas, sem IA.
- Se o Ollama estiver fora do ar, demorar mais que o limite ou responder fora do formato, o item fica na fila marcado "IA indisponível", com a sugestão pelo valor, e o resumo avisa. A conciliação nunca para por causa da IA.

## Limitações conhecidas

- Exportação do Protheus com fatura de status diferente de "Aberto", ou do Omie com `paid_flag` diferente de "N", é recusada inteira, com o motivo.
- Só o extrato do Itaú tem leitor; extratos de outros bancos são recusados com o motivo até haver uma amostra do formato.
- Na análise de impacto do data pack, não há decisões da analista, então a plataforma usa as próprias sugestões como verdade: se ela errou a fatura no antes, o erro passa para o depois.
- A emissão das cobranças e os pagamentos são simulados, seguindo as especificações públicas do Pix (Banco Central) e do retorno de boleto CNAB 240 (FEBRABAN); não há banco ou PSP real.
- Não há integração por API com o Protheus nem com o Omie: os dados entram por arquivos exportados.
- A baixa no ERP continua manual: a plataforma nunca escreve no Protheus nem no Omie, porque o Protheus só libera leitura. Ela gera a lista do que baixar.
- A tela não tem login: ela só aceita acesso da própria máquina, e quem decide é registrado como o usuário do sistema.
- A tela atende uma ação por vez: enquanto concilia, fica esperando, e com o Ollama e volume real isso pode levar minutos.
- A IA errou 1 de 28 pares de nomes fictícios na avaliação (disse "sim" para nomes de empresas diferentes); por isso o "sim" dela nunca baixa sozinho.
- Multa de 2% e juros zero por atraso são premissas ainda não confirmadas pelo contrato (ajustáveis na configuração).
- Só os feriados bancários nacionais contam no vencimento; feriados municipais não.
- Decisões feitas no Excel só valem se o arquivo for salvo no Excel, que registra quem salvou.

## Configuração

O `conciliacao.toml` é o que muda de um cliente para outro. O código é o mesmo para qualquer cliente: só a configuração e os leitores de arquivo de cada banco e ERP mudam.

- `[[contas]]`: qual banco e conta é cada arquivo de extrato, pelo nome do arquivo.
- `[encargo]`: multa e juros por atraso.
- `[ia]`: endereço do Ollama, modelo e tempo limite. Sem essa seção, a IA fica desligada.
- `[migracao]`: franqueados que já recebem a Cobrança Endereçada (comentado; sem ele a emissão diária não emite).
- `[analise_de_impacto]`, `[somas]` e `[resumo]`: parâmetros da análise de impacto, da busca de combinações de faturas e do alerta de queda.

Cada comando aceita `--configuracao` para usar outro arquivo.

## Testes

```sh
uv run pytest                 # suíte completa, sem Ollama (usa uma IA falsa)
uv run pytest -m integracao   # com o Ollama real (pula se ele não estiver rodando)
uv run mypy                   # checagem de tipos
```

Cobrem as regras de identificação, a leitura de cada formato, as decisões da analista, a tela, a emissão e a análise de impacto, incluindo a aceitação ponta a ponta com o data pack e com dados sintéticos de volume real (cerca de 1.900 faturas). A suíte leva cerca de 1,5 minuto.

## Onde está o resto

- `CONTEXT.md`: glossário dos termos do domínio.
- `docs/adr/`: decisões de arquitetura.
- `docs/decisoes-implementacao.md`: cada decisão de implementação, com o porquê e as alternativas.
- `docs/analise-de-impacto.md`: como a análise de impacto calcula.
- `.scratch/conciliacao-fase1/spec.md` e `.scratch/conciliacao-fase2/spec.md`: specs da Conciliação Assistida e da Cobrança Endereçada.

## Fora do escopo

- Contas a pagar (`data/04_caixa_de_entrada_contas_a_pagar.txt`) e qualquer saída de dinheiro do extrato.
- Banco ou PSP real, envio da cobrança ao franqueado, QR Code e boleto em PDF.
- Cancelamento ou reemissão de cobrança quando a fatura muda.
- Várias analistas, aprovação em dois níveis e instalação no servidor do cliente.

## Próximos passos

- **Conta virtual por franqueado**: todo pagamento que entra por ela, inclusive TED e depósito, já diz de qual franqueado é.
- **Pix Automático para royalty**: o franqueado autoriza uma vez e o royalty é debitado no vencimento, já com identificador.
