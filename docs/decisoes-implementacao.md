# Decisões de implementação

Decisões tomadas durante a implementação que não estavam na spec, no `CONTEXT.md` nem nos ADRs.

## Ticket 01: lançamentos considerados em cada execução

- **Decisão:** cada execução classifica todos os Créditos já guardados no SQLite mais os débitos lidos nesta execução. Débitos de execuções anteriores não reaparecem em Fora do escopo.
- **Por quê:** Créditos continuam vivos até a Analista decidir (ainda não há decisões neste ticket), então precisam continuar na Lista ou na Fila; débitos não exigem decisão e repeti-los todo dia só incharia Fora do escopo. A conferência de soma é feita sobre esse mesmo conjunto.
- **Alternativas:** classificar só o que veio nos arquivos da execução (perderia Créditos vivos quando o Extrato seguinte não cobre o período); classificar tudo que já foi guardado, inclusive débitos (Fora do escopo cresceria sem fim).

## Ticket 01: chave natural inclui a natureza do lançamento

- **Decisão:** a chave natural é banco + conta + data + natureza (C/D) + valor + histórico + documento + ordinal.
- **Por quê:** o valor é guardado sem sinal; sem a natureza, um débito e um crédito com mesmo dia, valor e histórico colidiriam. Equivale a usar o valor com sinal.
- **Alternativas:** valor com sinal na chave (mesmo efeito, menos legível).

## Ticket 01: Motivo provisório na Fila

- **Decisão:** Crédito sem regra aplicável vai para a Fila com "sem identificação do pagador"; Crédito com nosso número de um Título mas valor diferente vai com "valor não fecha", sugerindo o Título.
- **Por quê:** são os Motivos da spec que descrevem o caso com o que já existe; os tickets seguintes refinam a escolha e a precedência.
- **Alternativas:** um Motivo genérico fora da lista da spec (quebraria a regra de Motivos estáveis).

## Ticket 01: nosso número em mais de um Título

- **Decisão:** se o documento do Extrato é o nosso número de mais de um Título em aberto, o Crédito vai para a Fila sem sugestão.
- **Por quê:** a plataforma nunca escolhe entre opções igualmente válidas.
- **Alternativas:** escolher pelo valor (seria escolher por conta própria).

## Ticket 01: comparação do nosso número

- **Decisão:** o campo documento do Extrato precisa ser igual, como texto, ao nosso número do Título, sem completar zeros, extrair dígitos nem remover espaços.
- **Por quê:** é a forma mais estrita; qualquer tolerância de formato fica para quando houver amostra de outro banco.
- **Alternativas:** comparar só dígitos ou ignorar zeros à esquerda.

## Ticket 01: status do Protheus

- **Decisão:** linha do Protheus com status diferente de "Aberto" faz o arquivo ser recusado com o motivo.
- **Por quê:** a amostra só tem "Aberto"; tratar outro valor seria adivinhar (ADR 0005).
- **Alternativas:** ignorar a linha; aceitar qualquer status.

## Ticket 01: configuração de contas

- **Decisão:** arquivo TOML (`conciliacao.toml`) com `[[contas]]` de `padrao` (glob sobre o nome do arquivo), `banco` e `conta`. Extrato cujo nome casa com nenhum ou com mais de um padrão é recusado; Extrato cujo layout é de um banco diferente do configurado também.
- **Por quê:** TOML é lido pela biblioteca padrão; recusar ambiguidade segue o "nunca adivinhar".
- **Alternativas:** YAML/JSON; usar o primeiro padrão que casar.

## Ticket 01: identificador estável do item e falha da conferência

- **Decisão:** o identificador do item é `L<id do lançamento no SQLite>`, o mesmo em todas as execuções. Quando a conferência de soma falha, a transação inteira é desfeita: nenhum lançamento novo nem execução é guardado e o workbook não é gerado.
- **Por quê:** a leitura de volta do Excel precisa de um identificador que não mude; desfazer tudo evita estado parcial de uma execução que parou (ADR 0005).
- **Alternativas:** identificador por execução; guardar os lançamentos mesmo com a conferência falhando.

## Ticket 01: typechecker

- **Decisão:** mypy em modo estrito sobre `src` e `tests`.
- **Por quê:** pega erros de tipo cedo com custo baixo de manutenção.
- **Alternativas:** pyright; sem typechecker.

## Ticket 02: diferença de cabeçalho citada no motivo

- **Decisão:** quando o cabeçalho não corresponde exatamente a nenhum layout, o motivo cita a diferença (colunas que faltam, a mais, ou fora da ordem) em relação ao layout com mais colunas em comum. Se nenhum layout tem coluna em comum, ou se há empate, o motivo é só "cabeçalho não corresponde a nenhum layout conhecido". O layout mais próximo serve apenas para o texto do motivo; o arquivo é sempre recusado.
- **Por quê:** a Analista precisa saber o que mudou na exportação; usar o layout mais próximo só para explicar não é adivinhar layout (ADR 0005), e no empate não há base para escolher.
- **Alternativas:** citar a diferença contra todos os layouts (motivo longo e confuso); motivo genérico sempre (não atende o critério do ticket).

## Ticket 02: Extrato de banco sem adaptador

- **Decisão:** arquivo cujo cabeçalho não é de nenhum layout e cujo nome casa com exatamente uma conta configurada de banco sem adaptador é recusado com motivo que nomeia o banco e a conta e diz que o banco não tem adaptador.
- **Por quê:** a configuração já diz o banco; é o motivo mais útil e não depende de adivinhar o conteúdo.
- **Alternativas:** motivo genérico de cabeçalho desconhecido; exigir que a configuração liste só bancos com adaptador (impediria cadastrar as contas antes da amostra chegar).

## Ticket 02: arquivos lidos e recusados no Resumo e aba própria

- **Decisão:** o Resumo mostra "Arquivos lidos" e "Arquivos recusados" como contagem, seguidas de uma linha por arquivo (recusados com o motivo). A aba "Arquivos recusados" (colunas Arquivo e Motivo) é a última do workbook, na ordem das abas da spec. O teste do comando que listava exatamente as quatro abas do ticket 01 passou a incluir a nova aba, porque o ticket exige a aba.
- **Por quê:** a contagem é o que o ticket pede; manter o motivo no Resumo segue a spec ("o que foi recusado e por quê"). Arquivo vazio é recusado com "o arquivo está vazio".
- **Alternativas:** só a aba, sem detalhe no Resumo; contagem no mesmo texto dos nomes, como no ticket 01.
