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

## Ticket 03: CNPJ do Título normalizado na leitura

- **Decisão:** o adaptador do Protheus aceita o CNPJ como `12.345.678/0001-90` ou com 14 dígitos e guarda só os dígitos; qualquer outro formato recusa o arquivo inteiro com o motivo. O dígito verificador não é conferido.
- **Por quê:** a spec manda guardar o CNPJ só com dígitos e raiz de 8; recusar formato estranho segue o ADR 0005. A amostra tem CNPJs com dígito verificador inválido, então conferir o dígito recusaria exportações reais.
- **Alternativas:** conferir o dígito verificador; ignorar a linha com CNPJ inválido.

## Ticket 03: CNPJ no histórico

- **Decisão:** o histórico é varrido por CNPJs com pontuação completa ou com 14 dígitos seguidos, sem fazer parte de um número maior. Um CNPJ identifica o Franqueado quando sua raiz é a de algum Título já visto; CNPJ de raiz desconhecida é ignorado. Se os CNPJs conhecidos do histórico apontam para mais de um Franqueado, o Crédito vai para a Fila como "sem identificação do pagador". CPF ainda não é procurado: só identifica quando for Pagador conhecido confirmado pela Analista (ticket 13).
- **Por quê:** a raiz liga matriz e filiais (CONTEXT, Franqueado); com dois Franqueados a plataforma estaria escolhendo; não há CPF de Pagador conhecido antes das confirmações.
- **Alternativas:** usar o primeiro CNPJ do histórico; aceitar CNPJ parcialmente pontuado; procurar CPF já agora sem ter com o que comparar.

## Ticket 03: precedência entre nosso número e CNPJ

- **Decisão:** o nosso número é avaliado antes do CNPJ. Crédito cujo documento é nosso número de mais de um Título continua na Fila sem cair para a regra de CNPJ.
- **Por quê:** mantém a decisão do ticket 01 (nunca escolher entre Títulos igualmente válidos) e evita que uma regra mais fraca resolva um caso já marcado como ambíguo.
- **Alternativas:** usar o CNPJ para desempatar o nosso número.

## Ticket 03: Franqueado conhecido e Crédito sem título em aberto

- **Decisão:** o motor recebe as raízes de CNPJ de todos os Títulos já guardados, de qualquer execução, além dos Títulos em aberto da execução atual. Crédito identificado cujo Franqueado não tem nenhum Título em aberto vai para a Fila como "Crédito sem título em aberto", sem sugestão; como todo Crédito guardado é reclassificado a cada execução, ele casa quando o Título aparece.
- **Por quê:** um Franqueado cujos Títulos foram todos baixados continua sendo Franqueado; sem lembrar dele, a antecipação nunca seria identificada. O caso só leva à Fila, nunca à Lista.
- **Alternativas:** conhecer só os Franqueados da exportação atual (Crédito sem título em aberto seria inalcançável por documento).

## Ticket 03: Franqueado identificado com valor que não fecha ou que se repete

- **Decisão:** com Títulos em aberto e nenhum de mesmo valor, o Crédito vai para a Fila como "valor não fecha", sugerindo o Título só quando o Franqueado tem um único Título em aberto. Com mais de um Título de mesmo valor, vai como "mais de uma combinação possível", sem sugestão, citando os Títulos na explicação.
- **Por quê:** a precedência da spec põe "valor não fecha" antes de "Crédito sem título em aberto"; sugerir o único Título repete o tratamento do nosso número com valor diferente (ticket 01); com vários Títulos a plataforma não escolhe. Valor único também abrange combinação, por isso o Motivo de combinação. Encargo (ticket 04) e somas (ticket 07) refinam esses casos.
- **Alternativas:** tratar como "Crédito sem título em aberto"; sugerir todos os Títulos de mesmo valor.

## Ticket 04: feriados bancários nacionais

