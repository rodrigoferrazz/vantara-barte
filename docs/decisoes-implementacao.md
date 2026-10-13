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

## Ticket 07: soma exata sem Encargo

- **Decisão:** uma combinação de dois ou mais Títulos fecha só quando o Crédito é igual à soma dos valores dos Títulos. Encargo (pago ou dentro da tolerância) só é considerado para um Título sozinho. Título atrasado dentro de uma combinação que fecha é Encargo não pago, registrado na explicação.
- **Por quê:** a spec fala em "soma exata"; aceitar Encargo em combinação transformaria cada soma numa faixa, multiplicando as combinações que fecham e as chances de a plataforma decidir algo que a Analista deveria ver. Uma soma com Encargo pago vai para a Fila como "valor não fecha".
- **Alternativas:** somar o Encargo previsto de cada Título atrasado à faixa da combinação.

## Ticket 07: Valor único conta Título sozinho e combinações juntos

- **Decisão:** as opções de um Crédito são os Títulos que fecham sozinhos (considerando o Encargo) mais as combinações de dois ou mais Títulos com soma exata, todas do mesmo Franqueado. Uma única opção é Valor único; duas ou mais vão para a Fila como "mais de uma combinação possível", sem sugestão, citando na explicação as opções encontradas. A busca para ao achar a segunda opção.
- **Por quê:** o CONTEXT define Valor único como um só Título ou uma só combinação; um Título que fecha sozinho e uma soma que também fecha são opções igualmente válidas.
- **Alternativas:** preferir o Título sozinho à soma (seria escolher entre opções válidas); listar todas as combinações (custo sem limite).

## Ticket 07: limite da busca de somas

- **Decisão:** o limite conta as combinações examinadas na busca de somas, por Crédito e por Franqueado, em `[somas] limite_de_combinacoes` do `conciliacao.toml` (padrão 100.000; inteiro maior que zero, campo desconhecido recusa a configuração). Atingido o limite, o Crédito vai para a Fila como "mais de uma combinação possível", mesmo que já tenha achado uma opção. Na identificação por Nome por prefixo, Franqueado com limite atingido conta como Franqueado com que o valor fecha, para decidir entre "nome ambíguo" e os outros Motivos.
- **Por quê:** a spec manda o limite explícito e o destino quando atingido; sem terminar a busca não há como garantir que a opção encontrada é única. 100.000 combinações custam décimos de segundo por Crédito e cobrem com folga Franqueados com dezenas de Títulos em aberto.
- **Alternativas:** limitar o tamanho da combinação ou o número de Títulos por Franqueado (não mede o custo real da busca); limite por execução inteira (um Franqueado grande consumiria o limite dos outros).

## Ticket 07: Título proposto na Lista para mais de um Crédito

- **Decisão:** depois de classificar todos os Créditos, os que iriam para a Lista propondo um Título que outro Crédito da Lista também propõe vão todos para a Fila como "mais de uma combinação possível", mantendo os Títulos como sugestão e citando os outros Créditos na explicação.
- **Por quê:** é o único caminho por onde vários Créditos para vários Títulos (N:M) ou para o mesmo Título chegariam à Lista; a Lista nunca pode levar a baixar o mesmo Título duas vezes. O Motivo mais próximo da lista fixa é o de escolha entre combinações.
- **Alternativas:** manter na Lista só o primeiro Crédito (seria escolher); reservar também Títulos sugeridos na Fila (fora do escopo, ver ticket 06).

## Ticket 07: Crédito sem pagador identificado não procura somas

- **Decisão:** a busca de somas só acontece para o Franqueado identificado por CNPJ ou por Nome por prefixo. Crédito que só bate por valor continua procurando apenas Títulos sozinhos, entre todos os em aberto.
- **Por quê:** a spec restringe a soma ao mesmo Franqueado; sem pagador não há Franqueado, e somar Títulos de todos os Franqueados é o que a spec pede para evitar. O filtro por valor antes do parecer da LLM (ticket 08) pode reutilizar a busca por Franqueado candidato.
- **Alternativas:** procurar somas em cada Franqueado para Créditos só por valor.
- **Exemplo que sai da regra por enquanto:** na amostra, o TED de 14/07 (47.630,50, nome que não é prefixo) aparece com a sugestão de NF 104533 + NF 104588; hoje fica sem sugestão, como "sem identificação do pagador", até o ticket 08 aplicar o filtro por valor com somas ao Franqueado candidato da LLM.

