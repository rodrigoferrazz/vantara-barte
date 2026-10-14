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
- **Substituída:** ver Correção: CPF ou CNPJ desconhecido no histórico

## Ticket 03: precedência entre nosso número e CNPJ

- **Decisão:** o nosso número é avaliado antes do CNPJ. Crédito cujo documento é nosso número de mais de um Título continua na Fila sem cair para a regra de CNPJ.
- **Por quê:** mantém a decisão do ticket 01 (nunca escolher entre Títulos igualmente válidos) e evita que uma regra mais fraca resolva um caso já marcado como ambíguo.
- **Alternativas:** usar o CNPJ para desempatar o nosso número.

## Ticket 03: Franqueado conhecido e Crédito sem título em aberto

- **Decisão:** o motor recebe as raízes de CNPJ de todos os Títulos já guardados, de qualquer execução, além dos Títulos em aberto da execução atual. Crédito identificado cujo Franqueado não tem nenhum Título em aberto vai para a Fila como "Crédito sem título em aberto", sem sugestão; como todo Crédito guardado é reclassificado a cada execução, ele casa quando o Título aparece.
- **Por quê:** um Franqueado cujos Títulos foram todos baixados continua sendo Franqueado; sem lembrar dele, a antecipação nunca seria identificada. O caso só leva à Fila, nunca à Lista.
- **Alternativas:** conhecer só os Franqueados da exportação atual (Crédito sem título em aberto seria inalcançável por documento).
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto

## Ticket 03: Franqueado identificado com valor que não fecha ou que se repete

- **Decisão:** com Títulos em aberto e nenhum de mesmo valor, o Crédito vai para a Fila como "valor não fecha", sugerindo o Título só quando o Franqueado tem um único Título em aberto. Com mais de um Título de mesmo valor, vai como "mais de uma combinação possível", sem sugestão, citando os Títulos na explicação.
- **Por quê:** a precedência da spec põe "valor não fecha" antes de "Crédito sem título em aberto"; sugerir o único Título repete o tratamento do nosso número com valor diferente (ticket 01); com vários Títulos a plataforma não escolhe. Valor único também abrange combinação, por isso o Motivo de combinação. Encargo (ticket 04) e somas (ticket 07) refinam esses casos.
- **Alternativas:** tratar como "Crédito sem título em aberto"; sugerir todos os Títulos de mesmo valor.
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto

## Ticket 04: feriados bancários nacionais

- **Decisão:** são dias não úteis sábado, domingo, os feriados nacionais fixos (1/1, 21/4, 1/5, 7/9, 12/10, 2/11, 15/11, 25/12, e 20/11 a partir de 2024), segunda e terça de Carnaval, Sexta-feira da Paixão e Corpus Christi, calculados a partir da Páscoa. Quarta-feira de Cinzas, 24/12 e 31/12 contam como dias úteis.
- **Por quê:** é o calendário de feriados bancários nacionais da FEBRABAN; nas datas que ficaram de fora há expediente ou compensação. Calcular pela Páscoa evita uma tabela que precisa ser atualizada todo ano.
- **Alternativas:** tabela de feriados em configuração (manutenção anual); tratar Cinzas, 24/12 e 31/12 como não úteis.

## Ticket 04: cálculo do Encargo previsto

- **Decisão:** atraso é a diferença em dias corridos entre a data do Crédito no Extrato e o Vencimento efetivo. Com atraso, Encargo previsto = multa sobre o valor do Título + juros ao mês pro rata (dias de atraso / 30), cada parcela arredondada ao centavo (meio para cima). Padrões: multa 2%, juros 1% ao mês, tolerância R$ 0,00, em `[encargo]` do `conciliacao.toml` (`multa_percentual`, `juros_ao_mes_percentual`, `tolerancia_reais`); campo desconhecido, negativo, não numérico ou tolerância com fração de centavo recusam a configuração.
- **Por quê:** a spec só fixa a multa de 2%; juros de 1% ao mês é o usual em contrato e a tolerância zero só manda para a Lista o que a regra explica. A data do Crédito é a única data de pagamento que o Extrato traz.
- **Alternativas:** juros de 0% (todo pagamento com juros iria para a Fila); juros compostos ou por dias úteis; contar o atraso do vencimento original.
- **Substituída:** ver Correção: juros zero por padrão

## Ticket 04: faixa que fecha com o Título

- **Decisão:** o Crédito fecha com o Título quando é igual ao valor do Título (em dia, ou com Encargo não pago se atrasado) ou, se atrasado, quando fica acima do Título e no máximo no Título + Encargo previsto + tolerância; qualquer valor nessa faixa conta como Encargo pago, inclusive só a multa. A tolerância só vale com atraso: sem atraso, qualquer valor acima é Valor a maior. Abaixo do Título é Diferença a menor. Os dois casos vão para a Fila como "valor não fecha", com a explicação dizendo qual. Principal e Encargo aparecem só na explicação.
- **Por quê:** Valor a maior é definido sobre o Encargo previsto, que é zero sem atraso; pagar parte do Encargo (ex.: só a multa) não é motivo para investigar. A spec pede principal e Encargo na explicação, sem coluna própria.
- **Alternativas:** exigir o Encargo exato; aplicar a tolerância também a pagamentos em dia; colunas de principal e Encargo no workbook.

## Ticket 04: Encargo na identificação por CNPJ

- **Decisão:** na identificação por CNPJ, Valor único passa a ser "um só Título em aberto do Franqueado com que o valor fecha, considerando o Encargo". Se fecha com mais de um (ex.: exato num e dentro do Encargo de outro), vai para a Fila como "mais de uma combinação possível". Se não fecha com nenhum, segue "valor não fecha", sugerindo o Título quando é o único e explicando se é Diferença a menor ou Valor a maior.
- **Por quê:** a spec põe "CNPJ + Valor único; Encargo não pago" e "CNPJ; 22.900 + 458 de multa" na Lista; preferir o valor exato seria escolher entre opções válidas.
- **Alternativas:** Encargo só no nosso número; preferir o Título de valor exato.
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto

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
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto

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
- **Substituída:** ver Correção: IA chamada por Franqueado candidato

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
- **Substituída:** ver Correção: prompt e modelo da IA

## Ticket 08: parecer no workbook e no Resumo

- **Decisão:** a aba Fila de exceções ganha a coluna "Parecer da IA" no fim, com Franqueado, resposta, explicação, modelo e versão do prompt de cada parecer; a explicação do item também cita o parecer. O Resumo ganha a linha "IA (parecer de nome)": funcionando com N itens, indisponível com N itens marcados, ou não foi necessária.
- **Por quê:** a spec pede o parecer exibido e destacado no item e o Resumo dizendo se a IA estava funcionando. Coluna no fim não mexe nas colunas existentes.
- **Alternativas:** parecer só dentro da explicação (não fica destacado).

## Ticket 08: prompt e teste de integração

- **Decisão:** o prompt (versão `nome-v1`) pede comparação palavra por palavra, aceitando abreviação como começo da palavra e ignorando palavras genéricas, com saída estruturada `{explicacao, pertence}` (explicação antes da resposta) e temperatura 0. O teste que chama o Ollama real é marcado `integracao`, fica fora da suíte padrão (`uv run pytest -m integracao` para rodar) e é pulado se o Ollama ou o modelo não estiver disponível.
- **Por quê:** num conjunto de 9 pares de nomes inventados, o `qwen2.5:3b` acertou 6 com esse prompt; com a primeira versão, que só descrevia a tarefa, respondia sim para todos os nomes sem relação. Errar para "não" mantém a sugestão por valor e só muda o Motivo; errar para "sim" daria um "pagador provável" falso.
- **Alternativas:** exemplos dentro do prompt (few-shot), que pioraram para 4 de 9; modelo maior (não cabe no M2 de 8 GB com folga).
- **Exemplo que sai da regra:** na amostra, a spec espera "pagador provável, primeira vez" com parecer positivo para TED DOCE PONTO COM ALIME e PIX SABOR CIA. O `qwen2.5:3b` com este prompt responde "não" nos dois, então ficam "sem identificação do pagador", mantendo as sugestões NF 104533 + NF 104588 e NF 104552. É limitação do modelo, não da regra; o prompt não foi ajustado aos nomes da amostra.
- **Substituída:** ver Correção: prompt e modelo da IA

## Ticket 09: última data de cada conta e conta sem Extrato

- **Decisão:** a última data de uma conta configurada é a do lançamento mais recente (Crédito ou débito) já guardado dela, de qualquer execução. A Data de referência é a menor entre as contas configuradas (banco + conta, sem repetir). Se alguma conta configurada nunca teve Extrato, não há Data de referência e a Lista de cobrança sai vazia; o Resumo mostra "sem Data de referência" e aponta a conta "sem Extrato". Em empate, todas as contas com a menor data aparecem como as que seguram.
- **Por quê:** a spec quer que um Extrato atrasado nunca mande pagador para cobrança; uma conta sem Extrato nenhum é o caso extremo. Usar todo o histórico guardado evita que uma execução só com o Extrato de uma conta faça a data de outra "sumir".
- **Alternativas:** ignorar contas sem Extrato (cobraria quem pode ter pago nelas); usar só os Extratos da execução (a data dependeria de quais arquivos vieram naquele dia).

## Ticket 09: o que é Crédito candidato

- **Decisão:** um Título tem Crédito candidato quando algum item da Lista de baixa ou da Fila de exceções o propõe, o sugere ou o cita como possível destino do Crédito: opções de "mais de uma combinação possível" e "nome ambíguo", Títulos comparados em "valor não fecha", nosso número de mais de um Título e Títulos que só o valor aponta. A classificação ganhou `citados` para carregar esses Títulos sem virar sugestão. Título com Crédito candidato sai da cobrança e aparece em "em análise", com os itens dos Créditos.
- **Por quê:** o ticket diz "na Lista ou na Fila", e a história 43 quer que nunca se cobre quem já pagou; um Crédito que fecha com dois Títulos sem saber qual é candidato dos dois.
- **Alternativas:** só Títulos sugeridos (cobraria Títulos que um Crédito pendente pode quitar); só a Fila como "em análise", como na contagem da amostra.
- **Exemplo que sai da regra:** a amostra de julho espera 9 Títulos em análise, que são só os sugeridos na Fila. Pela regra do ticket, os Títulos propostos na Lista de baixa ainda não confirmada também ficam em análise, e a amostra dá 14 (NF 104580 fica fora por estar em Possível duplicidade). O ticket 17 precisa decidir isso com o usuário.
- **Substituída:** ver Correção: "em análise" só com Crédito candidato na Fila

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

## Ticket 10: Franqueado do Crédito na causa raiz

- **Decisão:** o motor atribui a cada Crédito o Franqueado que a evidência do pagador aponta sozinha: o do Título do nosso número (ou dos Títulos, quando todos são do mesmo Franqueado), o da raiz do CNPJ, o único Franqueado do Nome por prefixo (ou o único entre eles com que o valor fecha, quando o valor desempata) e o único Franqueado com parecer "sim" da IA. Só valor, CNPJs de vários Franqueados, nome ambíguo, parecer negativo e IA indisponível ficam sem Franqueado e formam o grupo "sem Franqueado". A atribuição e o canal ficam numa tabela própria `itens_atribuicoes`.
- **Por quê:** a causa raiz mede de quem é o problema; um Título sugerido só pelo valor não diz quem pagou. Desempate pelo valor segue a decisão do ticket 06 para "pagador provável, primeira vez". Tabela nova evita migração (padrão dos tickets 06 e 08).
- **Alternativas:** usar o Franqueado do Título sugerido mesmo quando só o valor aponta (atribuiria depósitos não identificados a um Franqueado sem prova); coluna nova em `itens` (exigiria migração).

## Ticket 10: canal inferido pelo adaptador do Extrato

- **Decisão:** cada adaptador de Extrato diz o canal pelo começo do histórico. No Itaú: "PIX RECEBIDO" é Pix, "TED RECEBIDA" é TED, "LIQUIDACAO COBRANCA" é boleto e "DEPOSITO" é depósito; qualquer outro histórico, ou banco sem adaptador, é "canal não identificado". O canal é calculado na classificação e guardado com o item, para que a saída de uma execução não mude se o adaptador mudar depois.
- **Por quê:** o texto do histórico é parte do layout do banco, como o nome do pagador (ticket 06); um canal desconhecido não é adivinhado (ADR 0005), mas aparece como categoria própria para a soma fechar em 100%.
- **Alternativas:** inferir o canal pelo nosso número ou pela evidência (boleto sem nosso número reconhecido sumiria); recalcular o canal ao carregar o resultado.

## Ticket 10: categorias, ordem e escopo do relatório de causa raiz

- **Decisão:** o relatório conta só os Créditos da Fila de exceções; itens de Título (Possível duplicidade) ficam fora, porque não têm valor de Crédito. A agregação por Motivo lista sempre os oito Motivos na ordem da spec, inclusive os zerados, e a por canal lista sempre os quatro canais mais "canal não identificado". Franqueados e bancos são ordenados por concentração: quantidade de Créditos, depois valor, depois nome; o grupo "sem Franqueado" vem por último, fora da ordenação. Franqueado aparece com todos os seus nomes nos Sistemas de origem e a raiz. A aba "Causa raiz" vem depois da Lista de cobrança, com quatro blocos (Grupo, Quantidade, % quantidade, Valor, % valor) e uma linha Total de 100%; com a Fila vazia, os percentuais ficam vazios. O teste do comando que lista exatamente as abas passou a incluir "Causa raiz".
- **Por quê:** a spec pede Motivos estáveis mês a mês e soma de 100% sobre os Créditos; quantidade mede o trabalho da Analista e o valor desempata; o grupo sem Franqueado não é alguém a abordar. "Possível fonte não integrada" aparece como categoria própria, mas nenhuma regra do motor atribui esse Motivo hoje: a spec não define como detectá-lo, e Conciliado fora é do ticket 13.
- **Alternativas:** ordenar por valor; incluir itens de Título contando zero de valor; mostrar só categorias com ocorrência; inventar uma regra de detecção de fonte não integrada.
- **Substituída:** ver Correção: Possível fonte não integrada classificada pela Analista

## Ticket 11: gerador como módulo, proporções como frações dos Títulos

- **Decisão:** o gerador é o módulo `conciliacao.gerador`, chamado por `gerar_dados_sinteticos(ConfiguracaoDoGerador(semente=...))`, sem comando de linha nem seção no `conciliacao.toml`. As proporções ficam na dataclass `Proporcoes` e são frações do número de Títulos (`unidade_norte` é fração dos Franqueados, só no Omie; `soma_de_titulos` conta Créditos, cada um pagando 2 ou 3 Títulos). O que sobra é pago por boleto em dia (Protheus) ou Pix/TED com CNPJ (Omie). Proporção fora de 0 a 1, frações de Títulos somando mais de 1 ou quantidade que os dados não comportam recusam a geração com `ConfiguracaoDoGeradorInvalida`, em vez de gerar menos casos sem avisar.
- **Por quê:** a spec só pede semente fixa e proporções configuráveis para os testes; um terceiro comando não está na spec (dois comandos). Recusar segue o "nunca adivinhar" (ADR 0005).
- **Alternativas:** comando `gerar-sinteticos` com TOML; gerar menos casos quando faltam Títulos.

## Ticket 11: quatro contas no layout do Itaú

- **Decisão:** os Extratos das 4 contas são todos no layout do Itaú, com 4 contas Itaú na configuração (`extrato_itau_<conta>_*.csv`). Liquidações de boleto entram na primeira conta; Pix, TED e depósitos em qualquer uma. Os primeiros débitos são uma tarifa no último dia útil de cada conta, para todas fecharem no mesmo dia.
- **Por quê:** só existe adaptador do Itaú; inventar layouts dos outros 3 bancos violaria o "nunca inferir layout" e esses arquivos seriam recusados (spec, Out of Scope), e o critério pede arquivos aceitos sem ajuste.
- **Alternativas:** layouts inventados para outros bancos (recusados hoje); uma conta só.

## Ticket 11: gabarito garantido pela construção, com checagem conservadora

- **Decisão:** cada Crédito é gerado a partir de um caso e o gabarito traz o destino, o Motivo, o Franqueado pagador, o nome do Extrato e os Títulos que ele realmente paga. Antes de aceitar um caso, o gerador confere: as opções do valor entre os Títulos do Franqueado (Título sozinho numa faixa acima do Encargo previsto de qualquer atraso dentro do mês, e somas exatas de 2 ou mais) são exatamente uma (Lista, nome truncado, abreviado e invertido) ou nenhuma (parcial por CNPJ, antecipação); o Nome por prefixo, com a normalização da plataforma, aponta só o Franqueado (truncado) ou nenhum (abreviado e invertido); nenhum Título é pago por dois Créditos. Se não passa, tenta outro Título. A IA falsa dos testes responde sim só para o nome do Extrato gerado a partir daquele Franqueado.
- **Por quê:** o gabarito precisa ser verdade sem rodar o motor; a faixa larga só rejeita casos a mais, nunca aceita um ambíguo. A normalização é a definição de Nome por prefixo do CONTEXT, não regra do motor.
- **Alternativas:** calcular o gabarito com o próprio motor (teste tautológico); confiar no acaso dos valores (colisões de soma e de Encargo acontecem com 1.900 Títulos).