- **Decisão:** são dias não úteis sábado, domingo, os feriados nacionais fixos (1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 25/12, e 20/11 a partir de 2024), segunda e terça de Carnaval, Sexta-feira da Paixão e Corpus Christi, calculados a partir da Páscoa. Quarta-feira de Cinzas, 24/12 e 31/12 contam como dias úteis.
- **Por quê:** é o calendário de feriados bancários nacionais da FEBRABAN; nas datas que ficaram de fora há expediente ou compensação. Calcular pela Páscoa evita uma tabela que precisa ser atualizada todo ano.
- **Alternativas:** tabela de feriados em configuração (manutenção anual); tratar Cinzas, 24/12 e 31/12 como não úteis.

## Ticket 04: cálculo do Encargo previsto

- **Decisão:** atraso é a diferença em dias corridos entre a data do Crédito no Extrato e o Vencimento efetivo. Com atraso, Encargo previsto = multa sobre o valor do Título + juros ao mês pro rata (dias de atraso / 30), cada parcela arredondada ao centavo (meio para cima). Padrões: multa 2%, juros 1% ao mês, tolerância R$ 0,00, em `[encargo]` do `conciliacao.toml` (`multa_percentual`, `juros_ao_mes_percentual`, `tolerancia_reais`); campo desconhecido, negativo, não numérico ou tolerância com fração de centavo recusam a configuração.
- **Por quê:** a spec só fixa a multa de 2%; juros de 1% ao mês é o usual em contrato e a tolerância zero só manda para a Lista o que a regra explica. A data do Crédito é a única data de pagamento que o Extrato traz.
- **Alternativas:** juros de 0% (todo pagamento com juros iria para a Fila); juros compostos ou por dias úteis; contar o atraso do vencimento original.

## Ticket 04: faixa que fecha com o Título

- **Decisão:** o Crédito fecha com o Título quando é igual ao valor do Título (em dia, ou com Encargo não pago se atrasado) ou, se atrasado, quando fica acima do Título e no máximo no Título + Encargo previsto + tolerância; qualquer valor nessa faixa conta como Encargo pago, inclusive só a multa. A tolerância só vale com atraso: sem atraso, qualquer valor acima é Valor a maior. Abaixo do Título é Diferença a menor. Os dois casos vão para a Fila como "valor não fecha", com a explicação dizendo qual. Principal e Encargo aparecem só na explicação.
- **Por quê:** Valor a maior é definido sobre o Encargo previsto, que é zero sem atraso; pagar parte do Encargo (ex.: só a multa) não é motivo para investigar. A spec pede principal e Encargo na explicação, sem coluna própria.
- **Alternativas:** exigir o Encargo exato; aplicar a tolerância também a pagamentos em dia; colunas de principal e Encargo no workbook.

## Ticket 04: Encargo na identificação por CNPJ

- **Decisão:** na identificação por CNPJ, Valor único passa a ser "um só Título em aberto do Franqueado com que o valor fecha, considerando o Encargo". Se fecha com mais de um (ex.: exato num e dentro do Encargo de outro), vai para a Fila como "mais de uma combinação possível". Se não fecha com nenhum, segue "valor não fecha", sugerindo o Título quando é o único e explicando se é Diferença a menor ou Valor a maior.
- **Por quê:** a spec põe "CNPJ + Valor único; Encargo não pago" e "CNPJ; 22.900 + 458 de multa" na Lista; preferir o valor exato seria escolher entre opções válidas.
- **Alternativas:** Encargo só no nosso número; preferir o Título de valor exato.

## Ticket 05: layout exato da exportação Omie

- **Decisão:** o adaptador do Omie aceita só o cabeçalho `customer_name,tax_id,invoice_ref,due_date,amount,paid_flag` com vírgula, valor com ponto e exatamente duas casas sem separador de milhar (`1234.56`), data `aaaa-mm-dd` e CNPJ com 14 dígitos sem pontuação. `paid_flag` diferente de "N" recusa o arquivo com o motivo. Título do Omie não tem nosso número.
- **Por quê:** é o formato da exportação como vem; cada adaptador declara o layout exato (spec) e o resto é recusado (ADR 0005). O tratamento de `paid_flag` repete o do status do Protheus (ticket 01).
- **Alternativas:** aceitar também CNPJ pontuado ou valor sem centavos; ignorar linhas com `paid_flag` "S".