## Ticket 08: quando a IA é chamada e sobre quais Franqueados

- **Decisão:** a IA só é chamada para Crédito com nome do pagador que não é Nome por prefixo de nenhum Franqueado. Os candidatos são os Franqueados com que o valor fecha pela mesma busca da identificação por nome: Título sozinho considerando o Encargo, soma exata de Títulos do Franqueado, ou limite da busca atingido. A IA recebe o nome do Extrato e todos os nomes do candidato em todos os Sistemas de origem, uma chamada por candidato. Sem candidato, não há chamada e o Crédito segue como "sem identificação do pagador". Nome que é prefixo de algum Franqueado continua no caminho do ticket 06, sem IA, mesmo quando o valor fecha só com outro Franqueado.
- **Por quê:** a spec manda filtrar por valor antes do parecer e restringir somas ao mesmo Franqueado; reutilizar a busca do ticket 07 mantém as duas identificações coerentes. Manter o caminho do prefixo preserva a precedência já decidida no ticket 06 ("valor não fecha" antes de qualquer outro Motivo).
- **Alternativas:** perguntar à IA sobre todos os Franqueados (custo e risco de a IA escolher entre muitos); chamar a IA também quando o nome é prefixo de um Franqueado cujo valor não fecha.

## Ticket 08: destino conforme o parecer

- **Decisão:** tudo que passa pela IA vai para a Fila. Sim para um só candidato: com Valor único dele, "pagador provável, primeira vez" sugerindo o Título ou a combinação; com várias opções ou limite atingido, "mais de uma combinação possível" sem sugestão. Sim para mais de um candidato: "nome ambíguo" sem sugestão. Nenhum sim: "sem identificação do pagador" com a sugestão por valor, que é a única opção entre todos os candidatos (Título sozinho ou soma), ou nenhuma quando há mais de uma. A evidência é "parecer de LLM" quando há sim e "só valor" quando não há.
- **Por quê:** o parecer positivo ocupa o lugar do Nome por prefixo; o item fica na Fila só por falta de confirmação do nome (história 40). O parecer negativo não é evidência da sugestão, por isso a evidência volta a ser só valor.
- **Alternativas:** parecer positivo como "nome ambíguo" sempre (perderia a métrica do que o aprendizado resolve); sugestão por valor só com Títulos sozinhos, como no Crédito sem nome (perderia a soma do Franqueado candidato).

## Ticket 08: IA indisponível

- **Decisão:** cada parecer é sim, não ou "IA indisponível", com modelo e versão do prompt, guardado por Franqueado candidato numa tabela própria `itens_pareceres`. Ollama fora do ar, erro HTTP, tempo esgotado ou resposta fora do formato pedido viram "IA indisponível" com o motivo. Se algum candidato ficou sem parecer, o item inteiro é tratado como sem parecer: "sem identificação do pagador" com a sugestão por valor, marcado "IA indisponível". A marca do item e as contagens do Resumo são derivadas dos pareceres guardados. A plataforma tenta a IA em cada Crédito, sem desistir depois da primeira falha.
- **Por quê:** um sim ao lado de um candidato sem resposta não garante que o nome não é também do outro; tratar resposta malformada como indisponível evita decidir com base em texto que não seguiu o formato. Tabela nova não exige migração (mesmo padrão do ticket 06).
- **Alternativas:** usar os pareceres que vieram e ignorar os indisponíveis; parar de chamar a IA depois da primeira falha na execução (uma falha passageira marcaria todo o resto).

## Ticket 08: configuração da IA