## Ticket 11: o que os testes de volume comparam

- **Decisão:** na Lista de baixa, destino e Títulos de cada item precisam bater com o gabarito. Para todo lançamento, destino e Motivo precisam bater. Os Títulos sugeridos na Fila não são comparados. O teste de tempo aceita até 60 s; a execução com ~1.900 Títulos leva cerca de 2 s no M2.
- **Por quê:** a sugestão de um Crédito que só bate por valor depende de outros Títulos que fecham por coincidência, e a spec só exige precisão na Lista. Comparar destino e Motivo de tudo garante que o gabarito descreve os casos que diz gerar.
- **Alternativas:** comparar só a Lista (o gerador poderia gerar casos que nunca chegam ao destino pretendido); comparar também as sugestões da Fila.
- **Exemplo que sai da regra:** a história 27 trata a antecipação como "Crédito sem título em aberto". Numa execução só, o Franqueado identificado sempre tem outros Títulos em aberto, então pela decisão do ticket 06 a antecipação vai como "valor não fecha", sem Título, e é isso que o gabarito espera.
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto

## Ticket 12: de onde vem o workbook lido de volta

- **Decisão:** a execução recebe opcionalmente o workbook anterior (`workbook_anterior`) e aplica as decisões dele antes de rodar o motor, dentro da mesma transação. O comando lê o workbook do caminho de `--saida`, se existir, antes de gerar o novo por cima.
- **Por quê:** a Analista trabalha no arquivo que a plataforma gerou; ler o mesmo caminho evita mais uma opção na linha de comando. Na mesma transação, uma conferência de soma que falha desfaz também as decisões.
- **Alternativas:** opção `--decisoes` separada; pasta de decisões monitorada (substituída pelo ADR 0006).

## Ticket 12: quem e quando de uma decisão do Excel

- **Decisão:** o autor é a propriedade "última alteração por" do arquivo, que o Excel grava ao salvar, e o momento é a data de modificação do arquivo (ou o momento da leitura, se faltar). Workbook sem autor não foi salvo por ninguém depois de gerado: nenhuma decisão é aplicada e o Resumo avisa.
- **Por quê:** a decisão precisa de autor para ser auditável, e o "confirmar" pré-preenchido não pode confirmar o lote sozinho só porque a Analista não abriu o arquivo.
- **Alternativas:** campo "Analista" para preencher no Resumo (uma ação a mais por dia); opção `--analista` no comando (registra quem rodou, não quem decidiu).

## Ticket 12: workbook de outra execução e linhas inválidas

- **Decisão:** só se aplicam decisões de um workbook cuja linha "Execução" do Resumo é a última execução guardada; senão nada é aplicado e o Resumo avisa. Na aba Lista de baixa, "confirmar" confirma; célula vazia ou "rejeitar" rejeita (exige motivo); qualquer outro texto, item que não está na Lista daquela execução e item repetido não são aplicados e viram aviso. A evidência, a explicação, a regra e os Títulos gravados na decisão vêm do item guardado da execução, não do texto do workbook.
- **Por quê:** o identificador é estável entre execuções, mas a proposta pode mudar; decidir sobre uma proposta que não é a mostrada seria aplicar algo que a Analista não viu. Na dúvida, não aplicar e explicar (ADR 0005).
- **Alternativas:** aplicar workbooks antigos item a item quando a proposta não mudou; tratar texto desconhecido como rejeição.

## Ticket 12: efeito da confirmação

- **Decisão:** Crédito confirmado deixa de ser Crédito vivo (não é mais classificado nem entra na conferência de soma das execuções seguintes) e os Títulos confirmados, identificados por Sistema de origem + documento, saem dos Títulos em aberto que vão para o motor e para a Lista de cobrança, mesmo que ainda apareçam na exportação.
- **Por quê:** a Lista só tem pagamentos que quitam os Títulos (Diferença a menor vai para a Fila), então o Saldo de um Título confirmado é zero; mantê-lo em aberto permitiria propô-lo para outro Crédito ou cobrá-lo. Mostrar esses Títulos como Aguardando baixa no ERP fica para o ticket 14.
- **Alternativas:** manter os Títulos em aberto até sumirem da exportação (arriscaria baixar o mesmo Título duas vezes).

## Ticket 12: par rejeitado e destino do Crédito

- **Decisão:** a rejeição de uma proposta registra um par rejeitado para cada Título dela. O motor recebe os pares e classifica o Crédito como se esses Títulos não estivessem em aberto para ele; a explicação cita a rejeição e o motivo. Se mesmo assim o Crédito cairia na Lista com outro Título, ele vai para a Fila como "mais de uma combinação possível", com o novo Título como sugestão.
- **Por quê:** o ticket manda o Crédito rejeitado para a Fila e a Lista é confiada sem investigação; uma proposta de regra já errada uma vez para esse Crédito não deve voltar à Lista. "Mais de uma combinação possível" é o Motivo da lista fixa que descreve o caso: a regra fechou com mais de um Título e a Analista escolhe.
- **Alternativas:** deixar a nova proposta ir para a Lista; rejeitar só a combinação inteira em propostas por soma (deixaria os mesmos Títulos voltarem em outra combinação).

## Ticket 12: regra que gerou a proposta

- **Decisão:** a Classificação da Lista passa a carregar a regra (nosso número + valor; CNPJ/CPF + Valor único; CNPJ/CPF + soma exata), guardada numa tabela própria do item e copiada para a decisão com a evidência e a explicação mostradas. Pareceres de LLM não são copiados porque a Lista nunca tem parecer.
- **Por quê:** a explicação é texto livre; a regra como valor fixo permite auditoria e as métricas do ticket 16. Tabela própria segue o padrão de não alterar tabelas existentes de estados já criados.
- **Alternativas:** usar só a evidência como regra (não separa Título único de soma).

## Ticket 12: lista para baixa manual e Resumo

- **Decisão:** aba "Baixa manual no ERP", logo depois da Lista de baixa, com uma linha por Título confirmado nesta execução: Título, Sistema de origem, Franqueado, CNPJ, Vencimento, Valor principal, Encargo (o que o Crédito pagou acima do principal; zero em soma de Títulos e em Encargo não pago), Item, data, banco, conta e valor do Crédito. O Resumo ganha "Decisões lidas do Excel" (confirmadas, rejeitadas, não aplicadas) e uma linha "Decisão não aplicada" por aviso. O teste do comando que lista exatamente as abas passou a incluir a nova aba.
- **Por quê:** a spec põe a lista do lote confirmado no mesmo workbook, e não é arquivo de importação (ADR 0002); a Analista precisa separar principal e Encargo ao baixar.
- **Alternativas:** arquivo separado; acumular todas as confirmações ainda não baixadas (é o Aguardando baixa no ERP do ticket 14).

## Ticket 13: como a Analista resolve a Fila no workbook

- **Decisão:** a aba Fila de exceções ganha, no fim, as colunas Decisão, Títulos escolhidos, Franqueado do Conciliado fora (CNPJ) e Referência do Conciliado fora, todas vazias (a Fila não vem pré-preenchida). Para Crédito: "confirmar", "antecipação", "devolução", "erro" ou "conciliado fora"; para item de Título (Possível duplicidade): "mesma dívida" ou "dívidas distintas". A comparação ignora maiúsculas e acentos. Títulos escolhidos são escritos como na coluna Títulos sugeridos ("NF 1 (Protheus); NF 2 (Protheus)") ou só pelo documento, quando ele identifica um único Título; "confirmar" sem Títulos escolhidos confirma os Títulos sugeridos. Linha com Decisão vazia é ignorada. Valem as mesmas regras do ticket 12 (autor, execução do workbook, aviso no Resumo para o que não for aplicado), e o Resumo ganha as linhas "Fila resolvida pelo Excel", "Conciliado fora (na causa raiz)" e "Títulos a cancelar na origem". Confirmações da Fila entram na contagem de confirmadas.
- **Por quê:** colunas no fim não mexem nas existentes; a Fila exige decisão ativa da Analista, ao contrário da Lista; confirmar o que foi sugerido é a mesma coisa que confirmar uma proposta da Lista.
- **Alternativas:** aba própria de decisões da Fila; exigir sempre os Títulos escolhidos (uma digitação a mais para o caso comum).

## Ticket 13: confirmação pela Fila segue o caminho da Lista

- **Decisão:** a confirmação de um item da Fila grava uma decisão "confirmar" com os Títulos escolhidos, com o mesmo Encargo, a mesma saída na Baixa manual no ERP e o mesmo efeito do ticket 12: o Crédito deixa de ser vivo e os Títulos saem dos Títulos em aberto, inclusive em Diferença a menor. O Título precisa estar em aberto na execução do workbook (nem confirmado, nem cancelado na origem). Um Título usado por mais de uma decisão do mesmo workbook (confirmações da Lista, da Fila, ou Título que uma "mesma dívida" manda cancelar) faz com que nenhuma dessas decisões seja aplicada, com aviso.
- **Por quê:** o ticket pede o mesmo caminho da Lista; Saldo parcial calculado pelas decisões é do ticket 14. Aplicar uma das decisões em disputa seria a plataforma escolher pela Analista.
- **Alternativas:** manter o Título em aberto quando o Crédito é menor (antecipa o ticket 14); aplicar a primeira decisão do workbook.

## Ticket 13: o que é confirmação por nome e qual é a chave do Pagador conhecido

- **Decisão:** a chave do Pagador conhecido é o nome do pagador extraído do histórico pelo adaptador, normalizado como no Nome por prefixo, e não o histórico inteiro (PIX e TED do mesmo nome são o mesmo pagador). Toda confirmação (Lista ou Fila) de Crédito com nome grava um vínculo nome + Franqueado de cada Título confirmado, com a decisão de origem. O vínculo é "por nome" quando os Títulos são de um só Franqueado e o nome aponta para ele: é Nome por prefixo de um nome dele, a IA disse sim para ele ou o item já veio por Pagador conhecido dele. Um nome é Pagador conhecido quando tem algum vínculo por nome; ele vale enquanto todos os vínculos do nome apontam para o mesmo Franqueado. Confirmação de item só por valor ou por soma grava vínculo que não é por nome, então não cria regra. CPF e CNPJ de raiz desconhecida no histórico não viram Pagador conhecido neste ticket.
- **Por quê:** o CONTEXT define Pagador conhecido como nome de extrato vinculado a um Franqueado e a spec fala em "nome igual a Pagador conhecido confirmado"; guardar os vínculos com a decisão permite ao ticket 14 desfazer o aprendizado na reversão. Gravar também os vínculos que não são por nome faz uma confirmação por valor para outro Franqueado desativar o nome, que é o lado conservador. Aprender documento a partir de confirmação de item só por valor contrariaria "confirmações por valor não criam regra".
- **Alternativas:** chave pelo histórico completo (PIX e TED do mesmo pagador seriam pagadores diferentes); aprender de qualquer confirmação com nome; aprender CPF do histórico (história 13 da spec, que fica sem cobertura).
- **Exemplo que sai da regra:** o ticket diz "mesmo histórico"; pela regra, "PIX RECEBIDO X" confirmado faz "TED RECEBIDA X" ir para a Lista também.

## Ticket 13: Pagador conhecido no motor

- **Decisão:** o Pagador conhecido é avaliado depois do nosso número e do CNPJ e antes do Nome por prefixo e da IA, com evidência "Pagador conhecido". Com Valor único (Título sozinho considerando o Encargo, ou uma única soma exata) entre os Títulos em aberto do Franqueado, vai para a Lista com a regra "nome de Pagador conhecido + Valor único" ou "+ soma exata"; senão segue os mesmos Motivos da identificação por CNPJ (Crédito sem título em aberto, mais de uma combinação possível, valor não fecha). Pares rejeitados e Título disputado na Lista continuam valendo. A IA não é chamada para nome que já é Pagador conhecido.
- **Por quê:** é a regra da spec ("nome igual a Pagador conhecido confirmado + Valor único" e 1:N com Pagador conhecido); reutilizar o caminho do CNPJ mantém as duas identificações coerentes.
- **Alternativas:** avaliar o Pagador conhecido antes do CNPJ (o documento é evidência mais forte que o nome).

## Ticket 13: nome confirmado para mais de um Franqueado

- **Decisão:** o nome com vínculos para mais de um Franqueado deixa de ser Pagador conhecido (a situação é derivada dos vínculos, não guardada). O Crédito com esse nome segue o caminho do Nome por prefixo ou da IA e nunca vai para a Lista; quando o Motivo seria "pagador provável, primeira vez", passa a ser "nome ambíguo", sem Franqueado na causa raiz e mantendo a sugestão; os outros Motivos seguem a precedência. A explicação cita as raízes para as quais o nome foi confirmado.
- **Por quê:** "pagador provável, primeira vez" mede o que o aprendizado vai resolver (história 40), e esse nome não será aprendido; a ambiguidade é do nome. Derivar dos vínculos faz a reversão do ticket 14 reativar o nome sem regra extra.
- **Alternativas:** marcar o nome como desativado para sempre numa tabela própria; manter "pagador provável, primeira vez".

## Ticket 13: classificação do Crédito sem título em aberto

- **Decisão:** "antecipação", "devolução" e "erro" só são aceitos para item com Motivo "Crédito sem título em aberto". Devolução e erro encerram o Crédito (deixa de ser vivo, como a confirmação). Antecipação registra a decisão e mantém o Crédito vivo e na Fila, retentado a cada importação, com a classificação na explicação; quando o Título aparece, ele casa normalmente.
- **Por quê:** o CONTEXT diz que o Crédito sem título em aberto continua vivo para casar quando o Título aparecer, que é o caso da antecipação; tirá-lo da Fila sem destino quebraria a conferência de soma. Classificar outro Motivo seria decidir algo que o ticket não pede.
- **Alternativas:** tirar a antecipação da Fila até o Título aparecer (exigiria um destino novo fora da conferência de soma); aceitar devolução e erro para qualquer Crédito.

## Ticket 13: Conciliado fora

- **Decisão:** "conciliado fora" vale para qualquer Crédito da Fila e exige o CNPJ (14 dígitos) ou a raiz (8 dígitos) do Franqueado, com ou sem pontuação, e uma referência livre; o Franqueado não precisa ter Título na plataforma. O Crédito deixa de ser vivo e sai da Fila, e passa a contar no relatório de causa raiz de todas as execuções seguintes, com o Motivo, banco e canal do item decidido e o Franqueado informado pela Analista. A conferência de soma não muda, porque o Crédito não é mais vivo.
- **Por quê:** o Franqueado da terceira unidade pode não ter Títulos integrados; o relatório mede por que os Créditos não foram identificados, e o Franqueado dito pela Analista é o que importa para as ondas de migração. O relatório ainda não tem período, então o Crédito conta enquanto o relatório existir.
- **Alternativas:** contar só na execução que aplicou a decisão (a contagem sumiria no dia seguinte); exigir Franqueado já conhecido; manter o Franqueado atribuído pelo motor.

## Ticket 13: Possível duplicidade decidida

- **Decisão:** "mesma dívida" exige escolher um só Título do grupo como oficial; os outros saem para sempre dos Títulos em aberto (motor e Lista de cobrança) e aparecem na nova aba "Cancelar na origem", logo depois de Baixa manual no ERP, enquanto ainda vierem na exportação. "Dívidas distintas" tira o item da Fila e devolve os Títulos à cobrança. Um grupo decidido não volta a virar item; se a composição do grupo mudar, é outro item. As decisões ficam numa tabela própria, com autor, momento e origem. O teste do comando que lista exatamente as abas passou a incluir a nova aba.
- **Por quê:** o ticket pede a lista para cancelamento na origem; tirar o Título duplicado também do motor evita que um Crédito seja proposto para a cópia que vai ser cancelada. Depois de cancelado no Sistema de origem, o Título some da exportação e não há mais o que cancelar.
- **Alternativas:** tirar o Título só da cobrança (o Crédito continuaria em "mais de uma combinação possível"); listar para sempre os Títulos cancelados.

## Ticket 13: decisão registra o parecer da IA

- **Decisão:** toda decisão sobre Crédito copia os pareceres do item (Franqueado, resposta, explicação, modelo e versão do prompt), em tabela própria. Substitui a observação do ticket 12 de que pareceres não eram copiados.
- **Por quê:** a spec pede modelo e versão do prompt na decisão quando há parecer, e agora a Fila, que tem parecer, também é decidida.
- **Alternativas:** guardar só modelo e versão do prompt (perderia a resposta que a Analista viu).

## Ticket 14: fotografia anterior por Sistema de origem

- **Decisão:** cada execução guarda quais Sistemas de origem tiveram exportação lida (inclusive exportação só com cabeçalho). Um Título "sumiu" quando estava na fotografia anterior do seu Sistema (a última execução que leu exportação dele) e não está na exportação atual. Sistema sem exportação na execução não é comparado.
- **Por quê:** comparar com a execução anterior como um todo faria todos os Títulos do Omie "sumirem" num dia em que só veio o Protheus, gerando Baixados por fora falsos.
- **Alternativas:** comparar com a execução imediatamente anterior; exigir sempre todas as exportações (recusaria execuções parciais).

## Ticket 14: Título proposto e ainda não confirmado que some