## Ticket 05: nomes do Franqueado

- **Decisão:** os nomes do Franqueado por Sistema de origem vêm das fotografias de Títulos já guardadas, de todas as execuções (`Armazenamento.franqueados()`), sem tabela própria. Os nomes são guardados como vêm; a normalização para a comparação de prefixo fica para o ticket 06. Um nome que deixou de aparecer na exportação continua sendo do Franqueado.
- **Por quê:** a fotografia de Títulos já registra raiz, sistema e nome; uma tabela à parte duplicaria o dado. Manter nomes antigos segue a decisão do ticket 03 de lembrar Franqueados de execuções anteriores.
- **Alternativas:** tabela `franqueados`/`nomes` atualizada a cada execução; considerar só os nomes da exportação atual.

## Ticket 05: Possível duplicidade entre sistemas

- **Decisão:** Títulos em aberto da execução são agrupados por raiz do CNPJ + vencimento (o original, não o efetivo) + valor; o grupo vira um item de Título quando tem Títulos de mais de um Sistema de origem, com todos os Títulos do grupo. O item recebe o identificador estável `D<n>`, ligado ao conjunto de (Sistema de origem, documento) dos Títulos, e fica em `Resultado.itens_de_titulo`, fora de `fila_de_excecoes` (que segue só com Créditos). A duplicidade não muda a classificação dos Créditos: um Crédito que fecha com os dois Títulos vai para a Fila como "mais de uma combinação possível", a não ser que o nosso número aponte um só.
- **Por quê:** a definição do CONTEXT fala de valor e vencimento como estão no Título; a spec conta Créditos e itens de Título separadamente ("Fila com 9 Créditos" e "1 item de Título") e a conferência de soma é só sobre lançamentos do Extrato. Identificador estável é necessário para a decisão da Analista pelo Excel (ticket 13).
- **Alternativas:** comparar pelo Vencimento efetivo; marcar duplicidade também dentro do mesmo sistema; excluir os Títulos duplicados do casamento com Créditos (seria decidir pela Analista).

## Ticket 05: item de Título no workbook

- **Decisão:** os itens de Título aparecem na aba Fila de exceções depois dos Créditos, com Item, Motivo, Títulos sugeridos e Explicação preenchidos e as colunas do lançamento (inclusive Valor) vazias; valor e vencimento ficam na explicação. O Resumo ganha a linha "Itens de Título na Fila" e as linhas por destino continuam contando só lançamentos.
- **Por quê:** a spec põe a Possível duplicidade na Fila; deixar Valor vazio faz a soma da coluna na aba continuar igual à soma dos Créditos da Fila.
- **Alternativas:** aba própria para itens de Título; preencher Valor com o valor do Título.

## Ticket 06: nome do pagador no histórico do Extrato

- **Decisão:** cada adaptador de Extrato diz onde está o nome do pagador no histórico. No Itaú, o nome é o texto depois de "PIX RECEBIDO " ou "TED RECEBIDA "; qualquer outro histórico (depósito, liquidação de cobrança etc.) é tratado como Crédito sem nome. O nome só é procurado depois do nosso número e do CNPJ.
- **Por quê:** o começo do histórico é parte do layout do banco, como o cabeçalho; tentar cada sufixo do histórico como nome acharia "nomes" de uma letra que são prefixo de muitos Franqueados.
- **Alternativas:** testar todos os sufixos do histórico; lista de começos em configuração (o layout já mora no adaptador).

## Ticket 06: normalização e comparação do Nome por prefixo