- **Decisão:** seção `[ia]` do `conciliacao.toml` com `endereco`, `modelo` e `tempo_limite_segundos`, todos obrigatórios dentro da seção e campo desconhecido recusado. Sem a seção, a execução roda e os itens que precisariam de parecer ficam "IA indisponível" com o motivo "falta a seção [ia] na configuração". O padrão do projeto é `qwen2.5:3b` (cerca de 2 GB, cabe no M2 de 8 GB) com tempo limite de 120 s, que cobre o carregamento do modelo na primeira chamada.
- **Por quê:** endereço e modelo não podem estar no código; a falta da IA nunca para a conciliação, e o Resumo mostra a situação.
- **Alternativas:** recusar a configuração sem `[ia]` (pararia a execução por causa da IA); valores padrão no código.

## Ticket 08: parecer no workbook e no Resumo

- **Decisão:** a aba Fila de exceções ganha a coluna "Parecer da IA" no fim, com Franqueado, resposta, explicação, modelo e versão do prompt de cada parecer; a explicação do item também cita o parecer. O Resumo ganha a linha "IA (parecer de nome)": funcionando com N itens, indisponível com N itens marcados, ou não foi necessária.
- **Por quê:** a spec pede o parecer exibido e destacado no item e o Resumo dizendo se a IA estava funcionando. Coluna no fim não mexe nas colunas existentes.
- **Alternativas:** parecer só dentro da explicação (não fica destacado).

## Ticket 08: prompt e teste de integração

- **Decisão:** o prompt (versão `nome-v1`) pede comparação palavra por palavra, aceitando abreviação como começo da palavra e ignorando palavras genéricas, com saída estruturada `{explicacao, pertence}` (explicação antes da resposta) e temperatura 0. O teste que chama o Ollama real é marcado `integracao`, fica fora da suíte padrão (`uv run pytest -m integracao` para rodar) e é pulado se o Ollama ou o modelo não estiver disponível.
- **Por quê:** num conjunto de 9 pares de nomes inventados, o `qwen2.5:3b` acertou 6 com esse prompt; com a primeira versão, que só descrevia a tarefa, respondia sim para todos os nomes sem relação. Errar para "não" mantém a sugestão por valor e só muda o Motivo; errar para "sim" daria um "pagador provável" falso.
- **Alternativas:** exemplos dentro do prompt (few-shot), que pioraram para 4 de 9; modelo maior (não cabe no M2 de 8 GB com folga).
- **Exemplo que sai da regra:** na amostra, a spec espera "pagador provável, primeira vez" com parecer positivo para TED DOCE PONTO COM ALIME e PIX SABOR CIA. O `qwen2.5:3b` com este prompt responde "não" nos dois, então ficam "sem identificação do pagador", mantendo as sugestões NF 104533 + NF 104588 e NF 104552. É limitação do modelo, não da regra; o prompt não foi ajustado aos nomes da amostra.

## Ticket 09: última data de cada conta e conta sem Extrato

- **Decisão:** a última data de uma conta configurada é a do lançamento mais recente (Crédito ou débito) já guardado dela, de qualquer execução. A Data de referência é a menor entre as contas configuradas (banco + conta, sem repetir). Se alguma conta configurada nunca teve Extrato, não há Data de referência e a Lista de cobrança sai vazia; o Resumo mostra "sem Data de referência" e aponta a conta "sem Extrato". Em empate, todas as contas com a menor data aparecem como as que seguram.
- **Por quê:** a spec quer que um Extrato atrasado nunca mande pagador para cobrança; uma conta sem Extrato nenhum é o caso extremo. Usar todo o histórico guardado evita que uma execução só com o Extrato de uma conta faça a data de outra "sumir".
- **Alternativas:** ignorar contas sem Extrato (cobraria quem pode ter pago nelas); usar só os Extratos da execução (a data dependeria de quais arquivos vieram naquele dia).

## Ticket 09: o que é Crédito candidato