- **Decisão:** Título que some sem confirmação em vigor, mas que estava proposto ou sugerido em algum item da última execução, sai de tudo sem virar Baixado por fora; o Crédito continua vivo e é reclassificado. Título cancelado na origem por "mesma dívida" que some também não é Baixado por fora.
- **Por quê:** o ADR 0004 diz que Título proposto que some foi baixado pela Analista; o ticket só chama de Baixado por fora o não proposto. O Crédito não é encerrado porque não há decisão da Analista sobre ele.
- **Alternativas:** tratar como Baixado por fora (contradiz o ADR); encerrar o Crédito junto (a plataforma decidiria sozinha).

## Ticket 14: Divergência de baixa

- **Decisão:** há Divergência de baixa quando some, sem confirmação em vigor, um Título do mesmo Franqueado e do mesmo Sistema de origem de uma confirmação ainda Aguardando baixa no ERP. A confirmação deixa de valer (o Crédito volta a ser vivo e o Título confirmado volta a ter Saldo), mas o Pagador conhecido aprendido nela continua. Enquanto o Crédito estiver vivo, ele vai sempre para a Fila: se o motor o mandaria para a Lista, vai como "mais de uma combinação possível", com a explicação da divergência. O Título sumido aparece como "Divergência de baixa" no Acompanhamento do ERP da execução que a detectou e não como Baixado por fora. Havendo mais de uma confirmação aguardando nesse Franqueado e Sistema, todas voltam para a Fila.
- **Por quê:** a Analista dá baixa no mesmo Sistema de origem do Título proposto; sem como saber qual confirmação foi trocada, devolver todas é o lado conservador. "Mais de uma combinação possível" é o Motivo da lista fixa que descreve o caso: o Título da plataforma ou o baixado no ERP. Segue o precedente do par rejeitado do ticket 12.
- **Alternativas:** manter a confirmação e só avisar (o ticket manda o caso para a Fila); exigir Franqueado e valor iguais; desfazer também o Pagador conhecido (a divergência é sobre o Título, não sobre quem pagou).

## Ticket 14: Saldo pelas decisões e pagamento parcial

- **Decisão:** toda confirmação guarda, por Título, o principal aplicado: o menor entre o Crédito e o Saldo, num Título só; o Saldo de cada Título, em confirmação de vários. O Saldo de um Título é o valor da exportação atual menos o principal das confirmações em vigor cujo Título não mudou de valor em nenhuma exportação desde a execução do item confirmado; se mudou, a confirmação já está refletida no ERP e não é descontada de novo. Título com Saldo zero sai do motor e da cobrança; com Saldo positivo continua em aberto e o motor e a Lista de cobrança usam o Saldo (o Encargo previsto também é calculado sobre ele). A Baixa manual no ERP mostra o principal aplicado. Confirmação de vários Títulos com Crédito menor que a soma dos Saldos não é aplicada, com aviso. Substitui o efeito do ticket 12 e 13 de tirar o Título confirmado dos Títulos em aberto mesmo em Diferença a menor, e o "Saldo antes das decisões" do ticket 09.
- **Por quê:** o CONTEXT define o Saldo assim e a história 72 pede que o pagamento parcial nunca seja descontado duas vezes. Dividir um Crédito menor entre vários Títulos exigiria a plataforma escolher a imputação.
- **Alternativas:** comparar só a exportação atual com a do item confirmado (ignoraria uma mudança que voltou ao valor antigo); imputar o pagamento parcial pelo vencimento mais antigo; o motor seguir com o valor do ERP (proporia um Título parcialmente pago para um Crédito do valor cheio).

## Ticket 14: reversão pelo Excel

- **Decisão:** nova aba "Reverter confirmação", vazia, com as colunas Item e Motivo da reversão; a Analista escreve o identificador do item confirmado (o mesmo da Baixa manual no ERP e do Acompanhamento do ERP). Só confirmações em vigor podem ser revertidas, e o motivo é obrigatório; o resto vira aviso no Resumo. Valem as regras de autor e execução do workbook do ticket 12. A reversão é gravada como decisão "reverter" com autor, momento, motivo e os Títulos da confirmação, e o Resumo conta as revertidas em "Decisões lidas do Excel".
- **Por quê:** o Título confirmado e já baixado sai de todas as saídas, então a reversão não pode depender de uma linha que mostre o item; o motivo segue o padrão da rejeição, para que toda desfeita fique explicada.
- **Alternativas:** coluna de decisão na aba Acompanhamento do ERP (só cobriria Títulos ainda abertos); listar todas as confirmações já feitas (cresceria sem fim e contradiz "sai de todas as saídas"); reverter outras decisões (o ticket só fala de confirmação).

## Ticket 14: efeito da reversão

- **Decisão:** a reversão faz o Crédito voltar a ser vivo, o Título voltar a ter Saldo e os pares da confirmação revertida passarem a valer como pares rejeitados (motivo "confirmação revertida, ..."), então o Crédito vai para a Fila pelo caminho da rejeição do ticket 12. Os vínculos de Pagador conhecido gravados naquela decisão deixam de contar. Se o Título não está na exportação, aparece como "Estorno necessário no ERP" em toda execução até reaparecer em alguma fotografia depois da reversão; depois disso não volta a ser marcado.
- **Por quê:** reverter é dizer que aquela ligação estava errada; tratá-la como rejeição evita que a mesma regra a reproponha para a Lista. A Analista ainda pode escolher o mesmo Título na Fila.
- **Alternativas:** devolver o Crédito ao motor sem rejeitar o par e forçar a Fila (o Motivo sairia "mais de uma combinação possível" sem haver duas opções).

## Ticket 14: saídas do acompanhamento do ERP

- **Decisão:** aba "Acompanhamento do ERP", logo depois de Cancelar na origem e antes de Reverter confirmação, com Situação, Título, Sistema de origem, Franqueado, CNPJ, Vencimento, Valor, Saldo, Item e Explicação. Aguardando baixa no ERP e Estorno necessário no ERP aparecem em toda execução enquanto valem; Baixado por fora e Divergência de baixa só na execução que os detectou (ficam guardados). O Resumo ganha uma linha com a quantidade de cada situação. A Baixa manual no ERP deixa de listar Título que já não está na exportação do seu Sistema. O teste do comando que lista exatamente as abas passou a incluir as duas abas novas.
- **Por quê:** Título confirmado que some sai de todas as saídas (história 68); um evento já registrado repetido todo dia esconderia os novos.
- **Alternativas:** abas separadas por situação; repetir Baixados por fora em todas as execuções.

## Ticket 16: o que é "resolvido sozinho"

- **Decisão:** a parte resolvida sozinha é a fração dos Créditos classificados na execução (Lista de baixa + Fila de exceções, os vivos de todas as importações) que foi para a Lista de baixa, em quantidade e em valor. Fora do escopo não entra na base. Sem Crédito na execução, o Resumo diz "nenhum Crédito para conciliar nesta execução" em vez de um percentual. É derivada dos itens guardados, sem coluna nova.
- **Por quê:** débitos não são conciliados, e incluí-los inflaria a parte automática; usar o mesmo conjunto dos totais por destino mantém o Resumo coerente consigo mesmo e com a conferência de soma.
- **Alternativas:** só os Créditos novos da execução (rodar de novo os mesmos arquivos daria "sem Crédito" e esconderia a comparação); incluir Fora do escopo na base.

## Ticket 16: alerta de queda da parte automática

- **Decisão:** compara com a execução imediatamente anterior, em pontos percentuais, separadamente em quantidade e em valor; alerta se qualquer uma das duas cai estritamente mais que o limite. O limite fica em `[resumo] limite_de_queda_pontos_percentuais` (número de 0 a 100, campo desconhecido recusado), padrão 10, e é guardado com cada execução (tabela `limites_de_queda`) para que o Resumo seja relido do armazenamento sem depender da configuração atual. Execução anterior sem Crédito não é comparada; execução guardada antes deste ticket fica sem alerta. O Resumo sempre tem a linha "Alerta de queda da parte automática", com o alerta ou com os percentuais da anterior.
- **Por quê:** a spec deixa o limiar configurável e em aberto com o cliente; queda em valor sem queda em quantidade (poucos Créditos grandes) também indica exportação quebrada, então alertar por qualquer uma é o lado conservador. Pontos percentuais são o que a Analista lê no Resumo.
- **Alternativas:** queda relativa (percentual do percentual); média das últimas execuções; só quantidade; sem valor padrão (a seção passaria a ser obrigatória).

## Ticket 16: conflitos no Resumo

- **Decisão:** o Resumo ganha "Conflitos entre Excel e tela" (contagem) e uma linha "Conflito" por conflito, lidas de `DecisoesLidas.conflitos`. Hoje só há a origem Excel, então a contagem é sempre 0; o ticket 15 (tela) preenche os conflitos.
- **Por quê:** o ticket pede o Resumo completo e o ticket 15 depende deste; zero é o valor verdadeiro enquanto não existe a segunda origem.
- **Alternativas:** deixar a linha para o ticket 15; criar já a tabela de conflitos sem nada que escreva nela.

## Ticket 16: relatório de métricas

- **Decisão:** aba "Métricas", logo depois de Causa raiz, com três blocos: taxa de rejeição por tipo de evidência, taxa de rejeição por regra e acerto da primeira sugestão da IA por modelo e versão do prompt. As métricas são acumuladas de todas as decisões aplicadas até a execução, calculadas ao carregar o resultado, e nada no motor as lê. O teste do comando que lista exatamente as abas passou a incluir "Métricas".
- **Por quê:** o resultado guardado é a única origem das saídas e a causa raiz já é um relatório no workbook; o motor não recebe as métricas, então nenhuma regra muda por causa delas (história 77).
- **Alternativas:** comando ou arquivo separado; aba no fim, depois de Arquivos recusados.

## Ticket 16: taxa de rejeição

- **Decisão:** conta só decisões "confirmar" e "rejeitar" sobre propostas da Lista de baixa (as que têm regra). Taxa = rejeitadas / (confirmadas + rejeitadas), por cada tipo de evidência da proposta e por regra. Confirmações revertidas depois aparecem numa coluna à parte e continuam contando como confirmadas.
- **Por quê:** só a Lista é rejeitada; a Fila exige decisão ativa e não tem proposta. A reversão pode ter motivo que não é erro da regra (ticket 14), então misturá-la à taxa a distorceria; mostrá-la à parte deixa a leitura para o desenvolvedor.
- **Alternativas:** contar a reversão como rejeição; incluir confirmações da Fila.

## Ticket 16: acerto da primeira sugestão da IA

- **Decisão:** a primeira sugestão de um Crédito é o conjunto de pareceres do primeiro item dele em que todos os candidatos tiveram parecer (execuções com "IA indisponível" são puladas). A verdade é o Franqueado da decisão em vigor da Analista: os Títulos confirmados (pela raiz do CNPJ) ou o Franqueado do Conciliado fora. A sugestão acerta quando cada resposta bate: sim para o Franqueado decidido e não para os outros candidatos (inclusive "não" para todos quando a Analista escolheu um Franqueado que não era candidato). Crédito com parecer e sem decisão conta como "aguardando decisão"; confirmação com Títulos de mais de um Franqueado não é avaliada. Agrupado por modelo e versão do prompt.
- **Por quê:** "primeira" isola o que a IA disse antes de qualquer correção; o "não" também é sugestão (mantém a sugestão por valor sem nome), então errar para "não" precisa contar como erro.
- **Alternativas:** usar o parecer copiado na decisão (é o último, não o primeiro); avaliar só os pareceres "sim".

## Ticket 15: comando e servidor da tela local

- **Decisão:** comando `conciliar-tela` (módulo `conciliacao.tela`), com `--estado` (padrão `conciliacao.sqlite`, o mesmo do `conciliar`), `--porta` (padrão 8765) e `--sem-navegador`. O servidor é o `HTTPServer` da biblioteca padrão, de uma linha de execução, ouvindo só em 127.0.0.1, e abre o armazenamento a cada requisição para ler a última execução; um arquivo de estado inexistente não é criado, a tela só diz que não há execução. As rotas ficam num mapa caminho -> função que recebe o caminho do estado e devolve a resposta, para que as ações POST do ticket 15 entrem como outro mapa.
- **Por quê:** a spec pede dois comandos sobre o mesmo armazenamento, sem servidor externo e sem dependência nova. Uma linha de execução serializa as gravações futuras no SQLite; ler a cada requisição faz a tela acompanhar uma execução nova sem reiniciar e não guarda resultado em memória. Ouvir só em 127.0.0.1 mantém a tela local, já que não há autenticação (fora do escopo).
- **Alternativas:** subcomando do `conciliar`; `ThreadingHTTPServer`; carregar o resultado uma vez ao subir; framework web.

## Ticket 15: o que a tela mostra

- **Decisão:** o Resumo da tela é a mesma lista de linhas da aba Resumo, gerada por uma função compartilhada (`linhas_do_resumo`), para que os totais nunca divirjam. Seções: Resumo, Lista de baixa, Fila de exceções (com os itens de Título, como na aba), Lista de cobrança, Títulos em análise (com os Créditos candidatos), Causa raiz e Fora do escopo. Lista de baixa e Fila têm as colunas Item, Crédito, Título(s), Evidência, Motivo e Explicação; o parecer da IA vai num bloco destacado dentro da Explicação, com a marcação "IA indisponível" quando for o caso. A causa raiz tem dois gráficos de barras horizontais em SVG desenhados no servidor (quantidade e valor por Motivo, com todos os Motivos, inclusive os zerados, como na aba) e as tabelas por Motivo, Franqueado, banco e canal. Baixa manual, Cancelar na origem, Acompanhamento do ERP, Métricas e Arquivos recusados ficam só no workbook (os recusados aparecem no Resumo).
- **Por quê:** a spec lista exatamente o que a tela mostra; repetir o resto do workbook aumentaria a superfície sem pedido. Compartilhar as linhas do Resumo é a forma mais simples de garantir que tela e workbook mostram os mesmos totais.
- **Alternativas:** todas as abas do workbook na tela; um único gráfico com duas barras por Motivo; esconder Motivos zerados.

## Ticket 15: decisões da tela ficam pendentes até a próxima execução

- **Decisão:** a tela grava cada decisão como uma linha pendente (mesmos campos de uma linha do workbook: aba, item, decisão, motivo, Títulos escolhidos, Franqueado, referência, mais autor e momento) na tabela `decisoes_da_tela` do mesmo armazenamento. Na etapa "aplicar decisões" da execução seguinte, as linhas do Excel e as pendentes da tela passam pela mesma interpretação e pelo mesmo registro (`aplicar_decisoes`), cada uma com sua origem ("Excel" ou "Tela"); as pendentes são marcadas como lidas por aquela execução, aplicadas ou não. A tela mostra a decisão pendente de cada item.
- **Por quê:** a spec põe a aplicação das decisões (Excel e tela) numa etapa da execução, detectando conflitos "desde a última execução"; aplicar na hora do clique tornaria impossível não aplicar nada quando o Excel trouxer o mesmo item depois. Um só interpretador garante o mesmo efeito, as mesmas validações e os mesmos avisos no Resumo.
- **Alternativas:** aplicar a decisão da tela no clique e tratar o Excel como conflito depois (a decisão da tela já teria efeito); validar tudo no clique com a configuração do Encargo (a tela passaria a depender da configuração).

## Ticket 15: quem decide pela tela e o que a tela valida no clique

- **Decisão:** o autor das decisões da tela é o usuário do sistema que abriu a tela, ou o nome dado em `--analista`; o momento é o do clique. No clique a tela só recusa (sem gravar, com a mensagem) o que é certamente inválido: não há execução, item que não está na Lista de baixa ou na Fila da última execução, decisão vazia e rejeição sem motivo. O resto (Título escolhido, Conciliado fora, Saldo) é validado na aplicação, como no Excel, e o que não for aplicado vira aviso no Resumo.
- **Por quê:** a autenticação está fora do escopo e a decisão precisa de autor; o usuário do sistema é o dado mais confiável disponível sem pedir nada a mais por clique. Validar o certo no clique evita surpresa sem duplicar a interpretação.
- **Alternativas:** campo de nome em cada formulário; autor fixo "Tela"; validação completa no clique.

## Ticket 15: confirmar o lote e decidir de novo pela tela

- **Decisão:** "Confirmar o lote" registra "confirmar" para os itens da Lista de baixa que ainda não têm decisão da tela; cada item também pode ser confirmado ou rejeitado (com motivo) sozinho. Uma nova decisão da tela sobre o mesmo item, antes da execução seguinte, substitui a anterior.
- **Por quê:** é o equivalente do workbook, em que o lote vem com "confirmar" e a Analista só muda o que rejeita; e, como no Excel, vale o último estado salvo antes da execução.
- **Alternativas:** o lote sobrescrever as rejeições já feitas; recusar segunda decisão sobre o item.

## Ticket 15: o que conta como conflito

- **Decisão:** conflito é o mesmo identificador de item com linha no workbook aplicável (salvo pela Analista e da última execução) e decisão pendente da tela, mesmo que as decisões coincidam. Toda linha da Lista de baixa de um workbook salvo conta como decisão (o "confirmar" pré-preenchido e a célula vazia também), e na Fila só as linhas com decisão. Nenhuma das duas é aplicada, o conflito vai para `conflitos_das_decisoes` (Resumo e tela, numa seção destacada) e a decisão da tela é dada como lida: o item volta a aparecer para nova decisão, sem conflito repetido. Workbook ignorado (sem autor, de outra execução) não gera conflito. O aviso de Título usado por mais de uma decisão passou a valer entre as duas origens.
- **Por quê:** a spec adota a interpretação literal e diz que a plataforma não escolhe entre as origens; a linha pré-preenchida é uma decisão do workbook salvo, como no ticket 12.
- **Alternativas:** só linhas alteradas pela Analista contarem (o workbook não guarda o que foi alterado); manter a decisão da tela pendente após o conflito.

