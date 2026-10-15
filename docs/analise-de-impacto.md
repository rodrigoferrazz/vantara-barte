# Como a análise de impacto calcula

O comando `analisar-impacto <pasta>` responde: quanto da Fila de exceções sumiria se parte dos Franqueados pagasse pela Cobrança Endereçada (Pix com txid ou boleto com nosso número emitido pela plataforma)?

## O antes e o depois

1. Concilia a pasta base como ela é. Esse é o "antes".
2. Monta o Ranking de migração: os Franqueados com mais Créditos na Fila que um Identificador de cobrança resolveria vêm primeiro.
3. Divide o Ranking em Ondas de migração e, para cada onda acumulada e cada Adesão da faixa (a parte dos pagamentos que chega identificada), refaz a mesma conciliação trocando os Créditos sorteados por pagamentos identificados. Esse é o "depois".

O dinheiro é sempre o mesmo do antes: só muda se cada Crédito chega com identificador. Todas as conciliações rodam em armazenamento temporário e a pasta base não muda. Só o resultado é gravado no `conciliacao.sqlite` (opção `--estado`), ao lado das execuções diárias, sem mexer nelas. A aba Migração da tela lê esse resultado; para atualizar, rode o comando de novo e recarregue a página.

## A verdade de cada Crédito

Para saber qual Título cada Crédito pagaria pelo identificador, a análise usa, nesta ordem, a primeira fonte que conhece o Crédito:

1. o gabarito do gerador de dados sintéticos (só nos testes);
2. as decisões confirmadas da Analista no `conciliacao.sqlite` (só lidas, nunca alteradas);
3. a Proposta da Lista de baixa ou a sugestão da Fila do próprio antes.

Na amostra de julho não há decisões confirmadas, então a verdade de todos os 15 Créditos é a sugestão do antes: o depois supõe que o antes acertou o Título. A aba Premissas diz isso.

## Configuração

Semente do sorteio, tamanho da onda e faixa de Adesão ficam em `[analise_de_impacto]` no `conciliacao.toml`. A mesma pasta com a mesma configuração dá sempre o mesmo relatório.

## Tempo

Cada combinação de onda e Adesão é uma conciliação inteira. Nos dados sintéticos de volume real (cerca de 1.900 Títulos em 4 contas), a configuração padrão (ondas de 10 Franqueados e Adesões de 50%, 80% e 95%) dá 14 ondas e 45 conciliações e leva cerca de 2,5 minutos num MacBook Air M2 com a IA falsa dos testes. Com ondas de 50 Franqueados são 3 ondas e cerca de 40 segundos, que é o que o teste de aceitação roda. Na amostra de julho o comando leva cerca de 30 segundos com o Ollama.

As decisões por trás de cada passo estão em `docs/decisoes-implementacao.md`, nas seções "Fase 2, ticket 06" a "Fase 2, ticket 10".