- **Decisão:** um Título tem Crédito candidato quando algum item da Lista de baixa ou da Fila de exceções o propõe, o sugere ou o cita como possível destino do Crédito: opções de "mais de uma combinação possível" e "nome ambíguo", Títulos comparados em "valor não fecha", nosso número de mais de um Título e Títulos que só o valor aponta. A classificação ganhou `citados` para carregar esses Títulos sem virar sugestão. Título com Crédito candidato sai da cobrança e aparece em "em análise", com os itens dos Créditos.
- **Por quê:** o ticket diz "na Lista ou na Fila", e a história 43 quer que nunca se cobre quem já pagou; um Crédito que fecha com dois Títulos sem saber qual é candidato dos dois.
- **Alternativas:** só Títulos sugeridos (cobraria Títulos que um Crédito pendente pode quitar); só a Fila como "em análise", como na contagem da amostra.
- **Exemplo que sai da regra:** a amostra de julho espera 9 Títulos em análise, que são só os sugeridos na Fila. Pela regra do ticket, os Títulos propostos na Lista de baixa ainda não confirmada também ficam em análise, e a amostra dá 14 (NF 104580 fica fora por estar em Possível duplicidade). O ticket 17 precisa decidir isso com o usuário.

## Ticket 09: vencido, boleto e janela de compensação

- **Decisão:** Título vencido é o de Vencimento efetivo estritamente antes da Data de referência. Boleto é o Título com nosso número; ele só entra na cobrança depois do segundo dia útil seguinte ao Vencimento efetivo (vencido na quinta, com sexta e segunda de compensação, é cobrável a partir da terça). A janela de 2 dias úteis é constante do motor, porque a spec a fixa.
- **Por quê:** no dia do Vencimento efetivo o pagamento ainda está em dia; o nosso número é o que identifica a Cobrança do boleto nos dados que existem hoje.
- **Alternativas:** usar a coluna "tipo" do Protheus (é Produto/Royalty/Serviço, não meio de pagamento); janela em configuração (a spec não pede).

## Ticket 09: Possível duplicidade fora da cobrança e de "em análise"

- **Decisão:** Títulos de uma Possível duplicidade não aparecem na Lista de cobrança nem em "em análise", mesmo com Crédito candidato; continuam como item de Título na Fila.
- **Por quê:** a spec diz "sem duplicidade" e o item de Título já pede a decisão à Analista; mostrar o mesmo Título em dois lugares do time de cobrança só confundiria.
- **Alternativas:** mostrá-los em "em análise" quando têm Crédito candidato.

## Ticket 09: Saldo antes das decisões

- **Decisão:** enquanto não há baixa confirmada na plataforma (tickets 12 e 14), o Saldo de cada Título é o valor da exportação atual do ERP. A Lista de cobrança guarda o Saldo por Título na execução, para que o cálculo pelas decisões entre depois sem mudar as saídas.
- **Por quê:** pelo CONTEXT, sem baixas confirmadas o Saldo é o valor, e um valor que mudou no ERP é o novo Saldo.
- **Alternativas:** antecipar o registro de decisões só para este cálculo (escopo do ticket 12).

## Ticket 09: Lista de cobrança no workbook e no Resumo

- **Decisão:** a aba "Lista de cobrança" vem logo depois da Fila de exceções, com Título, Sistema de origem, Franqueado, CNPJ, Vencimento, Vencimento efetivo, Valor e Saldo; abaixo, depois de uma linha vazia, o bloco "Em análise" com as mesmas colunas e "Créditos candidatos" (identificadores dos itens). O Resumo ganha "Data de referência", "Conta que segura a Data de referência", "Lista de cobrança" e "Títulos em análise" (quantidade e Saldo). A Data de referência e a cobrança ficam guardadas por execução (`ultimas_datas_das_contas`, `cobranca`, `cobranca_creditos_candidatos`). O teste do comando que listava exatamente as abas passou a incluir "Lista de cobrança".
- **Por quê:** a spec ordena as abas assim e pede "em análise" à parte na mesma aba; o resultado guardado é a única origem das saídas.
- **Alternativas:** aba separada para "em análise"; uma coluna de situação numa tabela só (não fica "à parte").