## Ticket 17: o teste de aceitação lê a pasta da amostra

- **Decisão:** só o código de teste lê `data/`; a tabela esperada da spec fica no próprio teste de aceitação (`tests/test_aceitacao_amostra_julho.py`) e nenhum valor da amostra entra no código de produção. O teste roda a plataforma pela mesma entrada do comando (`executar_conciliacao`) com o `conciliacao.toml` do projeto, para refletir o que `uv run conciliar data/` faz. A confirmação do usuário pedida pela spec continua em aberto.
- **Por quê:** a restrição do usuário é sobre valores no código, não sobre o teste ler os arquivos; é a opção mais conservadora enquanto não há resposta e evita copiar os arquivos da amostra para dentro dos testes.
- **Alternativas:** copiar a amostra para fixtures em `tests/` (duplicaria os dados); recriar a amostra com os construtores de `tests/arquivos.py` (perderia o formato exato dos arquivos reais).

## Ticket 17: IA falsa na suíte padrão e Ollama real na integração

- **Decisão:** a aceitação roda com duas origens de parecer: a IA falsa, que responde "sim" só para os dois pares que a spec dá como parecer positivo (DOCE PONTO COM ALIME e SABOR CIA), na suíte padrão; e o Ollama do `conciliacao.toml`, marcado `integracao`, pulado se o Ollama ou o modelo não estiver disponível. As mesmas asserções valem para as duas. Onde o resultado diverge da spec, o teste mantém a expectativa da spec e fica marcado `xfail(strict=True)` com a causa.
- **Por quê:** a parte determinística (identificação, somas, Encargo, destinos, cobrança) não deve depender do Ollama; a IA falsa só substitui o parecer validado pelo usuário, sem mudar regra nenhuma. O `strict` faz o teste falhar quando a divergência deixar de existir.
- **Alternativas:** ajustar as expectativas ao resultado atual (esconderia as divergências); só o teste com Ollama real (a suíte padrão dependeria do serviço).

## Ticket 17: divergências da amostra mantidas como xfail

- **Decisão:** três divergências ficam registradas como `xfail(strict=True)`, sem mudar regra de produção: o PIX de 30/07 (1.850,00) sai "valor não fecha" em vez de "Crédito sem título em aberto" (ticket 06, Títulos propostos ou sugeridos não são reservados); "em análise" dá 14 em vez de 9 (ticket 09 conta Crédito candidato na Lista ou na Fila); com o Ollama real, DOCE PONTO e SABOR CIA saem "sem identificação do pagador" com evidência só valor (ticket 08, o `qwen2.5:3b` responde "não"). O TED de 14/07 tem a sugestão NF 104533 + NF 104588 nos dois casos: com o "sim" pelo parecer, com o "não" pela sugestão por valor do Franqueado candidato.
- **Por quê:** a regra é aplicada como princípio e não é ajustada aos exemplos; as duas primeiras dependem de decisão do usuário (reservar Títulos já propostos, o que conta como "em análise") e a terceira é limitação do modelo.
- **Alternativas:** reservar Títulos propostos na Lista ou sugeridos na Fila; contar só a Fila em "em análise"; ajustar o prompt aos nomes da amostra.
- **Substituída:** ver Correção: Título candidato e Crédito sem título em aberto, Correção: "em análise" só com Crédito candidato na Fila e Correção: prompt e modelo da IA

## Ticket 17: verificação de identificadores da amostra no código de produção

- **Decisão:** o teste lê os arquivos da amostra e monta os identificadores: nomes dos clientes dos Títulos e nomes do pagador no histórico do Extrato (depois dos prefixos de canal do adaptador), documentos e o número final de cada um, CNPJs (formatados e só dígitos), nossos números, números de 5 ou mais dígitos do Extrato e cada valor em quatro formas (`18.450,00`, `18450,00`, `18450.00`, centavos). Procura cada um, sem diferenciar maiúsculas e como palavra inteira, em todo `src/`. Textos genéricos de banco (como "DEPOSITO NAO IDENTIFICADO" e "TARIFA PIX EMISSAO") não contam como nome. A verificação achou um CNPJ da amostra como exemplo de formato numa mensagem de erro de `normalizacao.py`, trocado por `00.000.000/0000-00`.
- **Por quê:** derivar a lista dos arquivos garante que um dado novo da amostra também é verificado, sem repetir a amostra no teste; a palavra inteira evita falso positivo com números que só contêm um valor.
- **Alternativas:** lista fixa de identificadores no teste; procurar também em `conciliacao.toml` (configuração, não código).
- **Substituída:** ver Correção: vocabulário do gerador e palavras distintivas da amostra

## Correção: Título candidato e Crédito sem título em aberto

- **Decisão:** Título candidato de um Crédito é (1) o Título do nosso número do Crédito; (2) entre os Títulos em aberto do Franqueado identificado, cada opção que fecha com o valor (Título sozinho dentro do Encargo e da tolerância, ou soma exata); (3) sem opção que feche, o único Título em aberto do Franqueado, frente ao qual o Crédito é Diferença a menor ou Valor a maior. Com dois ou mais Títulos em aberto e nenhuma opção que feche, nenhum Título é apontado e não há candidato. Assim, "valor não fecha" sempre tem o Título candidato sugerido e o Crédito de Franqueado identificado sem candidato vai para a Fila como "Crédito sem título em aberto", sem sugestão, e é retentado a cada importação. Vale igual para CNPJ, Pagador conhecido e Nome por prefixo; no Nome por prefixo de vários Franqueados, os candidatos são os Títulos únicos de cada um: um só vira "valor não fecha" com ele sugerido, mais de um vira "valor não fecha" sem sugestão, citando-os (como no ticket 06). `citados` passa a levar só Títulos candidatos; Títulos do Franqueado que não são candidatos ficam só na explicação. O gerador sintético grava no gabarito do pagamento parcial por CNPJ e da antecipação "valor não fecha" quando o Franqueado tem um só Título e "Crédito sem título em aberto" quando tem mais.
- **Por quê:** decisão do usuário ("segue a spec"). O CONTEXT.md (linha 96) define "Crédito sem título em aberto" como Crédito de Franqueado identificado "sem nenhum Título candidato", não "sem Título em aberto"; Diferença a menor e Valor a maior (CONTEXT.md, linhas 83-90; spec, histórias 19 e 21) são medidos frente a um Título. A regra anterior deixava a história 27 (antecipação, spec linha 63) inalcançável sempre que o Franqueado tinha outro Título em aberto e mandava Franqueado com vários Títulos para "valor não fecha" sem Título sugerido, contra a história 42 (spec linha 84). Pela regra, o PIX de 30/07 da amostra (dois Títulos em aberto do Franqueado, nenhuma opção que feche) sai "Crédito sem título em aberto", sem reservar Títulos.
- **Alternativas:** Título candidato por proximidade do valor (exigiria uma faixa que nem a spec nem o CONTEXT definem); reservar Títulos já propostos ou sugeridos a outro Crédito (resolveria a amostra por outro caminho, mas não a história 42); tratar todos os Títulos do Franqueado como candidatos (é a regra anterior).

## Correção: "em análise" só com Crédito candidato na Fila

- **Decisão:** "em análise" mostra só Títulos com Crédito candidato na Fila de exceções, com esses Créditos. Título proposto na Lista de baixa sai da cobrança mas não entra em "em análise", a menos que também tenha Crédito candidato na Fila. Os Títulos candidatos são os sugeridos e os `citados`, que agora só levam Títulos candidatos (ver a correção anterior). Os textos de "em análise" no workbook e na tela dizem "Crédito candidato na Fila de exceções".
- **Por quê:** decisão do usuário ("segue a spec"). A história 46 (spec linha 91) restringe "em análise" a Títulos com Crédito candidato na Fila; a história 43 (spec linha 178, "sem Crédito candidato confirmado ou em análise") tira da cobrança também o Título proposto na Lista. A amostra passa a dar os 9 Títulos em análise da spec.
- **Alternativas:** manter a Lista em "em análise" (regra anterior); devolver à cobrança o Título proposto na Lista (cobraria quem já pagou).

## Correção: IA chamada por Franqueado candidato

- **Decisão:** Franqueado candidato é o Franqueado, agrupado pela raiz do CNPJ, com que o valor do Crédito fecha (Título sozinho considerando o Encargo, soma exata ou limite da busca atingido). Para cada Franqueado candidato, o nome do Extrato é comparado por prefixo com todos os nomes desse Franqueado em todos os Sistemas de origem; a IA é chamada, uma vez por candidato, só para os candidatos de que o nome não é Nome por prefixo. Se nenhum candidato precisa de IA, segue o caminho do Nome por prefixo (ticket 06) ou, sem Nome por prefixo, o de só valor. Quando a IA é chamada, os Franqueados com o nome confirmado são os candidatos por Nome por prefixo mais os candidatos com parecer "sim", e o destino segue o do ticket 08: um só, "pagador provável, primeira vez" com a opção dele (ou "mais de uma combinação possível"); mais de um, "nome ambíguo" sem sugestão; IA indisponível em algum candidato, "sem identificação do pagador" com a sugestão por valor entre todos os candidatos, marcado "IA indisponível". A evidência é nome por prefixo, parecer de LLM ou os dois, conforme de onde veio cada Franqueado confirmado. Com todos os pareceres "não" e o nome sendo Nome por prefixo de algum Franqueado com que o valor não fecha, vale o caminho do Nome por prefixo ("valor não fecha" ou "Crédito sem título em aberto", ver a correção de Título candidato), com os pareceres guardados no item e citados na explicação.
- **Por quê:** decisão do usuário ("compara com todos os nomes do Franqueado candidato, pelo CNPJ"). A história 30 (spec linha 69), a regra de decisão da spec (linha 176) e o Parecerista de nome (linha 164) mandam chamar a IA quando o nome não é prefixo de nenhum nome do Franqueado candidato, já filtrado por valor; a regra anterior deixava de chamar a IA sempre que o nome era prefixo de qualquer Franqueado, mesmo que o valor só fechasse com outro. O caso de pareceres "não" com Nome por prefixo de outro Franqueado não está na spec: o Nome por prefixo é identificação por regra e a precedência da história 39 põe "valor não fecha" e "Crédito sem título em aberto" antes dos outros Motivos, por isso ele prevalece sobre a história 33, que trata do nome que só a IA poderia identificar.
- **Alternativas:** manter a regra anterior (contra a spec); com pareceres "não" e Nome por prefixo de outro Franqueado, mandar para "sem identificação do pagador" com a sugestão por valor (ignoraria a identificação por regra); com IA indisponível, usar o Nome por prefixo do candidato e ignorar o candidato sem parecer (um "sim" não dado ainda tornaria o nome ambíguo).

## Correção: CPF ou CNPJ desconhecido no histórico

- **Decisão:** o histórico passa a ser varrido também por CPF (`000.000.000-00` ou 11 dígitos seguidos, sem fazer parte de um número maior). Sem CNPJ de Franqueado conhecido no histórico, o Crédito cujo histórico traz CPF ou CNPJ de raiz desconhecida vai para a Fila como "sem identificação do pagador", sem procurar Pagador conhecido pelo nome, Nome por prefixo nem parecer da IA; a sugestão é a de só valor (um Título em aberto com que o valor fecha, entre todos) e a explicação cita o documento. CNPJ de Franqueado conhecido no histórico continua identificando, mesmo com CPF ou outro CNPJ desconhecido junto. As histórias 12 e 13 (aprender CPF e CNPJ de filial como Pagador conhecido) ficam fora por ora, por decisão do usuário: até lá, nenhum CPF identifica.
- **Por quê:** decisão do usuário (Crédito cujo histórico traz CPF, ou CNPJ cuja raiz não pertence a nenhum Franqueado conhecido, vai para a Fila com Motivo "sem identificação do pagador"). O documento diz quem pagou e não é Franqueado; procurar o nome no resto do histórico ou perguntar à IA tentaria contrariar o documento. A sugestão por valor segue a história 18 (spec linha 54).
- **Alternativas:** sem sugestão por valor; deixar o documento desconhecido de lado e seguir pelo nome (regra anterior); tratar CPF só quando pontuado (11 dígitos seguidos são como o banco escreve CNPJ sem pontuação, a amostra mostra esse formato).

## Correção: juros zero por padrão

- **Decisão:** o padrão de `juros_ao_mes_percentual` passa a ser 0, no código (`ParametrosDeEncargo`) e no `conciliacao.toml`. Sem juros configurados, o Encargo previsto é só a multa; qualquer valor entre o Título e o Título + multa + tolerância continua fechando como Encargo pago. Os testes que exercitam o cálculo de juros passam juros de 1% explicitamente.
- **Por quê:** decisão do usuário ("juros ao mês fica em zero, como a gente decidiu"). A spec (linhas 162 e 211) só fixa a multa de 2% e deixa os juros do contrato como ponto aberto com o cliente.
- **Alternativas:** manter 1% ao mês (regra anterior); juros sem padrão, obrigatório na configuração.

## Correção: Possível fonte não integrada classificada pela Analista

- **Decisão:** a Analista classifica um Crédito da Fila de exceções como "possível fonte não integrada", pela coluna Decisão da aba Fila de exceções ou pela tela local, com o mesmo interpretador, a mesma comparação sem maiúsculas e acentos, os mesmos avisos e a mesma regra de conflito entre Excel e tela do ticket 15. Vale para Crédito da Fila com qualquer Motivo; não vale para a Lista de baixa nem para item de Título (Possível duplicidade). A classificação não encerra o Crédito: ele continua vivo e é retentado a cada importação, como a antecipação. Em toda execução seguinte em que o motor mandar o Crédito para a Fila, o Motivo passa a ser "Possível fonte não integrada" (o Título sugerido, a evidência, os pareceres e o Franqueado atribuído pelo motor não mudam) e a explicação diz quando a Analista classificou e qual Motivo o motor apontava. Se o motor passar a propor o Crédito na Lista de baixa (o Título apareceu numa exportação), ele vai para a Lista e casa normalmente. Na causa raiz o Crédito conta em "Possível fonte não integrada", com o Franqueado, banco e canal do motor; marcado depois como Conciliado fora, continua contando nesse Motivo (o Conciliado fora usa o Motivo do item decidido, ticket 13) e com o Franqueado informado. O Resumo ganha, na linha "Fila resolvida pelo Excel", a contagem de Créditos classificados como Possível fonte não integrada na execução. As métricas não mudam: a taxa de rejeição só conta a Lista de baixa e o acerto da IA só tem verdade com confirmação ou Conciliado fora, então o Crédito classificado com parecer segue "aguardando decisão". A classificação não é desfeita por uma decisão própria; o Crédito sai dela por "confirmar" ou "conciliado fora", que o encerram, ou pela Lista de baixa. Uma nova classificação do mesmo Crédito só atualiza a data citada. "antecipação", "devolução" e "erro" continuam exigindo o Motivo "Crédito sem título em aberto", e o Motivo do item classificado passa a ser Possível fonte não integrada, por isso não são aceitos depois dela. O motor continua sem atribuir esse Motivo sozinho. Substitui, na decisão do ticket 10 sobre as categorias da causa raiz, só a afirmação de que nenhuma regra atribui esse Motivo; o resto daquela decisão segue valendo. Estende a lista de decisões da Fila do ticket 13 ("como a Analista resolve a Fila no workbook").
- **Por quê:** decisão do usuário ("Possível fonte não integrada é uma classificação da analista, não detecção automática"). A história 38 (spec linha 80) põe Possível fonte não integrada entre os Motivos estáveis, e a spec linha 199 diz que os Créditos da terceira unidade aparecem como Possível fonte não integrada e podem ser marcados Conciliado fora; o CONTEXT.md define o Motivo como Crédito que provavelmente pertence a um Título fora da plataforma, o que pede o Crédito vivo para casar quando o Título vier, como na antecipação. Manter o Crédito na Fila preserva a conferência de soma e não decide nada além do que a Analista disse. Deixar o motor propor na Lista quando o Título aparece segue o "casa normalmente" da antecipação; a Analista ainda confirma ou rejeita. Não criar o desfazer evita um tipo de decisão novo sem pedido; confirmar ou Conciliado fora cobrem a saída prevista pela spec.
- **Alternativas:** encerrar o Crédito na classificação (sairia da conferência de soma sem destino e não casaria quando o Título aparecesse); manter o Crédito na Fila mesmo quando o motor o propõe na Lista (esconderia uma proposta com Título); aceitar a classificação só para "sem identificação do pagador" ou "Crédito sem título em aberto" (a spec não restringe); uma decisão "desfazer classificação" ou deixar devolução e erro valerem sobre o Motivo original do motor (exigiria guardar o Motivo do motor à parte); detectar o Motivo pelo motor (contra a decisão do usuário).

## Correção: termos do glossário nos nomes internos

