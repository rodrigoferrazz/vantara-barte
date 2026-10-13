# Conciliação de Contas a Receber - Vantara

Plataforma que liga cada crédito bancário aos títulos a receber dos franqueados, para que a analista de conciliação só decida o que regra não resolve.

## Language

### Partes

**Franqueado**:
Empresa franqueada da Vantara, identificada pela raiz do CNPJ (8 dígitos).
_Avoid_: Cliente, sacado

**Pagador conhecido**:
CNPJ, CPF ou nome de extrato já vinculado a um Franqueado, como filial, sócio ou apelido truncado.
_Avoid_: Alias, depositante

**Analista de conciliação**:
Pessoa que confirma ou rejeita propostas e dá a baixa no ERP.
_Avoid_: Usuário, operador

### Origem dos dados

**Sistema de origem**:
ERP ou planilha onde um Título foi registrado (Protheus, Omie).
_Avoid_: Fonte, base

**Título**:
Valor a receber de um Franqueado registrado num Sistema de origem, com vencimento.
_Avoid_: Fatura, boleto, nota, invoice

**Extrato**:
Lançamentos de uma conta bancária; é a fonte principal do que foi efetivamente recebido.
_Avoid_: Retorno, movimento

**Crédito**:
Lançamento de entrada no Extrato.
_Avoid_: Pagamento, recebimento, depósito

### Conciliação

**Proposta de baixa**:
Vínculo entre um ou mais Créditos e um ou mais Títulos, com a explicação de como foi encontrado.
_Avoid_: Match, sugestão

**Lista de baixa**:
Propostas de baixa prontas para a Analista confirmar sem investigação.
_Avoid_: Auto-baixa, baixados

**Fila de exceções**:
Casos que exigem decisão da Analista antes de qualquer baixa.
_Avoid_: Pendências, fila manual

**Aguardando baixa no ERP**:
Título com Proposta de baixa confirmada na plataforma que ainda aparece em aberto no Sistema de origem.

**Possível duplicidade entre sistemas**:
Títulos do mesmo Franqueado, valor e vencimento em Sistemas de origem diferentes, sem decisão sobre serem a mesma dívida.

**Saldo**:
Quanto ainda falta receber de um Título. Se o valor mudou entre exportações, é o novo valor do ERP; se não mudou, é o valor menos as baixas confirmadas na plataforma.

**Estorno necessário no ERP**:
Confirmação revertida na plataforma cujo Título já foi baixado no Sistema de origem.

**Baixado por fora**:
Título que sumiu da exportação sem ter Proposta de baixa da plataforma.

**Divergência de baixa**:
Analista baixou no Sistema de origem um Título diferente do proposto; o caso volta para a Fila de exceções.

**Conciliado fora**:
Crédito atribuído a um Franqueado e a uma referência fora da plataforma, normalmente de uma Possível fonte não integrada.

**Vencimento efetivo**:
Vencimento do Título prorrogado para o próximo dia útil quando cai em fim de semana ou feriado bancário nacional; é a base para atraso e Encargo.

**Nome por prefixo**:
Nome do Extrato que, normalizado, é o começo de algum dos nomes do Franqueado, em qualquer Sistema de origem, ligados pela raiz do CNPJ. Qualquer outra semelhança (abreviação, palavras invertidas, palavras faltando) exige parecer da LLM.

**Encargo**:
Multa e juros por atraso previstos em contrato, somados ao valor do Título.

**Diferença a menor**:
Crédito abaixo do valor do Título, por desconto, retenção ou pagamento parcial. Pagamento atrasado só com o valor original não é Diferença a menor: é Encargo não pago.

**Encargo não pago**:
Atraso quitado só pelo valor original; segue como se estivesse em dia e a explicação registra que o Encargo não foi pago.

**Valor a maior**:
Crédito acima do valor do Título somado ao Encargo previsto.

**Valor único**:
Valor que corresponde a um só Título, ou a uma só combinação de Títulos, entre os em aberto do mesmo Pagador conhecido.

**Crédito sem título em aberto**:
Crédito de Franqueado identificado sem nenhum Título candidato; continua vivo e é retentado a cada nova importação.

### Saídas

**Data de referência**:
O "hoje" da conciliação: a data do último lançamento do Extrato, não a data do computador.
_Avoid_: Hoje, data atual

**Lista de cobrança**:
Títulos vencidos na Data de referência com saldo em aberto e sem Crédito candidato, confirmado ou em análise.
_Avoid_: Inadimplentes, devedores

**Motivo de não identificação**:
Causa principal, e única, de um Crédito estar na Fila de exceções; base do relatório de causa raiz.

**Pagador provável, primeira vez**:
Motivo de não identificação para Crédito que só foi para a Fila porque o nome bate por semelhança e ainda não foi confirmado como Pagador conhecido.

**Fora do escopo**:
Lançamento do Extrato que não é Crédito de Franqueado, como débitos e tarifas.

**Arquivo recusado**:
Arquivo de entrada com layout, formato ou banco não reconhecido; não é processado e não impede os demais.

**Possível fonte não integrada**:
Motivo de não identificação para Crédito que provavelmente pertence a um Título de um Sistema de origem fora da plataforma, como as planilhas da terceira unidade.

### Cobrança

**Cobrança identificada**:
Meio de pagamento emitido para um único Título, com Identificador de cobrança próprio, para que o pagamento chegue dizendo qual Título paga.
_Avoid_: Boleto, QR, link de pagamento

**Identificador de cobrança**:
Código que liga um pagamento a um único Título: o nosso número do boleto ou o txid do Pix.
_Avoid_: Referência, código de barras

**Retorno de cobrança**:
Aviso do banco de que uma Cobrança identificada foi paga (retorno CNAB do boleto ou Pix recebido); só enriquece um Crédito do Extrato, nunca cria um.
_Avoid_: Extrato, baixa

**Franqueado migrado**:
Franqueado cujos Títulos passam a ser emitidos com Cobrança identificada.

**Onda de migração**:
Grupo de Franqueados migrados juntos, na ordem dada pelo relatório de causa raiz.

**Crédito solto**:
Crédito de Franqueado migrado que chegou sem Identificador de cobrança, por Pix, TED ou depósito.
_Avoid_: Pix solto, pagamento avulso

**Adesão**:
Parte dos Créditos de Franqueados migrados que chega com Identificador de cobrança.