- **Decisão:** nomes são normalizados em maiúsculas, sem acento, com todo caractere que não é letra ou dígito virando espaço e espaços repetidos colapsados ("Pão & Café Ltda." vira "PAO CAFE LTDA"). O prefixo é por caractere, não por palavra, porque o banco corta no meio da palavra. Os nomes comparados são todos os do Franqueado guardados em execuções anteriores mais os da exportação atual.
- **Por quê:** é a normalização da spec; tratar símbolo como separador faz "&" e "/" sumirem dos dois lados igualmente.
- **Alternativas:** trocar "&" por "E" (o banco da amostra simplesmente remove o símbolo); prefixo por palavra inteira.

## Ticket 06: Motivo do Crédito identificado só por Nome por prefixo

- **Decisão:** com os Franqueados cujo nome tem o nome do Extrato como prefixo: nenhum deles com Título em aberto vira "Crédito sem título em aberto"; nenhum Título deles fecha com o valor (considerando o Encargo) vira "valor não fecha", sugerindo o Título quando há um só entre todos; Títulos de mais de um Franqueado fecham vira "nome ambíguo", sem sugestão; mais de um Título do mesmo Franqueado fecha vira "mais de uma combinação possível", sem sugestão; um só Título fecha vira "pagador provável, primeira vez", com o Título sugerido, mesmo quando o nome era prefixo de mais de um Franqueado (o valor desempatou). Nunca vai para a Lista, porque ainda não existe Pagador conhecido.
- **Por quê:** segue a precedência da spec (valor não fecha, Crédito sem título em aberto, nome ambíguo, pagador provável) e as decisões dos tickets 03 e 04 para o caso de CNPJ; "pagador provável" fica só para o item que está na Fila apenas por falta de confirmação do nome (história 40).
- **Alternativas:** sugerir todos os Títulos no nome ambíguo (pareceria uma combinação); tratar o caso de vários Títulos do mesmo Franqueado como "pagador provável".
- **Exemplo que sai da regra:** na amostra, o PIX de 30/07 (1.850,00) aparece como "Crédito sem título em aberto"; pela regra ele fica "valor não fecha", porque os dois Títulos do Franqueado continuam em aberto na exportação, ainda que um esteja proposto na Lista e o outro sugerido a outro Crédito da Fila. Reservar Títulos já propostos ou sugeridos a outro Crédito não faz parte deste ticket.

## Ticket 06: Crédito que só bate por valor

- **Decisão:** Crédito sem nosso número, CNPJ ou Nome por prefixo procura, entre todos os Títulos em aberto, os que fecham com o valor considerando o Encargo. Com um só, vai para a Fila como "sem identificação do pagador" sugerindo esse Título; com mais de um, mesmo Motivo sem sugestão, citando os Títulos na explicação; com nenhum, mesmo Motivo sem evidência. Nome que não é prefixo de nenhum Franqueado recebe o mesmo tratamento até o parecer da IA (ticket 08). Nosso número de vários Títulos e CNPJs de vários Franqueados continuam sem sugestão (tickets 01 e 03).
- **Por quê:** a spec põe o depósito sem nome com o Título sugerido e "sem identificação do pagador"; com vários Títulos a plataforma não escolhe.
- **Alternativas:** "mais de uma combinação possível" quando o valor aponta vários Títulos (o que falta é o pagador, não a escolha da combinação).

## Ticket 06: evidência e o que falta

- **Decisão:** cada item guarda a evidência como tipos de um conjunto aberto (por enquanto nosso número, CNPJ/CPF, nome por prefixo, só valor), numa tabela própria `itens_evidencias`; o detalhe continua na explicação. O que falta é derivado do Motivo, com um texto fixo por Motivo. A aba Fila de exceções ganha as colunas Evidência e O que falta, entre Títulos sugeridos e Explicação; itens de Título têm Evidência vazia.
- **Por quê:** a spec trata a evidência como tipos para a fase 2 acrescentar "identificador de cobrança"; uma tabela nova é criada em bancos SQLite já existentes sem migração. O que falta depende só da causa, então guardar seria duplicar.
- **Alternativas:** coluna de evidência na tabela `itens` (exigiria migração); texto livre de o que falta por item.