- **Decisão:** os nomes internos passam a usar a linguagem do CONTEXT.md: `Titulo.cliente` vira `Titulo.nome_do_franqueado` (com a coluna `titulos.nome_do_franqueado` no SQLite), `PrimeiraSugestaoDaIa` vira `PrimeiroParecerDaIa` (ADR 0003: a IA dá parecer), os Títulos que o motor aponta na Fila passam a se chamar `titulos_candidatos` (Título candidato), a classe `Pagamento` do Encargo vira `CreditoEnquadrado` e a proporção `sem_pagamento` do gerador vira `sem_credito`. Banco já existente com a coluna antiga `cliente` tem a coluna renomeada ao abrir o Armazenamento (`ALTER TABLE ... RENAME COLUMN`), sem perder nem recriar dado. Os cabeçalhos dos arquivos do Protheus e do Omie não mudam, e o ajudante dos testes que escreve o arquivo do Protheus mantém o campo `cliente` porque descreve esse layout. Textos que a Analista vê e que os tickets fixam ficam como estão: a coluna "Títulos sugeridos" (ticket 06), o bloco "Acerto da primeira sugestão da IA" (ticket 16), a mensagem que cita essa coluna e "pagamento parcial" (ticket 09). O prompt da IA também não muda, para não trocar a versão do prompt nem o comportamento do modelo.
- **Por quê:** decisão do usuário ("corrige as violações de Standards"): as seções _Avoid_ do CONTEXT.md excluem Cliente (em Franqueado), sugestão (em Proposta de baixa) e Pagamento (em Crédito). Renomear a coluna em vez de recriar a tabela é o caminho que preserva o histórico de quem já roda a plataforma; a spec (Testing Decisions, linha 185) diz que os testes não dependem da forma das tabelas, por isso a renomeação foi conferida à mão e não tem teste próprio.
- **Alternativas:** manter o nome da coluna no SQLite e só renomear o código (deixaria o termo evitado no esquema); recriar o banco (perderia decisões e Créditos vivos); mudar também os textos visíveis (contra as expectativas dos tickets).

## Correção: vocabulário do gerador e palavras distintivas da amostra

- **Decisão:** o gerador deixa de usar partes de nomes e históricos que recompõem a amostra (por exemplo "Padaria", "Rede", "Casa do Pão", "Vila Nova", "Bela Vista", "Cantinho", "Sabor", "Mineiro", "Nobre", "Central", "Norte", "TARIFA PACOTE COBRANCA", "TARIFA PIX EMISSAO", "PAGAMENTO FORNECEDOR NF") e passa a usar vocabulário genérico; a unidade dos Franqueados do Omie no gerador passa a ser "AM". Além da verificação de identificadores inteiros, um segundo teste da aceitação monta as palavras distintivas da amostra (palavras dos nomes dos Títulos, do nome do pagador no histórico depois do prefixo do adaptador e dos históricos que não começam com prefixo de canal do adaptador) e procura cada uma, em maiúsculas ou com inicial maiúscula e sem acento, em todo texto literal de `src/`. Ficam fora: palavras com menos de 4 letras, designações de razão social (LTDA, EIRELI, EPP, CIA, COMERCIO, as mesmas que o prompt da IA trata como genéricas), palavras do CONTEXT.md (linguagem do domínio) e o layout (cabeçalhos dos arquivos, prefixos de canal e de nome do adaptador do Itaú, e históricos inteiros que começam com prefixo de canal sem nome, como "LIQUIDACAO COBRANCA SIMPLES" e "DEPOSITO NAO IDENTIFICADO"). Conferido que o teste falha com o gerador anterior e com um histórico da amostra plantado. Nos testes fora da aceitação, nomes e históricos parecidos com a amostra ("Bela Vista Emporio", "PIX RECEBIDO SABOR CIA", "Cantinho Doce", "Padaria Central", "TARIFA PIX", "PAGAMENTO FORNECEDOR") foram trocados por fictícios de mesma estrutura.
- **Por quê:** decisão do usuário ("corrige as violações de Standards"); a spec (Testing Decisions, linha 187) diz que os valores esperados vivem só na fixture da aceitação. A verificação só de nomes inteiros não pegava o gerador recompondo a amostra por partes. Procurar só em textos literais e só na grafia de nome próprio evita falso positivo com identificadores e com prosa ("não casa com nenhuma conta"), e as exclusões são categorias definidas fora da amostra, não palavras escolhidas para fazer o teste passar.
- **Alternativas:** lista fixa de palavras proibidas no teste (não acompanharia a amostra); procurar as palavras em todo o código sem diferenciar maiúsculas (falso positivo com prosa e nomes de variáveis); manter "Norte" como unidade do Omie por ser a unidade da spec (é também palavra de nome da amostra).

## Correção: regras da Analista e Divergência de baixa dentro do motor

- **Decisão:** o motor (`conciliar`) passa a receber as antecipações e as classificações de Possível fonte não integrada feitas pela Analista e as Divergências de baixa em vigor, e devolve destino, Motivo e explicação já com essas regras, na mesma ordem de antes (antecipação, fonte não integrada só para o que o motor manda à Fila, depois divergência levando a Lista para a Fila como "mais de uma combinação possível"). A execução só busca esses dados no armazenamento e os entrega ao motor. O motor segue puro e determinístico: recebe as datas das classificações como dados e não lê relógio nem banco.
- **Por quê:** decisão do usuário ("dos smells, só a regra do motor no execucao.py"); a spec (módulo 5) diz que é o motor que devolve destino e Motivo. O comportamento não muda e nenhum teste mudou de expectativa.
- **Alternativas:** manter as regras na execução (contra a spec); entregar ao motor o armazenamento (o motor deixaria de ser puro).

## Correção: teste da conferência de soma sem depender do motor

- **Decisão:** `executar_conciliacao` ganha o parâmetro opcional `motor`, que por padrão é `conciliar`. O teste da parada pela conferência de soma passa um motor falso que só classifica os débitos e perde o Crédito, pelo ponto de entrada, em vez de importar `conciliar` e trocar o nome dentro do módulo da execução. O teste continua verificando a parada com a soma do Extrato na mensagem e que nada foi guardado (a execução seguinte, com o motor real, é a primeira e grava os dois lançamentos); conferido que ele falha se a execução deixar de chamar a conferência.
- **Por quê:** decisão do usuário ("corrige as violações de Standards"); a spec (Testing Decisions, linha 185) diz que nenhum teste depende de funções internas do motor. Um motor correto nunca perde lançamento, então só um motor substituído exercita a conferência; o motor já é a unidade que a execução chama, o que torna o parâmetro uma porta natural, e o tipo `Motor` fica em `motor.py`. O tipo aceita qualquer lista de argumentos para não repetir a assinatura do motor num Protocol.
- **Alternativas:** testar `conferir_soma` direto (perderia a verificação de que a execução para sem guardar nada); provocar a falha por um arquivo de entrada (não existe entrada que faça um motor correto perder um lançamento); manter o monkeypatch (contra a spec).

## Correção: prompt e modelo da IA

- **Decisão:** o Parecerista de nome passa a usar o prompt `nome-v2` com o modelo `qwen3:4b` (cerca de 2,5 GB). O `nome-v2` mantém a saída `{explicacao, pertence}` e acrescenta oito exemplos fictícios (few-shot, como pares de mensagens antes da pergunta), quatro positivos e quatro negativos, cobrindo abreviação, corte no limite de caracteres, palavras invertidas, palavra faltando, sufixo societário, "&" escrito como "E", "COM" por "Comercio", acento, nome de pessoa e nomes parecidos de empresas diferentes; nenhum nome ou palavra da amostra. O pedido ao Ollama leva `"think": false`, que desliga o modo de raciocínio do `qwen3` (o Ollama 0.40 aceita o campo também em modelos sem esse modo). O modelo fica só no `conciliacao.toml`. A medição usa um conjunto de avaliação próprio, `tests/avaliacao_parecerista.py`, com 28 pares fictícios (14 positivos e 14 negativos, todos diferentes dos exemplos do prompt), que também roda como script (`uv run python -m tests.avaliacao_parecerista [modelo ...]`) e como teste de integração (`test_ollama_real_no_conjunto_de_avaliacao_com_pares_ficticios`: nenhum indisponível, no máximo 1 falso positivo e pelo menos 26 acertos, o resultado medido do modelo escolhido menos uma folga de 1 acerto). DOCE PONTO e SABOR CIA da amostra passaram a receber "sim", e o `xfail` do parecer com o Ollama real foi removido do teste de aceitação, sem mudar a tabela.
- **Tentativas** (temperatura 0; tempo médio por chamada no M2 de 8 GB, com o modelo já carregado; amostra = resposta para DOCE PONTO / SABOR CIA, vista pelo teste de aceitação de integração e só como verificação final, sem orientar o prompt):

| Prompt | Modelo | Acertos (28) | Falsos positivos | Falsos negativos | Tempo por chamada | Amostra |
|---|---|---|---|---|---|---|
| nome-v1 | qwen2.5:3b | 18 | 2 | 8 | 1,4 s | não / não |
| nome-v2 | qwen2.5:3b | 19 | 8 | 1 | 1,3 s | sim / sim |
| nome-v3 | qwen2.5:3b | 20 | 6 | 2 | 3,1 s | sim / sim |
| nome-v4 | qwen2.5:3b | 21 | 6 | 1 | 3,5 s | sim / sim |
| nome-v1 | llama3.2:3b | 13 | 1 | 11 (+3 indisponíveis) | 15,1 s | não / não |
| nome-v2 | llama3.2:3b | 17 | 9 | 2 | 1,4 s | sim / sim |
| nome-v3 | llama3.2:3b | 22 | 5 | 1 | 4,0 s | sim / sim |
| nome-v4 | llama3.2:3b | 18 | 9 | 1 | 4,0 s | sim / sim |
| nome-v1 | phi4-mini (3,8B) | 15 | 3 | 10 | 1,8 s | não / não |
| nome-v2 | phi4-mini (3,8B) | 18 | 5 | 5 | 1,5 s | sim / não |
| nome-v3 | phi4-mini (3,8B) | 23 | 3 | 2 | 4,6 s | sim / sim |
| nome-v4 | phi4-mini (3,8B) | 26 | 2 | 0 | 5,2 s | sim / sim |
| nome-v1 | qwen3:4b, sem raciocínio | 27 | 1 | 0 | 8,4 s e 9,0 s | sim / sim |
| **nome-v2** | **qwen3:4b, sem raciocínio** | **27** | **1** | **0** | **2,5 s e 2,0 s** | **sim / sim** |
| nome-v3 | qwen3:4b, sem raciocínio | 20 | 8 | 0 | 6,1 s | sim / sim |
| nome-v4 | qwen3:4b, sem raciocínio | 22 | 6 | 0 | 7,2 s | sim / sim |

  - `nome-v1`: o prompt anterior, sem exemplos.
  - `nome-v2`: regra reescrita (cada palavra do extrato corresponde a uma do nome, igual ou começo dela, em qualquer ordem; palavras do nome podem faltar; na dúvida, "não") e os oito exemplos fictícios.
  - `nome-v3`: `nome-v2` com a saída estruturada palavra por palavra (`palavras: [{palavra, correspondente}]` antes da explicação). Os modelos preenchem correspondências erradas ("MAR" para "Sul") e respondem "sim" assim mesmo. A instrução tinha um par de palavras parecidas que repetia palavras do conjunto de avaliação, retirado no `nome-v4`.
  - `nome-v4`: `nome-v3` com a exigência de o correspondente começar exatamente com as letras da palavra do extrato e dois exemplos a mais de corte no limite (um positivo e um negativo).
  - O único falso positivo do escolhido é "OLIVEIRA E SANTOS" para "Oliveira & Cia Materiais Ltda". Não foi criado prompt para corrigi-lo, para não ajustar o prompt ao próprio conjunto de avaliação.
  - `gemma3:4b` e `phi3.5` não foram medidos: o disco da máquina tinha cerca de 2 GB livres, e cada modelo foi baixado, medido e removido em seguida (`llama3.2:3b` e `phi4-mini`), ficando só o `qwen2.5:3b` que já existia e o `qwen3:4b` escolhido.
- **Por quê:** decisão do usuário ("melhora o prompt com exemplos genéricos, sem nada da amostra, e testa outros modelos de 3 a 4B. Registra cada tentativa no arquivo de decisões"). A spec (módulo 6, linha 164) pede modelo de 3 a 4B quantizado que caiba no M2 de 8 GB, e o ADR 0003 deixa a LLM só no parecer, sempre na Fila. O critério foi o conjunto fictício, priorizando poucos falsos positivos, coerente com a postura conservadora (um "sim" errado vira "pagador provável, primeira vez" falso; um "não" errado só muda o Motivo e mantém a sugestão por valor). `qwen3:4b` com `nome-v2` empata com `nome-v1` no menor número de falsos positivos e no maior número de acertos, e é cerca de quatro vezes mais rápido. A saída palavra por palavra piorou todos os modelos menos o `phi4-mini`, que ainda ficou atrás.
- **Alternativas:** manter `qwen2.5:3b` com `nome-v1` (2 falsos positivos e 8 falsos negativos); `phi4-mini` com `nome-v4` (26 acertos, 2 falsos positivos, mais lento); `qwen3:4b` com o modo de raciocínio ligado (não medido: gera o raciocínio antes de cada resposta, bem mais lento, e o modelo já não tem falso negativo no conjunto); conferir em código as correspondências palavra por palavra do `nome-v3` e transformar em "não" as incoerentes (o código passaria a decidir sobre o nome, além do pedido); exemplos com nomes da amostra (proibido e seria ajustar a regra ao exemplo).

## Fase 2, ticket 01: formato e sequência do txid

- **Decisão:** o txid é `CI` seguido de um sequencial de 30 dígitos com zeros à esquerda (32 caracteres, dentro do `[a-zA-Z0-9]{26,35}` da `cobv`). O sequencial é a quantidade de txids já gerados no armazenamento mais um; vínculos nunca são apagados e a tabela tem unicidade por tipo e identificador e por tipo e Título, então um txid nunca é reaproveitado e um Título nunca ganha dois.
- **Por quê:** determinístico (a mesma emissão gera os mesmos txids, o que o simulador do ticket 05 precisa para "mesma semente, mesmos arquivos") e a garantia de não reaproveitar fica no próprio armazenamento. O prefixo separa o txid do nosso número na leitura.
- **Alternativas:** txid aleatório (não reproduzível); derivar do Título (reemissão futura repetiria o identificador).

## Fase 2, ticket 01: Cobrança identificada só depois do envio

- **Decisão:** a emissão grava o vínculo numa transação própria antes de chamar a porta e marca o envio depois que a porta aceita, uma cobrança por vez. Um Título tem Cobrança identificada quando o vínculo foi enviado; se a porta falhar, a próxima emissão reenvia o mesmo txid, sem gerar outro.
- **Por quê:** a spec manda gravar o vínculo antes da porta (um pagamento nunca chega sem vínculo) e não duplicar ao emitir de novo. Sem marcar o envio, uma falha da porta deixaria o Título com vínculo e sem cobrança, e nenhuma emissão seguinte o enviaria.
- **Alternativas:** gravar o vínculo e chamar a porta na mesma transação (a falha da porta apagaria o vínculo de uma cobrança que pode ter saído); considerar o vínculo como Cobrança identificada mesmo sem envio (perderia a cobrança em silêncio).

## Fase 2, ticket 01: Títulos em aberto e valor emitido

- **Decisão:** a emissão lê a última exportação de cada Sistema de origem, tira os Títulos cancelados na origem por decisão de mesma dívida e usa o Saldo (valor menos baixas confirmadas ainda não absorvidas pelo ERP, como na execução); Título com Saldo zero não é emitido e o valor emitido é o Saldo. A Data de referência é calculada como na execução, pelas últimas datas dos Extratos das contas configuradas; sem ela (conta configurada sem Extrato) nada é emitido. O vencimento enviado é o do Título; o Vencimento efetivo só decide se ele está vencido.
- **Por quê:** "Título em aberto" já tem esse significado na fase 1 (Saldo maior que zero) e o motor compara o Crédito com o Saldo, então a cobrança pede o que o motor espera receber. Sem Data de referência não há como saber o que está vencido, e a spec deixa vencidos fora da emissão.
- **Alternativas:** emitir pelo valor do Título no ERP (cobraria de novo a parte já confirmada); usar a data do computador (contra a definição de Data de referência).

## Fase 2, ticket 01: o que a porta recebe e multa e juros

- **Decisão:** a porta recebe, por cobrança, só o Título (Sistema de origem e documento), o valor, o vencimento, o CNPJ do Franqueado e o txid. Multa e juros da `cobv` (história 11) não vão na chamada: são parâmetros da plataforma, e o adaptador da porta recebe o Encargo da configuração quando for construído (o simulado ainda não usa; entra no ticket 05).
- **Por quê:** o ticket diz que a porta recebe só esses dados, e a história 11 diz que multa e juros vêm do Encargo da fase 1; passar o Encargo ao adaptador atende as duas sem repetir o mesmo parâmetro em cada cobrança.
- **Alternativas:** multa e juros em cada cobrança (contra o "só" do ticket).

## Fase 2, ticket 01: arquivo de Pix recebidos

- **Decisão:** com `[migracao]` na configuração, um arquivo é de Pix recebidos quando é JSON com exatamente as chaves `parametros` e `pix`, como a resposta de `GET /pix` da API Pix. Cada Pix aceita só os campos da spec (`endToEndId`, `txid`, `valor`, `componentesValor`, `chave`, `horario`, `infoPagador`, `devolucoes`, `pagador`) e exige `endToEndId`, `valor` (`1234.56`) e `horario` (RFC 3339 com fuso); campo desconhecido ou faltando recusa o arquivo inteiro com o motivo. Pix sem txid não é Retorno de cobrança e é ignorado. A data do crédito é o horário convertido para o fuso de Brasília (`America/Sao_Paulo`), porque a API devolve UTC e o Extrato traz a data local. Banco e conta vêm de uma `[[contas]]` cujo padrão casa com o nome do arquivo, como nos Extratos; a configuração precisa de uma entrada para o arquivo de Pix. Sem `[migracao]`, o adaptador fica desligado e o arquivo é recusado como layout desconhecido, como na fase 1.
- **Por quê:** ADR 0005 (layout exato, identificação pelo conteúdo, recusa por arquivo) e a spec (banco e conta pela mesma configuração por nome de arquivo; sem configuração de migração nada da fase 2 executa). Um Pix das 22h em Brasília vem como dia seguinte em UTC e não casaria com o Crédito.
- **Alternativas:** aceitar campos a mais (inferir layout); usar a data UTC; um padrão de nome fixo para o arquivo.

## Fase 2, ticket 01: enriquecimento guardado

- **Decisão:** os Retornos lidos são guardados (únicos por tipo e `endToEndId`) e cada execução tenta ligar os que ainda não têm Crédito aos Créditos vivos ainda não enriquecidos, pelo par conta, data e valor; só liga quando o par tem um Retorno e um Crédito. A ligação fica guardada, então o Crédito continua identificado nas execuções seguintes sem o arquivo na pasta, e reimportar o mesmo arquivo não duplica. Retorno nunca vira lançamento: não entra na conferência de soma nem na Data de referência.
- **Por quê:** os Créditos são reclassificados a cada execução; sem guardar a ligação, o Crédito voltaria ao caminho da fase 1 na execução seguinte. Guardar os Retornos e retentar os sem par adianta parte do ticket 04, que continua com o Resumo dos Retornos pendentes e o desempate pelo pagador.
- **Alternativas:** enriquecer só com o arquivo da execução (resultado mudaria de uma execução para outra).

## Fase 2, ticket 01: Identificador de cobrança no motor

- **Decisão:** o Crédito enriquecido cujo txid tem vínculo com um Título em aberto segue a mesma regra de valor do nosso número da fase 1 (as duas usam agora o mesmo código): exato ou dentro do Encargo vai para a Lista de baixa com a regra "Identificador de cobrança + valor exato ou dentro do Encargo"; fora disso vai para a Fila com "valor não fecha" apontando o Título. A evidência é "Identificador de cobrança" e a explicação começa por "txid ... (Identificador de cobrança de origem plataforma) é do Título ...". O identificador é olhado antes de qualquer outra evidência. Identificador sem vínculo ou de Título que não está em aberto ainda segue o caminho da fase 1; os casos da spec para eles ("Possível fonte não integrada" e "Crédito sem título em aberto") ficam para o ticket 02.
- **Por quê:** a spec põe o identificador no mesmo nível do nosso número e com a mesma regra de valor; aplicar só o "valor exato" do ticket seria recortar a regra para caber no exemplo. Os dois casos de borda têm ticket próprio e um deles toca uma decisão da fase 1 (ver comentário no ticket).
- **Alternativas:** só o valor exato neste ticket; já tratar os casos de borda aqui.

## Correção: emissão de Pix exclui Títulos em Possível duplicidade não decidida

- **Decisão:** a emissão deixa de fora os Títulos de toda Possível duplicidade entre sistemas ainda sem decisão da Analista, pelo mesmo critério da Lista de cobrança: as Possíveis duplicidades calculadas sobre a última exportação sem os Títulos cancelados na origem, menos as já decididas (`possiveis_duplicidades_nao_decididas`, agora usada pela execução e pela emissão). Decidida a duplicidade, os Títulos voltam a ser emitidos na próxima emissão: com "dívidas distintas", os dois; com "mesma dívida", só o oficial, porque o outro passa a ser cancelado na origem.
- **Por quê:** decisão do usuário. Emitir os dois Títulos de uma possível mesma dívida pode cobrar duas vezes o Franqueado; a Lista de cobrança da fase 1 já os deixa de fora pelo mesmo motivo (ver comentário no ticket 01 da fase 2).
- **Alternativas:** emitir os dois, como a regra de emissão da spec dizia (cobrança em dobro); emitir só um deles (seria decidir pela Analista qual é o oficial).

## Correção: Lista de cobrança exclui duplicidade por Sistema de origem e documento

- **Decisão:** a Lista de cobrança deixa de fora os Títulos de Possível duplicidade não decidida comparando por Sistema de origem e documento, com o mesmo critério da emissão (`chaves_em_duplicidade`, usada pelas duas). Antes comparava o Título inteiro; como a Lista recebe os Títulos com o Saldo e as duplicidades são calculadas sobre a exportação, um Título em duplicidade com pagamento parcial confirmado voltava à cobrança.
- **Por quê:** decisão do usuário. A regra do ticket 09 ("Títulos de uma Possível duplicidade não aparecem na Lista de cobrança") não depende do Saldo; o Título é identificado por Sistema de origem e documento em todo o resto da plataforma.
- **Alternativas:** calcular as duplicidades sobre os Títulos com Saldo (um pagamento parcial desfaria a duplicidade, que é sobre o valor do ERP).

## Fase 2, ticket 02: identificador desconhecido segue a fase 1

- **Decisão:** Crédito enriquecido com um Identificador de cobrança sem vínculo na plataforma segue exatamente o caminho da fase 1 (mesmo destino, Motivo, Títulos e evidência). A explicação ganha só uma frase final dizendo que o txid do Retorno não tem vínculo na plataforma. O motor não atribui "Possível fonte não integrada": esse Motivo continua sendo só classificação da Analista (correção "Possível fonte não integrada classificada pela Analista"), que pode usá-lo para esse Crédito pela Fila. O mesmo vale para o identificador que aponta Título fora dos em aberto: ele recebe "Crédito sem título em aberto" (seção seguinte), nunca "Possível fonte não integrada".
- **Por quê:** decisão do usuário, contra a história 28 e o módulo 8 da spec, que mandavam o identificador desconhecido para a Fila com "Possível fonte não integrada". A frase na explicação não muda nenhuma regra e dá à Analista o sinal de cobrança emitida fora da plataforma.
- **Alternativas:** "Possível fonte não integrada" pelo motor, como a spec dizia (contra a decisão do usuário); seguir a fase 1 sem citar o identificador (a Analista perderia a pista).

## Fase 2, ticket 02: identificador de Título fora dos em aberto

- **Decisão:** quando o vínculo do identificador aponta um Título que não está entre os em aberto da execução (sumiu da exportação, tem Saldo zero ou foi cancelado na origem por mesma dívida), o Crédito vai para a Fila com "Crédito sem título em aberto", sem Título candidato, com evidência "Identificador de cobrança", o Franqueado do vínculo e a explicação citando o identificador e o Título. Nenhum outro Título do Franqueado é procurado, nem sozinho nem em soma. Como todo Crédito sem título em aberto, ele continua vivo e é retentado a cada importação.
- **Por quê:** spec, história 27 e módulo 8 ("um identificador aponta um único Título; o motor não procura soma para Crédito identificado"). Pela definição do CONTEXT.md, o Crédito é de Franqueado identificado e não tem Título candidato, porque o único que o identificador admite não está em aberto.
- **Alternativas:** cair no caminho da fase 1 pelo pagador (poderia propor outro Título para um pagamento em duplicidade); apontar o Título baixado como candidato (ele não está em aberto e iria para "em análise").

## Fase 2, ticket 02: proposta do identificador rejeitada

- **Decisão:** se a Analista rejeita a proposta de um Crédito identificado para o Título do vínculo, o Crédito passa a seguir o caminho da fase 1 sem esse Título, como acontece com o nosso número do Protheus, e cai na Fila pela regra da rejeição da fase 1. Não vira "Crédito sem título em aberto" por causa do identificador.
- **Por quê:** a rejeição tira o par Crédito-Título do motor na fase 1; o Título continua em aberto, então tratar o identificador como "Título fora dos em aberto" diria algo falso. Seguir a fase 1 é o mesmo tratamento do nosso número.
- **Alternativas:** manter o identificador e mandar para a Fila apontando o Título rejeitado (ignoraria a rejeição); "Crédito sem título em aberto" (o Título está em aberto).

## Fase 2, ticket 02: componentes do valor do Pix

- **Decisão:** o adaptador de Pix recebidos passa a ler `componentesValor`: objeto com só os componentes da API Pix (`original`, `saque`, `troco`, `juros`, `multa`, `abatimento`, `desconto`), `original` obrigatório e cada componente com `valor` no formato `1234.56`; fora disso o arquivo é recusado com o motivo. O Retorno guarda principal (`original`), multa e juros (zero quando o componente não vem), em colunas novas da tabela de Retornos. Quando o Crédito identificado tem esses componentes, a explicação termina com "O Retorno de cobrança separa principal ..., multa ... e juros ...". A regra de valor não usa os componentes: o valor do Crédito continua passando pelo Encargo da fase 1, e sem componentes a explicação fica com o principal e o Encargo calculados.
- **Por quê:** história 26 e o critério do ticket (componentes "quando o Retorno separa"); a spec diz que o identificador não muda a regra de valor. Os componentes ficam no Retorno porque são dado dele, não da ligação com o Crédito.
- **Alternativas:** guardar os componentes na tabela de enriquecimentos, como sugere o módulo 11 (o Retorno sem Crédito perderia os componentes até ser ligado); usar os componentes para decidir o Encargo (contra a spec).
- **Ponto em aberto:** as colunas novas entram no `CREATE TABLE` da tabela de Retornos criada no ticket 01, sem migração. Um `conciliacao.sqlite` criado com o código do ticket 01 e com `[migracao]` ligada precisa ser recriado; a tabela ainda não saiu desta branch.

## Fase 2, ticket 02: Pagador conhecido e identificador

- **Decisão:** nada muda no código: a confirmação de um Crédito com evidência só de Identificador de cobrança registra o nome do Extrato como as confirmações por CNPJ da fase 1, sem "por nome", e por isso nunca cria Pagador conhecido.
- **Por quê:** história 30 e fase 1, história 57; o teste fixa o comportamento.
- **Alternativas:** não registrar nada para o identificador (deixaria de marcar o nome como confirmado para mais de um Franqueado quando ele também paga outro).

## Fase 2, ticket 03: faixa de nosso número

- **Decisão:** a faixa fica em `[migracao.boleto]`, com `banco`, `conta`, `nosso_numero_inicial` e `nosso_numero_final`: só dígitos, até 20 (o tamanho do nosso número no Segmento T), o mesmo número de dígitos nos dois extremos e inicial menor ou igual ao final; banco e conta precisam estar numa `[[contas]]`. O nosso número gerado é o menor número da faixa, com os zeros à esquerda do tamanho dela, que ainda não está em nenhum vínculo; como vínculos nunca são apagados, nada é reaproveitado, mesmo que a faixa mude. Faixa esgotada desfaz a emissão inteira (nenhum vínculo novo, nada enviado) e o comando avisa. Sem `[migracao.boleto]`, os Títulos sem nosso número recebem só o Pix, e o comando avisa; configurada a faixa depois, a emissão seguinte manda só o boleto que falta.
- **Por quê:** spec, módulos 1 e 2 (faixa do beneficiário por conta, únicos e nunca reaproveitados). Uma conta só porque a spec não diz como escolher a conta beneficiária de cada Título. O tamanho fixo pela faixa é o que faz o nosso número do Extrato bater com o do vínculo.
- **Alternativas:** sequencial pela quantidade gerada, como o txid (repetiria números se a faixa mudar para uma que se sobrepõe à anterior); faixa obrigatória com `[migracao]` (quebraria a emissão só de Pix do ticket 01).
- **Ponto em aberto:** mais de uma conta beneficiária com faixas próprias. Também é premissa que a faixa é reservada pelo banco à plataforma: se um nosso número dela aparecer também num Título do Protheus, o Extrato com esse documento é resolvido pelo vínculo da plataforma.

## Fase 2, ticket 03: boleto e Pix na emissão

- **Decisão:** cada Título em aberto elegível tem um vínculo de txid e, se a exportação não traz nosso número, um vínculo de nosso número (únicos por tipo e Título). A porta recebe uma cobrança por Título com os identificadores ainda não enviados (`txid` e `nosso_numero`, cada um podendo faltar), e os dois são marcados como enviados juntos. Título que ganhou nosso número no Protheus antes de o boleto da plataforma ser enviado não recebe esse boleto. Título com boleto da plataforma já enviado que depois aparece com nosso número no Protheus fica com os dois; a plataforma não cancela cobrança (fora do escopo da spec).
- **Por quê:** ADR 0008 e spec, módulo 3 e história 3 (nenhum Título com dois boletos registrados) e módulo 4 (emitir Título, valor, vencimento, CNPJ e os identificadores). Mandar só o que falta evita reemitir o Pix quando o boleto chega depois. Identificadores de um mesmo Título com valor ou vencimento emitidos diferentes (reenvio depois de falha da porta) vão em cobranças separadas, cada uma com o valor do seu vínculo.
- **Alternativas:** uma chamada da porta por identificador (o boleto com QR Pix, comum nos bancos, é uma emissão só).

## Fase 2, ticket 03: adaptador de retorno CNAB 240

- **Decisão:** com `[migracao]`, um arquivo é retorno CNAB 240 quando a primeira linha tem 240 caracteres com lote `0000` e registro `0`. A partir daí tudo é conferido e qualquer desvio recusa o arquivo inteiro com o motivo: toda linha com 240 caracteres, cabeçalho de arquivo de retorno (posição 143 igual a 2), código do banco conhecido (341, Itaú) e igual ao da `[[contas]]` que casa com o nome do arquivo e o mesmo em todas as linhas, lotes de cobrança de retorno (operação T, serviço 01) com detalhes Segmento T seguido do Segmento U do mesmo lote e mesmo código de movimento, trailer de lote, trailer de arquivo com a quantidade de registros. Só os movimentos 06 (liquidação) e 17 (liquidação após baixa ou de título não registrado) viram Retorno; os demais são ignorados. O Retorno tem o nosso número do Segmento T (sem os brancos), a data de efetivação do crédito e o valor líquido creditado do Segmento U, e chave natural nosso número mais data de ocorrência. A versão do layout no cabeçalho não é conferida, e outro segmento (como o Y de alguns bancos) recusa o arquivo.
- **Por quê:** ADR 0005 e 0007 e spec, módulo 6 e história 15. O Retorno é ligado ao Crédito por conta, data e valor, e o que entra na conta é o valor líquido na data do crédito. A chave natural é a do ticket 04. Variações de banco, inclusive de versão, entram como adaptadores próprios.
- **Alternativas:** valor pago pelo pagador (não casa com o Extrato quando o banco desconta tarifa no crédito); só o movimento 06 (perderia dinheiro de boleto pago depois da baixa).

## Fase 2, ticket 03: multa e juros do Segmento U

- **Decisão:** o Segmento U da FEBRABAN traz multa, juros e encargos num campo só ("acréscimos"), então a explicação mostra "O Retorno de cobrança separa principal ... e acréscimos (juros, multa e encargos) ...", com principal igual ao valor pago menos os acréscimos. A frase só aparece quando os acréscimos são maiores que zero. A regra de valor continua a do Encargo, sem usar os componentes.
- **Por quê:** o critério do ticket pede multa e juros separados, mas o leiaute público não os separa; separar seria inventar a divisão (por exemplo, pela multa configurada). Fica o que o banco informa.
- **Alternativas:** dividir os acréscimos pela multa do Encargo (o valor separado não viria do Retorno); mostrar acréscimos zero em todo boleto pago em dia (ruído).
- **Ponto em aberto:** se algum banco separar multa e juros no retorno dele, isso entra no adaptador desse banco.

## Fase 2, ticket 03: boleto da plataforma no motor

- **Decisão:** o nosso número da plataforma é encontrado pelo vínculo, venha do documento do Extrato ou de um Retorno CNAB, e segue a mesma regra de valor do nosso número do Protheus, com a evidência "Identificador de cobrança", a regra "Identificador de cobrança + valor exato ou dentro do Encargo" e a explicação "nosso número ... (Identificador de cobrança de origem plataforma) é do Título ...", como o txid. O Retorno CNAB de um boleto do Protheus (nosso número de um único Título em aberto, sem vínculo) leva à regra da fase 1 sem nenhuma mudança (evidência "nosso número") e só acrescenta os acréscimos à explicação; isso também identifica o Crédito de boleto do Protheus que chega no Extrato sem o documento. Vínculos de origem Protheus não são gravados: o nosso número do Protheus vem da exportação. Pagamento parcial não precisa de marca de autorização: valor abaixo do Título é Diferença a menor e vai para a Fila com "valor não fecha" apontando o Título, como qualquer identificador.
- **Por quê:** spec, história 31 e módulo 8, e o critério do ticket de manter a regra do Protheus. A evidência separa o que a plataforma emitiu do que veio do Protheus, e a explicação da fase 1 não muda. Copiar o nosso número do Protheus para os vínculos seria uma terceira versão do Título (ADR 0004). O retorno CNAB não diz se o parcial foi autorizado; a regra de valor já leva o parcial para a Fila.
- **Alternativas:** evidência "nosso número" também para o boleto da plataforma (a Analista e a análise de impacto não distinguiriam a origem); gravar vínculo de origem Protheus na emissão, como sugere o módulo 11.

## Fase 2, ticket 03: janela de compensação do boleto da plataforma

- **Decisão:** na Lista de cobrança, Título com boleto da plataforma enviado tem a mesma janela de 2 dias úteis de compensação do Título com nosso número do Protheus.
- **Por quê:** a janela do ticket 09 da fase 1 existe porque o boleto leva dias para cair na conta; vale para qualquer boleto. Sem ela, um Título pago por boleto da plataforma no vencimento iria para a cobrança antes de o dinheiro chegar.
- **Alternativas:** janela só para o nosso número do Protheus (aplicaria a regra pelo exemplo, não pelo motivo).

## Fase 2, ticket 04: desempate pelo pagador

- **Decisão:** os Retornos e os Créditos livres são agrupados pelo par conta, data e valor. Com um Retorno e um Crédito no par, eles são ligados como no ticket 01, sem olhar o pagador. Com mais de um de qualquer lado, um Retorno e um Crédito são compatíveis quando o CNPJ ou CPF do pagador do Retorno aparece no histórico do Crédito ou quando o nome do pagador do Retorno, normalizado como no Nome por prefixo, é começo do nome do pagador que o Extrato traz no histórico, ou o contrário. Só é ligado o par compatível em que o Retorno tem um único Crédito compatível e o Crédito um único Retorno compatível. Depois de ligar, o que sobrou do par é olhado de novo, até nada mais ser ligado: se sobra um Retorno e um Crédito, eles são ligados. Fora disso o Retorno não enriquece e o Crédito segue a fase 1.
- **Por quê:** spec, módulo 7 e histórias 18 e 19, e o critério do ticket. O pagador só desempata; com par único a regra do ticket 01 continua. A exigência dos dois lados cobre o empate entre Créditos e também entre Retornos (dois boletos pagos no mesmo dia e valor). Repetir dentro da execução dá o mesmo resultado que a retentativa da execução seguinte daria (Retornos e Créditos já ligados saem da conta), então o resultado não depende de quantas vezes se roda. O CPF entra pelo mesmo princípio do CNPJ (documento do pagador no histórico), como já acontece na fase 1. O nome é comparado com o nome do pagador do histórico (o que vem depois de "PIX RECEBIDO" ou "TED RECEBIDA"), não com o histórico inteiro, como o Nome por prefixo da fase 1.
- **Alternativas:** desempatar só os Créditos (dois Retornos para um Crédito ligariam o primeiro); exigir o pagador também no par único (Retornos sem pagador, que a API Pix permite, deixariam de enriquecer); CNPJ com precedência sobre o nome (a spec põe os dois no mesmo nível; com os dois apontando Créditos diferentes, o empate persiste).

## Fase 2, ticket 04: pagador nos Retornos

- **Decisão:** o adaptador de Pix recebidos lê `pagador` como a pessoa da API Pix: objeto com só `cpf` (11 dígitos) ou `cnpj` (14 dígitos), no máximo um dos dois, e `nome`, todos opcionais. O adaptador CNAB 240 lê do Segmento T o tipo de inscrição do pagador (posição 133), o número (134 a 148) e o nome (149 a 188): tipo 1 é CPF e tipo 2 é CNPJ, com os dígitos à direita e zeros à esquerda; outro tipo fica sem documento. Pagador fora desse formato recusa o arquivo inteiro com o motivo. O pagador fica guardado no Retorno (colunas novas da tabela de Retornos, sem migração, como no ticket 02).
- **Por quê:** ADR 0005 (layout exato) e o desempate deste ticket. O ticket 03 deixou o pagador do Segmento T para este ticket.
- **Alternativas:** ignorar pagador malformado (aceitaria layout fora do declarado).

## Fase 2, ticket 04: Retornos sem Crédito no Resumo

- **Decisão:** cada execução registra os Retornos que continuam sem Crédito depois do enriquecimento, com quantos Créditos livres e quantos Retornos tinha o par. O Resumo mostra a quantidade e uma linha por Retorno (tipo, identificador, conta, data, valor e o motivo: nenhum Crédito com a mesma conta, data e valor, ou empate que o pagador não desfaz). As linhas só aparecem quando há Retorno sem Crédito, então sem Retornos o Resumo é o da fase 1. A chave natural continua a do ticket 01 e 03 (`endToEndId` no Pix, nosso número e data de ocorrência no boleto), e reimportar não cria outro Retorno nem outra linha.
- **Por quê:** spec, história 20 e módulo 7. O empate também deixa o Retorno sem Crédito e é retentado; mostrar o motivo evita que a Analista espere um Extrato que já chegou. O registro por execução mantém o Resumo de uma execução antiga como ela foi.
- **Alternativas:** mostrar só os Retornos sem nenhum candidato (o empate sumiria da vista); calcular os pendentes na hora de carregar o Resultado (o Resumo antigo mudaria).
- **Ponto em aberto:** Retorno cujo Crédito já saiu dos Créditos vivos (por uma decisão da Analista que encerra o Crédito, tomada antes de o Retorno chegar) nunca é ligado e aparece em todo Resumo. A spec não diz quando um Retorno deixa de ser retentado.

## Fase 2, ticket 05: contrato da Porta de cobrança

- **Decisão:** a porta tem duas operações: `emitir(cobrança)` e `trazer_retornos(pasta, início, fim)`, que grava na pasta os Retornos do período nos formatos públicos e devolve os caminhos: um arquivo de Pix recebidos (`pix_recebidos_AAAAMMDD_AAAAMMDD.json`, como a resposta de `GET /pix`) e um retorno CNAB 240 por banco (`retorno_cnab_<código do banco>_AAAAMMDD_AAAAMMDD.ret`), cada um só quando há pagamento. Emitir de novo a mesma cobrança não cria outra; um identificador já usado numa cobrança é recusado em outra. O `endToEndId` do Pix segue a ordem dos pagamentos na porta, então trazer períodos que se sobrepõem gera o mesmo Retorno e reimportar não duplica. O teste de contrato roda hoje só contra o adaptador simulado e usa `emitidas` e `pagar`, que um adaptador real teria de oferecer no ambiente de teste dele.
- **Por quê:** spec, módulo 4 e ADR 0007 (emitir e trazer retornos de um período para a pasta de entrada, nos formatos públicos). Reenviar depois de falha é o caso do ticket 01 (o mesmo txid volta à porta), e um adaptador real precisa aceitar isso sem duplicar. Os nomes casam com os padrões já sugeridos no `conciliacao.toml` (`*pix_recebidos*.json`, `*retorno_cnab*.ret`).
- **Alternativas:** nome de arquivo fixo (cada busca sobrescreveria a anterior na pasta); arquivo vazio quando não há pagamento (ruído na pasta).

## Fase 2, ticket 05: Encargo no adaptador da porta

- **Decisão:** o adaptador simulado recebe os parâmetros de Encargo na construção (o comando `emitir-cobrancas` passa o `[encargo]` da configuração), como ficou combinado no ticket 01. Com eles calcula o valor da `cobv` na data do pagamento (multa e juros a partir do Vencimento efetivo, pela mesma fórmula do motor, agora exposta em `multa_e_juros`) e recusa pagamento que a spec não permite: Pix com txid fora do valor da cobrança na data, boleto acima do valor com Encargo ou com acréscimos que não são a diferença para o valor do boleto, identificador já pago ou não emitido pela porta. O Pix recebido traz `componentesValor` com `original`, `multa` e `juros`; o CNAB traz multa e juros somados nos acréscimos.
- **Por quê:** história 11 (multa e juros da cobrança vêm do Encargo da fase 1) e história 39 (Pix com txid sempre com o valor da cobrança). Quem calcula o valor da `cobv` na data é o PSP, então a regra fica na porta, e o simulador não consegue inventar o que a spec proíbe.
- **Alternativas:** multa e juros em cada `CobrancaIdentificada` (contra o "só" do ticket 01); validar só no simulador (a porta aceitaria pagamento impossível).

## Fase 2, ticket 05: Plano por proporções

- **Decisão:** para cada Título com Cobrança identificada, um único sorteio com semente escolhe o desfecho: em dia, atraso com multa, atraso sem Encargo, parcial em boleto autorizado ou Crédito solto. As proporções somam 1 (padrão 55%, 10%, 10%, 5% e 20%, premissas sem base em dado real). O desfecho dá a data e o valor; o canal sai da regra, não do desfecho: o Pix com txid só aceita o valor da cobrança na data, o boleto da plataforma aceita até o valor com Encargo, inclusive abaixo dele (parcial). Quando nenhum Identificador da cobrança aceita o valor (atraso sem Encargo ou parcial de Título que só tem Pix, como os do Protheus), o pagamento chega como Crédito solto com esse valor, e o gabarito guarda o desfecho sorteado. Em dia é um dia útil de 7 dias antes do vencimento até o Vencimento efetivo, a partir do início da simulação; atraso, até 20 dias depois do Vencimento efetivo, como no gerador da fase 1.
- **Por quê:** spec, módulo 5 e histórias 38 a 40 e ADR 0007 (valor a menos com identificador só em boleto com parcial autorizado; no Pix, só como Crédito solto). Escolher o canal pela regra vale também com Encargo zero, quando o Pix atrasado sem Encargo é o valor da cobrança.
- **Alternativas:** sortear de novo quando o desfecho não cabe no canal (as proporções deixariam de ser as configuradas); mandar o parcial do Título só com Pix pelo Pix (contra a spec).
- **Ponto em aberto:** a emissão não diz se o boleto autoriza pagamento parcial (a spec não tem regra para isso), então o simulador trata todo boleto da plataforma como autorizado quando sorteia o parcial. O boleto do Protheus não é usado pelo simulador: ele só paga as Cobranças identificadas que a porta emitiu.

## Fase 2, ticket 05: Crédito solto no simulador

- **Decisão:** o Crédito solto usa a bagunça do gerador da fase 1, com os pesos das proporções padrão dele: CNPJ no histórico (às vezes de filial), nome truncado, nome abreviado e nome invertido, por Pix ou TED, e depósito sem nome. As variações de nome só valem no desfecho Crédito solto (em dia e valor exato); o solto que vem de atraso sem Encargo ou de parcial usa só CNPJ no histórico ou depósito, como o gerador faz com atraso e parcial sem nosso número. Cada variação só é usada quando dá um destino certo, com as mesmas condições do gerador (Valor único entre os Títulos do Franqueado, Nome por prefixo de um só Franqueado, nome para a IA sem prefixo e não repetido); senão o Crédito vira depósito sem nome. Para isso o simulador recebe os Títulos em aberto (o "mundo"), além das cobranças; quem chama passa os Títulos com o valor que o motor vai usar.
- **Por quê:** história 41 e o critério do ticket. O gabarito precisa dizer o destino de cada Crédito sem rotular à mão (história 43); as condições do gerador são as que já provaram, no teste de volume da fase 1, que o motor chega ao destino esperado. A lógica de Valor único e os nomes foram extraídos do gerador sem mudar o que ele gera.
- **Alternativas:** nomes inventados à parte (não seria a bagunça da fase 1); gabarito sem garantia de destino nos soltos.

## Fase 2, ticket 05: Extrato e contas do simulador

- **Decisão:** o simulador devolve o Extrato de cada conta no layout do Itaú, e quem chama dá o nome do arquivo (o que casa com a `[[contas]]` daquela conta). O Crédito do Pix com txid vai para a conta cuja `[[contas]]` casa com o arquivo de Pix da porta, com histórico `PIX RECEBIDO` e o nome truncado do Franqueado; o do boleto da plataforma vai para a conta do retorno CNAB, que precisa ser a de `[migracao.boleto]`, com histórico `LIQUIDACAO COBRANCA SIMPLES` e sem documento; o Crédito solto vai para qualquer conta com Extrato. Conta, data e valor nunca se repetem entre os Créditos simulados. O destino do Crédito identificado no gabarito vem da regra de valor da fase 1 (Lista quando fecha com o Encargo, senão Fila com "valor não fecha" apontando o Título).
- **Por quê:** história 37 (Créditos só pelo Extrato). Sem o nosso número no documento, quem identifica o boleto é o retorno CNAB trazido pela porta, que é o caminho que o ticket quer verificar. Conta, data e valor únicos garantem um par só entre Retorno e Crédito, então o gabarito não depende do desempate do ticket 04.
- **Alternativas:** nosso número também no documento do Extrato (o retorno CNAB não seria necessário no fluxo ponta a ponta); o simulador inventar o nome do arquivo a partir do padrão glob da conta.

## Fase 2, ticket 05: o que ficou de fora

- **Decisão:** a opção de linha de comando para demonstrar o simulador e as proporções em `[migracao]` no `conciliacao.toml` (spec, módulo 1) não entraram; as proporções e a semente são dadas em código pelos testes. Os dois testes de falha da porta dos tickets 01 e 03 passaram a estender `PortaSimulada`, porque a interface da porta ganhou `trazer_retornos`.
- **Por quê:** os critérios do ticket são todos verificados por testes; a análise de impacto (tickets 06 e 07) é quem vai usar o simulador e definir de onde vêm a semente e as proporções.
- **Alternativas:** criar já a seção de configuração sem quem a use.

## Fase 2, ticket 06: Franqueado do Crédito no Ranking de migração

- **Decisão:** o Ranking conta os Créditos da Fila de exceções do "antes" com os quatro Motivos que o Identificador de cobrança resolve. O Crédito conta para o Franqueado que a conciliação identificou (o mesmo da causa raiz da fase 1); sem ele, para o Franqueado dos Títulos sugeridos na Fila, quando são todos de um só Franqueado. O que sobra fica numa linha "sem Franqueado", fora de qualquer Onda de migração. A ordem é quantidade decrescente, depois valor decrescente e, persistindo o empate, a raiz do CNPJ, para o resultado não depender da ordem dos arquivos. Créditos fora da Fila (inclusive Conciliado fora) não entram.
- **Por quê:** spec, história 52 e módulo 9 ("Franqueados ordenados pelo número de Créditos ... deles"). Na fase 1, quase todo Crédito "sem identificação do pagador" fica sem Franqueado, porque só o valor aponta o Título; sem a sugestão, o motivo que a Cobrança identificada mais resolve quase não entraria no ranking, e o Franqueado que paga por depósito sem nome nunca seria migrado numa onda. A sugestão da Fila é a mesma que o módulo 10 aceita como última fonte da verdade de qual Título o Crédito paga. Na amostra de julho, o depósito não identificado entra no ranking pelo Título sugerido.
- **Alternativas:** só o Franqueado identificado, como a causa raiz (deixaria de fora quase todo "sem identificação do pagador"); dividir o Crédito entre os Franqueados citados (contaria o mesmo Crédito mais de uma vez).

## Fase 2, ticket 06: configuração da análise de impacto

- **Decisão:** a semente e o tamanho da onda ficam numa seção própria, `[analise_de_impacto]` (`semente`, padrão 1, e `tamanho_da_onda`, padrão 10 Franqueados), opcional e validada como as demais. A análise roda com ou sem `[migracao]`. A faixa de Adesão do ticket 07 deve entrar na mesma seção.
- **Por quê:** a spec (módulo 1) põe tamanho da onda e faixa de Adesão na configuração de migração, mas são premissas da análise, não da migração real, e a análise precisa rodar sobre a amostra de julho, cuja configuração não tem `[migracao]`. Exigir `[migracao]` ligaria também os adaptadores de Retorno e a emissão só para mudar o tamanho da onda. A semente na configuração, e não na linha de comando, faz a mesma configuração dar sempre o mesmo relatório.
- **Alternativas:** chaves em `[migracao]`, como a spec diz (a análise de julho exigiria ligar a fase 2); opções de linha de comando (o relatório dependeria de como o comando foi chamado, e a aba Premissas teria de repetir isso).

## Fase 2, ticket 06: comando e armazenamento temporário

- **Decisão:** o comando é `analisar-impacto <pasta base> [--configuracao] [--saida]` (padrão `analise_de_impacto.xlsx`). O "antes" é `executar_conciliacao` sobre a pasta com um armazenamento SQLite novo num diretório temporário apagado ao fim, sem workbook anterior e com o Parecerista de nome da `[ia]` da configuração (a função recebe o Parecerista, como a execução diária). Nada é gravado na pasta base nem no `conciliacao.sqlite`. O workbook tem só as abas Ranking de migração (onda, posição, Franqueado, raiz, quantidade e valor, mais a linha "sem Franqueado") e Premissas (semente, multa, juros, tolerância, tamanho da onda, Motivos do ranking, regra do Franqueado do Crédito e como o "antes" é conciliado). O workbook diário não muda.
- **Por quê:** spec, módulo 10 e história 57, e o critério do ticket. A opção de informar um armazenamento com decisões confirmadas da Analista é fonte da verdade do ticket 07 e entra com ele.
- **Alternativas:** `--estado` já neste ticket (sem uso até o ticket 07); reaproveitar o armazenamento do dia a dia (o "antes" carregaria decisões e Pagadores conhecidos, e a análise mexeria no estado real).

## Fase 2, ticket 07: fonte da verdade

- **Decisão:** cada Crédito do "antes" tem a fonte da primeira destas que o conhece, e ela decide sozinha, inclusive quando diz que não há Título: o gabarito do gerador (casado por conta, data, histórico, documento, valor e natureza), passado só pela função `analisar_impacto`, porque o gerador não escreve o gabarito na pasta; as decisões da Analista no armazenamento de `--estado` (confirmações em vigor dão os Títulos; antecipação, devolução, erro, Conciliado fora e Possível fonte não integrada dizem que o Crédito não tem Título); a Proposta da Lista ou a sugestão da Fila do "antes" (os Títulos do item, nunca os citados como alternativas). O `--estado` é copiado para o diretório temporário antes de ser aberto, então o arquivo da Analista não muda. A aba Premissas mostra quantos Créditos vieram de cada fonte.
- **Por quê:** spec, módulo 10, passo 2, e critério do ticket. Cair para a fonte seguinte quando uma fonte diz "sem Título" trocaria uma decisão por um palpite (uma devolução viraria pagamento de um Título sugerido pelo valor).
- **Alternativas:** só as confirmações como decisões (a sugestão do "antes" voltaria para Créditos que a Analista disse não terem Título); arquivo de gabarito na pasta (o gerador teria de mudar só para isso).

## Fase 2, ticket 07: quem chega identificado no depois

- **Decisão:** os Créditos do "antes" são ordenados por data e chave natural e cada um recebe um sorteio (`random.Random(semente)`), na mesma ordem, quer possa chegar identificado ou não. Fica como veio, sem depender da Adesão: o Crédito que já chegava pelo nosso número ou por Identificador de cobrança; o sem Título conhecido; o que paga um Título sem Cobrança identificada (fora dos em aberto da pasta base, em Possível duplicidade não decidida, como na emissão, ou com a cobrança já paga por um Crédito anterior da mesma análise); e o "não identificável pelo valor". Os demais chegam identificados quando `sorteio × 100 < Adesão`, então a Adesão maior contém a menor; os outros contam como "sorteio acima da Adesão". O Resumo do impacto mostra as quantidades e valores de cada razão.
- **Por quê:** spec, módulo 10, passo 3, e histórias 47 a 50. Decidir valor e cobrança antes do sorteio faz "não identificável pelo valor" ser uma propriedade do Crédito, igual em toda Adesão, e garante que com 100% todo Crédito com Título conhecido e valor permitido chega identificado. Se o Título já pago fosse decidido depois do sorteio, um Crédito identificado com 50% poderia perder o Título para outro com 80%.
- **Alternativas:** contar "não identificável pelo valor" só entre os sorteados (o número mudaria com a Adesão sem nada mudar no Crédito); sortear só os elegíveis (o sorteio de um Crédito dependeria dos outros).

## Fase 2, ticket 07: valor e canal do pagamento identificado

- **Decisão:** o Plano contrafactual (`Contrafactual` no simulador, que agora divide a base com o Plano por proporções) usa a mesma regra de canal do ticket 05: o Pix com txid aceita só o valor da cobrança na data (com multa e juros quando atrasado) e o boleto da plataforma aceita até o valor com Encargo, inclusive parcial. Quando os dois aceitam, vai o Pix. Crédito de vários Títulos vira um pagamento por Título no mesmo dia, cada um pelo valor do Título ou cada um pelo valor com Encargo, quando essa soma é o Crédito; se não for, ou se alguma parte não tiver canal, o Crédito inteiro fica "não identificável pelo valor". O desfecho do gabarito sai da data e do valor (parcial, em dia, atraso sem Encargo, atraso com multa). Quando o valor não é o da cobrança com Encargo, os acréscimos do boleto são a diferença acima do valor da cobrança (antes eram zero, o que nunca acontecia no Plano por proporções).
- **Por quê:** spec, módulos 5 e 10 e histórias 39, 40, 48 e 49 (ADR 0007). Escolher o Pix segue a Cobrança identificada (todo Título tem Pix; o boleto só quando falta). A divisão por Título não inventa valor: só usa as duas formas em que a soma fecha sem escolher como repartir uma diferença.
- **Alternativas:** canal pelo histórico do "antes" (TED e depósito não têm canal identificado equivalente); repartir a diferença entre os Títulos (inventaria a divisão).
- **Ponto em aberto:** o Plano contrafactual não usa as proporções do simulador, então a aba Premissas não as mostra; elas continuam só no fluxo ponta a ponta do ticket 05.

## Fase 2, ticket 07: pasta, configuração e emissão do depois

- **Decisão:** para cada Adesão, a análise cria um armazenamento temporário novo, emite pela porta simulada para todos os Títulos em aberto da pasta base fora de Possível duplicidade não decidida (a emissão foi dividida em selecionar e `emitir`, que a análise chama sem o corte de vencidos, porque a cobrança teria saído antes do pagamento), paga na porta, monta a pasta do "depois" e roda a mesma conciliação com o mesmo Parecerista. A pasta copia da base tudo que não casa com nenhuma `[[contas]]` (exportações e o resto) e escreve um Extrato no layout do Itaú por conta, com os lançamentos do "antes" que ficam e as linhas dos pagamentos identificados, mais os Retornos trazidos pela porta. A configuração do "depois" é a da base com: um Extrato por par banco e conta (nome fixo `depois_extrato_NN.csv`), todos os Franqueados migrados e Pix e boleto creditados na primeira conta com lançamentos (a conta de cobrança, mostrada em Premissas), com uma faixa de nosso número própria da análise (20 dígitos começando por 9). Isso vale com ou sem `[migracao]` na configuração.
- **Por quê:** spec, módulo 10, passo 4, e história 57. O Pix recebido tem um arquivo por período, ligado a uma única conta, então o pagamento identificado vai para a conta de cobrança (mesmo valor, data e Franqueado; só a conta pode mudar). A faixa própria não colide com o nosso número do Protheus e não toca a faixa real, que só existe no armazenamento diário. Com Adesão 0% nada muda nos Extratos e o "depois" sai igual ao "antes".
- **Alternativas:** usar `[migracao]` da configuração (a amostra de julho não tem; a análise exigiria ligar a fase 2); manter o Crédito identificado na conta original (o arquivo de Pix recebidos não teria uma conta só).
- **Ponto em aberto:** Retornos que estejam na pasta base não vão para o "depois", e um Crédito identificado só por eles volta ao caminho da fase 1; a amostra de julho e o gerador não têm Retornos. Mover um Crédito para a conta de cobrança pode antecipar a Data de referência quando ele era o último lançamento da conta de origem; isso só afeta a Lista de cobrança, que não entra no relatório.

## Fase 2, ticket 07: Resumo do impacto e Fila por motivo

- **Decisão:** a faixa de Adesão fica em `[analise_de_impacto] faixa_de_adesao_percentual` (padrão `[50, 80, 95]`, cada uma de 0 a 100, sem repetição, ordenadas). O workbook passa a ter as abas Resumo do impacto, Fila por motivo, Ranking de migração e Premissas. O Resumo tem uma linha para o "antes" e uma por Adesão com Créditos identificados e soltos, "não identificáveis pelo valor", Fila e % resolvido sozinho (quantidade e valor), e abaixo os Créditos que ficam soltos por razão. Identificado é o Crédito cuja evidência é nosso número ou Identificador de cobrança, pelo resultado da conciliação, a mesma regra no "antes" e no "depois"; solto é o resto. A Fila por motivo tem os oito Motivos e o total, no "antes" e em cada Adesão.
- **Por quê:** spec, módulo 10, passo 5, e decisão do ticket 06 (parâmetros da análise em `[analise_de_impacto]`). Medir identificados pelo resultado, e não pelo plano, mostra também o pagamento planejado que o enriquecimento não ligou.
- **Alternativas:** contar identificados pelo Plano (esconderia um Retorno que não enriquece).

## Fase 2, ticket 08: Ondas de migração no relatório

- **Decisão:** para cada onda acumulada do Ranking de migração (os Franqueados da onda 1 até ela) e cada Adesão da faixa, a análise roda um "depois" como o do ticket 07, com armazenamento temporário novo: só os Títulos dos Franqueados já migrados recebem Cobrança identificada e a configuração do "depois" declara só eles em `[migracao]`. O Crédito pertence ao Franqueado dos Títulos que a fonte da verdade diz que ele paga; ele só pode chegar identificado quando todos esses Títulos são de Franqueados migrados, senão fica solto como "Franqueado não migrado". As razões que não dependem da onda (sem Título conhecido, Título sem Cobrança identificada, não identificável pelo valor) são decididas uma vez, como se todos estivessem migrados, antes da migração e do sorteio; depois vem "Franqueado não migrado" e por último "sorteio acima da Adesão". O sorteio é o mesmo do ticket 07. Assim o conjunto de Créditos identificados cresce com a onda e com a Adesão.
- **Por quê:** spec, módulo 10, passo 3 ("para cada Adesão e cada onda acumulada") e história 54, e critérios do ticket. O Ranking atribui o Crédito ao Franqueado identificado ou sugerido, mas no "depois" quem chega identificado é o pagamento de uma Cobrança, que é do Franqueado do Título. Se "Título já pago" ou "não identificável pelo valor" fossem decididos só entre os migrados, um Crédito de Franqueado migrado numa onda posterior poderia tomar um Título de um Crédito já identificado antes, e a Fila poderia crescer de uma onda para a seguinte.
- **Alternativas:** usar o Franqueado do Ranking (um Crédito poderia chegar identificado pagando Título de quem não foi migrado); emitir para todos os Títulos e só filtrar os pagamentos (haveria Cobrança identificada de Franqueado não migrado).

## Fase 2, ticket 08: aba Ondas

- **Decisão:** nova aba Ondas, logo depois do Resumo do impacto, com uma linha para o "antes", uma por onda acumulada e Adesão e, no fim, uma por Adesão com todos os Franqueados migrados (os mesmos números do Resumo). Colunas: onda acumulada, Franqueados migrados, Adesão, Créditos identificados, Créditos de Franqueados não migrados, Fila em quantidade e valor e % resolvido sozinho em quantidade e valor. O Resumo do impacto continua sem a razão "Franqueado não migrado", que lá é sempre zero. Os testes que listam as abas do workbook da análise passaram a incluir Ondas.
- **Por quê:** spec, módulo 10, passo 5, e critério do ticket. A linha de todos os Franqueados mostra o que fica de fora das ondas: o Ranking só tem os Franqueados com Créditos na Fila pelos quatro Motivos que o identificador resolve, e Franqueados fora dele também têm Créditos que chegariam identificados. No sintético de 1.900 Títulos, com a configuração padrão, a última onda (101 Franqueados) deixa a Fila em 117 com 95% de Adesão e todos os 210 deixam em 70.
- **Alternativas:** uma coluna por Adesão (a tabela fica larga com a faixa configurável); só as ondas, sem a linha de todos (esconderia a diferença).
- **Ponto em aberto:** cada onda e Adesão é uma conciliação inteira; no sintético de 1.900 Títulos, com ondas de 10 e três Adesões, são 36 conciliações e a análise leva cerca de 2 minutos.

## Correção: Retorno de Crédito já encerrado pela Analista

- **Decisão:** o enriquecimento procura o Crédito do Retorno entre todos os Créditos guardados ainda sem Retorno, não só entre os vivos. Um Retorno que chega depois de a Analista encerrar o Crédito (confirmação, devolução, erro ou Conciliado fora) é ligado a ele pelo par conta, data e valor, com o mesmo desempate pelo pagador, e sai do Resumo. A decisão da Analista não muda: o Crédito encerrado continua fora da classificação, e o Retorno só passa a valer se a decisão for revertida e o Crédito voltar a viver, como se tivesse chegado antes. Um Crédito encerrado com a mesma conta, data e valor de um vivo também conta no par, então um Retorno que antes ligaria sozinho ao vivo passa a depender do pagador.
- **Por quê:** ponto em aberto do ticket 04. A confirmação é a decisão mais comum e o arquivo de Pix recebidos pode chegar um dia depois do Extrato; sem isso, o Retorno ficaria em todo Resumo para sempre, esperando um Extrato que já chegou. O Retorno é do pagamento, e o pagamento existe, encerrado ou não; ligá-lo só enriquece (ADR 0001). Contar o Crédito encerrado no par é o mesmo princípio de nunca escolher entre opções igualmente válidas.
- **Alternativas:** parar de mostrar o Retorno depois de um prazo (a spec não dá prazo e esconderia um Retorno de fato sem Crédito); ligar só quando não há Crédito vivo no par (escolheria o vivo só porque está vivo).

## Fase 2, ticket 09: aceitação de julho

- **Decisão:** o teste de aceitação roda a análise sobre `data/` com o `conciliacao.toml` do projeto (semente 1, ondas de 10), a faixa de Adesão trocada só no teste por 0%, 50%, 80%, 95% e 100%, e o Parecerista falso que reconhece os dois nomes da fase 1; com `-m integracao` roda também com o Ollama e espera os mesmos números. A fixture tem o antes e cada Adesão (Créditos identificados, Fila e sorteio acima da Adesão), as razões de ficar solto que não mudam com a Adesão e os cinco Créditos que ficam na Fila com toda a Adesão. Em todas as Adesões e na única onda de julho: o dinheiro do depois é o do antes e a Fila nunca aumenta.
- **Por quê:** critérios do ticket e ponto 2 da spec (Adesão 0% igual ao antes, 100% identifica tudo que pode). O padrão de 50%, 80% e 95% continua sendo o que o comando usa; os extremos só entram no teste.
- **Alternativas:** um teste por número espalhado pelos testes dos tickets 06 a 08 (os números de julho já apareciam lá, mas sem a amostra inteira num lugar só).

## Fase 2, ticket 09: Premissas e a verdade de julho

- **Decisão:** a aba Premissas ganha a linha "Limite da fonte da verdade": "N de M Créditos não têm gabarito nem decisão confirmada da Analista: a verdade deles é a Proposta ou a sugestão do próprio antes, então o depois supõe que o antes acertou o Título e um erro do antes passa para o depois". Em julho, 15 de 15.
- **Por quê:** spec (Further Notes, "Limite da análise de julho") e critério do ticket. As contagens por fonte já existiam, mas não diziam o que isso significa para o número do depois. A frase vale para qualquer pasta, não só para julho.
- **Alternativas:** um texto fixo sobre julho (o código de produção não conhece a amostra).

## Fase 2, ticket 09: aceitação no sintético de volume real

- **Decisão:** o teste usa o gerador da fase 1 com os padrões (cerca de 1.900 Títulos, 210 Franqueados, 4 contas no layout do Itaú, porque os layouts dos outros 3 bancos continuam ponto em aberto da fase 1; mesma semente do teste de volume da fase 1), a semente e a faixa de Adesão padrão da análise e ondas de 50 Franqueados, e confere em todo depois (cada onda acumulada e todos os Franqueados, em cada Adesão): nenhum item da Lista diverge do gabarito, o dinheiro é o do antes e a Fila nunca aumenta com a Adesão nem com a onda. Item da Lista que é um Crédito do antes precisa ter os Títulos do gabarito; pagamento identificado (Crédito novo do depois) precisa pagar um único Título que o gabarito diz ter sido pago, no mesmo dia, por um Crédito que saiu do antes. O tempo da geração mais a análise precisa ficar abaixo de 120 segundos.
- **Por quê:** com ondas de 10 (padrão) e a IA falsa que reconhece os nomes, o Ranking tem 132 Franqueados, 14 ondas e 45 conciliações, cerca de 2,5 minutos no MacBook Air M2, o dobro da suíte inteira. Ondas de 50 dão 3 ondas e 12 conciliações do depois, cerca de 40 segundos, e ainda verificam a Fila de uma onda para a seguinte. O projeto não tem marcação de teste lento e o tempo não justifica otimizar a análise: ela roda de vez em quando, não no fluxo diário. A medida da configuração padrão fica no README. O ticket 08 citava 11 ondas porque media com uma IA falsa que não reconhece nomes (101 Franqueados no Ranking).
- **Alternativas:** a configuração padrão no teste (2,5 minutos a mais em toda execução da suíte); criar uma marcação de teste lento (o critério de tempo deixaria de ser verificado na suíte padrão); paralelizar as conciliações (otimização sem necessidade).

## Fase 2, ticket 09: README e o que ficou de fora

- **Decisão:** o projeto ganha um README com o que a plataforma faz, instalação, os quatro comandos, a análise de impacto, os testes, o que ficou fora do escopo e os próximos passos (conta virtual por Franqueado e Pix Automático para royalty, sem implementação). A opção de linha de comando para demonstrar o simulador por proporções e as proporções no `conciliacao.toml` (spec, módulo 1 e "Comandos") continuam de fora e aparecem no README como fora do escopo da fase 2.
- **Por quê:** spec, história 60 e módulo 13. Nenhum critério do ticket 09 depende do simulador por proporções: a análise de impacto usa o Plano contrafactual (ticket 07), e o simulador por proporções só serve ao ponta a ponta e à demonstração, que os testes cobrem com as proporções em código.
- **Alternativas:** implementar a demonstração agora (comando e configuração sem quem os use no fluxo diário nem na análise).
