# Spec: Conciliação de contas a receber, fase 2 (Cobrança identificada)

Status: ready-for-agent

Pré-requisito: a fase 1 implementada como descrita em `.scratch/conciliacao-fase1/spec.md`. Esta spec não repete nem altera nenhuma regra da fase 1; só acrescenta. Quando cita a fase 1, cita pelo número da história ou do módulo de lá. Glossário em `CONTEXT.md` (seção Cobrança para os termos novos). Decisões de arquitetura nos ADRs 0001 (Retorno de cobrança só enriquece), 0007 (porta e simulação pelas specs públicas) e 0008 (vínculo Identificador-Título na plataforma). Rascunho de origem em `docs/fase2-decisoes.md`.

## Problem Statement

A fase 1 reduz o trabalho da Analista de conciliação, mas trata o sintoma: o Crédito chega sem identificação porque a cobrança sai sem identificação. Hoje só os Títulos do Protheus têm boleto com nosso número. Os do Omie não têm nenhum identificador, e mesmo quem tem boleto paga muitas vezes por Pix ou TED com o nome cortado. Enquanto isso acontecer, a Fila de exceções nunca encolhe de verdade: a plataforma só fica melhor em adivinhar.

A Vantara não tem acesso a um sistema de pagamento real para testar a mudança, e o gestor financeiro precisa de evidência do impacto antes de pedir aos Franqueados que mudem a forma de pagar.

## Solution

Cada Título de um Franqueado migrado passa a ter uma Cobrança identificada: um Pix com txid e, quando ainda não tem, um boleto com nosso número. Assim o pagamento já chega dizendo qual Título paga. A plataforma gera os identificadores, guarda o vínculo com o Título (o Protheus continua só leitura) e envia para emissão só o mínimo: Título, valor, vencimento e CNPJ do Franqueado.

Sem sistema real, a emissão e o Retorno de cobrança passam por uma Porta de cobrança cujo adaptador é um simulador. Ele segue a API Pix do Banco Central e o retorno CNAB 240 da FEBRABAN e é imperfeito de propósito: gera pagamento parcial, atraso com multa, valor a menos e Crédito solto, em proporções ajustáveis. No dia em que existir o sistema real, troca-se só esse adaptador.

O motor é o da fase 1. O Identificador de cobrança é uma evidência nova, do mesmo nível do nosso número: leva o Crédito direto ao Título, mas o valor continua passando pelas mesmas regras. Crédito sem identificador segue o caminho da fase 1.

O entregável principal é uma **análise de impacto**: sobre os Títulos de julho e sobre os dados sintéticos de 1.900 Títulos, mostra quantos Créditos chegavam soltos, quantos chegariam identificados e quanto a Fila diminui, para uma faixa de Adesão e a cada Onda de migração. O relatório de causa raiz da fase 1 vira o Ranking de migração, que diz quais Franqueados migrar primeiro.

## User Stories

### Emissão

1. As a gestor financeiro, I want to declare which Franqueados are migrados in a configuration, so that Cobrança identificada is rolled out in Ondas de migração and not all at once.
2. As a gestor financeiro, I want a command that emits Cobrança identificada for every open Título of a Franqueado migrado that does not have one yet, so that new Títulos are covered without manual work.
3. As a gestor financeiro, I want a Título that already has a nosso número in Protheus to keep that boleto and receive only a Pix, so that no Título ever has two registered boletos.
4. As a gestor financeiro, I want a Título without a nosso número (for example, from Omie) to receive both a boleto and a Pix from the platform, so that every channel the Franqueado uses carries an identifier.
5. As a developer, I want the platform to generate the txid and the nosso número itself, following the formats of the public specs, so that the link to the Título exists before anything is sent out.
6. As a developer, I want the link between each Identificador de cobrança and its Título stored in the platform, never in Protheus, so that Protheus stays read-only (ADR 0002).
7. As the client, I want only Título, valor, vencimento and CNPJ do Franqueado to leave the platform for emission, so that the minimum data is shared.
8. As a gestor financeiro, I want running the emission twice to not emit the same Título twice, so that a repeated run is harmless.
9. As a gestor financeiro, I want identifiers never reused, even after a Título is baixado, so that an old payment can never point to a new Título.
10. As a gestor financeiro, I want overdue Títulos to stay out of the emission, so that they keep following the Lista de cobrança of fase 1.
11. As a developer, I want the multa and juros sent with the Pix cobrança to come from the same Encargo parameters of fase 1, so that what the Franqueado is charged and what the motor accepts are the same.

### Retorno de cobrança

12. As a Analista de conciliação, I want the CNAB 240 retorno file of each bank to be read from the same input folder as the Extratos, so that my routine does not change.
13. As a Analista de conciliação, I want the received Pix list, in the format of the API Pix, to be read from the same input folder, so that Pix with txid enters the same run.
14. As a Analista de conciliação, I want a Retorno file with an unknown layout to be refused on its own with the reason, so that one bad file never blocks the rest (ADR 0005).
15. As a Analista de conciliação, I want only liquidation movements of the CNAB retorno to be considered, so that confirmations, changes and cancellations of a boleto never look like money.
16. As a Analista de conciliação, I want a Retorno to only enrich a Crédito that already came from the Extrato, never to create one, so that the same money is never counted twice (ADR 0001).
17. As a Analista de conciliação, I want a Retorno to be paired with a Crédito by account, credit date and value, so that pairing needs no guessing.
18. As a Analista de conciliação, I want a tie between equal Créditos to be broken by the payer's CNPJ or name in the Retorno against the Extrato histórico, so that two Franqueados paying the same royalty on the same day are still told apart.
19. As a Analista de conciliação, I want a Retorno that still matches more than one Crédito, or none, to enrich nothing, so that the Crédito follows the fase 1 path instead of a guessed one.
20. As a Analista de conciliação, I want a Retorno with no Crédito in the Extrato yet to be shown in the Resumo and retried on the next import, so that an Extrato exported late is not a problem.
21. As a Analista de conciliação, I want re-importing the same Retorno to not duplicate anything, so that I can export generous periods.
22. As a Analista de conciliação, I want the Data de referência to keep coming only from the Extratos, so that a Retorno never moves the "hoje" of the reconciliation.

### Motor com Identificador de cobrança

23. As a Analista de conciliação, I want a Crédito with an Identificador de cobrança and value exact or within the Encargo to go to the Lista de baixa, so that identified payments need no investigation.
24. As a Analista de conciliação, I want a Crédito with an Identificador de cobrança and a value outside those rules to go to the Fila de exceções with "valor não fecha", so that identification never bypasses the value check.
25. As a Analista de conciliação, I want a partial payment of a boleto with pagamento parcial autorizado to go to the Fila as Diferença a menor with the Título already pointed, so that I only decide the amount, not the payer.
26. As a Analista de conciliação, I want late payments whose Retorno separates multa and juros to show those components in the explanation, so that I know exactly how much was Encargo.
27. As a Analista de conciliação, I want a Crédito whose identifier points to a Título already baixado to go to the Fila as Crédito sem título em aberto, so that a duplicate payment is caught.
28. As a Analista de conciliação, I want a Crédito with an identifier the platform does not know to go to the Fila as Possível fonte não integrada, so that a cobrança emitted outside the platform is investigated.
29. As a Analista de conciliação, I want the identifier to win over the payer, so that a QR paid by a sócio or a filial still goes to the right Título.
30. As a Analista de conciliação, I want paying a Cobrança identificada to never create a Pagador conhecido, so that only my confirmations teach the engine (fase 1, história 57).
31. As a Analista de conciliação, I want a boleto emitted by the platform and settled in the Extrato with its nosso número to be resolved exactly like a Protheus boleto, so that both work the same way.
32. As a Analista de conciliação, I want a Crédito solto from a Franqueado migrado to follow exactly the fase 1 path, so that nothing is lost while Franqueados learn to use the QR.
33. As a Analista de conciliação, I want the Lista and the Fila explanation to say which kind of identifier was used (txid or nosso número, and whether it came from the platform or from Protheus), so that I can audit the evidence.
34. As a developer, I want every fase 1 test to keep passing unchanged, so that fase 2 adds behavior without changing what already works.

### Simulação

35. As a developer, I want emission and Retorno to go through a single Porta de cobrança, so that the real system replaces only the simulated adapter (ADR 0007).
36. As a developer, I want the simulated Retorno files to follow CNAB 240 FEBRABAN (Segmentos T and U) and the API Pix received-Pix format, so that the real adapter is a known variation, not a rewrite.
37. As a developer, I want the simulator to produce Extrato lines for every simulated payment, in the existing bank layouts, so that Créditos keep coming only from the Extrato.
38. As a developer, I want configurable proportions of partial payment, late payment with multa, late payment without the Encargo, value below and Crédito solto, so that the simulation is as messy as reality.
39. As a developer, I want a Pix with txid to always arrive with the cobrança value, with or without multa, so that the simulation respects the cobv spec.
40. As a developer, I want a value below with identifier to happen only through a boleto with pagamento parcial autorizado, and otherwise only as a Crédito solto, so that the simulation never invents what the specs forbid.
41. As a developer, I want a Crédito solto to come by Pix, TED or deposit, with the same name mess as the fase 1 generator, so that the fase 1 path is exercised for real.
42. As a developer, I want the simulator to be seeded, so that the same configuration always produces the same files.
43. As a developer, I want the simulator to output the expected destination of every Crédito, so that tests measure precision without hand labeling.

### Análise de impacto

44. As a gestor financeiro, I want a command that takes a base folder and shows the reconciliation before and after Cobrança identificada, so that I see the impact before asking Franqueados to change.
45. As a gestor financeiro, I want the "after" to keep the same money as the "before" (value, date and Franqueado of each Crédito) and change only whether it arrives identified, so that the comparison is fair.
46. As a gestor financeiro, I want the result shown for a range of Adesão (for example 50%, 80% and 95%), so that I see the impact as a function of the assumption, not as a single forecast.
47. As a gestor financeiro, I want a higher Adesão to identify at least everything a lower one identified, so that the curve never goes backwards by chance.
48. As a gestor financeiro, I want a Crédito that paid several Títulos at once to become one identified payment per Título in the "after", with the same total, so that the comparison reflects how a Franqueado would pay with one QR per Título.
49. As a gestor financeiro, I want a Crédito whose value could never come by Pix with txid (a value below that is not an authorized partial boleto) to stay solto in the "after" and be counted separately, so that the analysis does not promise what the specs forbid.
50. As a gestor financeiro, I want a Crédito without a known Título (for example, Crédito sem título em aberto) to stay solto in the "after", so that the analysis never invents a Título.
51. As a gestor financeiro, I want the report to show, for each scenario, how many Créditos arrived solto and identified (count and amount), the Fila size (count and amount), the share resolved automatically and the Fila by Motivo de não identificação, so that I know where the gain comes from.
52. As a gestor financeiro, I want the Ranking de migração: Franqueados ordered by how many of their Créditos went to the Fila for motives that Cobrança identificada solves, so that I know whom to migrate first.
53. As a gestor financeiro, I want Crédito sem título em aberto, Possível duplicidade entre sistemas and Possível fonte não integrada left out of the ranking, so that it only counts what an identifier fixes.
54. As a gestor financeiro, I want the ranking split into Ondas de migração of configurable size and the report to show how much the Fila falls after each cumulative onda, so that I can plan the rollout.
55. As a gestor financeiro, I want the same analysis on the July sample and on the 1.900-Título synthetic data, so that I see the effect both on real data and at real volume.
56. As a gestor financeiro, I want the report as an Excel workbook, like the other outputs, so that I can share it without any other tool (ADR 0006).
57. As a developer, I want the analysis to run the same reconciliation as the daily run, with fresh temporary storage and the same Parecerista de nome, so that "before" and "after" differ only by the identification.
58. As a gestor financeiro, I want the report to state which source of truth was used to know which Título each Crédito pays, so that I know how much of the "after" rests on suggestions instead of confirmations.

### Tela local

59. As a gestor financeiro, I want an impact page in the fase 1 local screen showing the before and after, the Adesão range and the Ondas de migração of the last analysis, so that I can present the impact without opening the workbook.

### Documentação

60. As a gestor financeiro, I want the README to describe conta virtual por Franqueado and Pix Automático for royalty as next steps, so that the path after fase 2 is recorded without being built now.

## Implementation Decisions

### Fronteira com a fase 1

- A fase 2 só acrescenta: novos adaptadores de fonte (Retornos), um novo tipo de evidência no motor, novas tabelas no armazenamento, novos módulos e dois comandos novos. Nenhuma regra, saída ou interface da fase 1 muda de comportamento.
- Sem vínculos de cobrança no armazenamento e sem Retornos na pasta, a execução da conciliação produz exatamente o que a fase 1 produz. A suíte da fase 1 é o critério de aceite disso e roda sem alteração.
- A evidência "Identificador de cobrança" entra no conjunto aberto de evidências do motor (fase 1, módulo 5) no mesmo nível do nosso número. A regra de nosso número da fase 1 (nosso número do Protheus no campo documento do Extrato) continua como está; o nosso número emitido pela plataforma é encontrado pelo vínculo, com a mesma regra de valor.
- Os Motivos de não identificação continuam os mesmos oito da fase 1. A fase 2 não cria motivo novo.

### Comandos

- **Conciliação** (o da fase 1, sem mudar a interface): a pasta de entrada agora pode conter arquivos de Retorno de cobrança.
- **Emitir cobranças**: lê a última fotografia de Títulos do armazenamento e a configuração de migração, gera identificadores, grava os vínculos e chama a Porta de cobrança.
- **Análise de impacto**: recebe uma pasta base e gera o relatório antes e depois.
- O simulador de pagamentos é usado pela análise de impacto e pelos testes; fora disso, é acionado por uma opção de linha de comando para demonstração, nunca no fluxo diário.

### Módulos

1. **Configuração de migração.** Lista de Franqueados migrados (raiz do CNPJ), tamanho da Onda de migração, faixa de Adesão padrão (50%, 80%, 95%), faixa de nosso número do beneficiário por conta e proporções do simulador. Sem configuração de migração, nada da fase 2 é executado.
2. **Gerador de identificadores.** txid alfanumérico de 26 a 35 caracteres (o formato de `cobv` na API Pix) e nosso número dentro da faixa configurada. Únicos e nunca reaproveitados.
3. **Emissão.** Seleciona Títulos em aberto de Franqueados migrados, sem Cobrança identificada, com Vencimento efetivo maior ou igual à Data de referência. Título com nosso número do Protheus recebe só Pix; os demais recebem boleto e Pix. Grava o vínculo antes de chamar a porta; emitir de novo não duplica. Multa e juros da cobrança vêm dos parâmetros de Encargo da fase 1 (módulo 4).
4. **Porta de cobrança.** Duas operações: emitir (Título, valor, vencimento, CNPJ do Franqueado e os identificadores) e trazer retornos de um período para a pasta de entrada, como arquivos nos formatos públicos. O adaptador simulado é o único nesta fase. Um adaptador real escreveria os mesmos formatos (o retorno CNAB baixado do banco e a resposta de Pix recebidos da API), então nada além dele muda.
5. **Simulador de pagamentos.** Recebe as Cobranças emitidas e um Plano de pagamentos e produz linhas de Extrato, nos layouts de banco que os adaptadores da fase 1 já aceitam, e os arquivos de Retorno correspondentes, além do gabarito. O Plano vem de uma de duas fontes:
   - **por proporções**: para cada Cobrança, sorteia (com semente) pagamento em dia, atraso com multa, atraso sem Encargo, parcial em boleto autorizado ou Crédito solto (por Pix, TED ou depósito, com a bagunça de nome do gerador da fase 1);
   - **contrafactual**: derivado dos Créditos de uma pasta base, mantendo valor, data e Franqueado (usado pela análise de impacto).

   Restrições da spec valem nas duas fontes: Pix com txid sempre com o valor da cobrança (com ou sem multa e juros); valor a menos com identificador só em boleto com pagamento parcial autorizado; no Pix, valor a menos só como Crédito solto.
6. **Adaptadores de Retorno.** Um para retorno CNAB 240 FEBRABAN (cabeçalho de arquivo e de lote, Segmentos T e U; só movimento de liquidação gera Retorno) e um para Pix recebidos no formato da resposta de `/pix` da API Pix (lista de Pix com `endToEndId`, `txid`, `valor`, `componentesValor`, `horario` e pagador). Seguem as regras dos adaptadores da fase 1: layout exato declarado, identificação pelo conteúdo, recusa por arquivo com motivo e banco e conta vindos da mesma configuração por nome de arquivo. Variações de banco sobre o CNAB 240 entram depois como adaptadores próprios.
7. **Enriquecimento.** Depois da leitura e antes do motor. Liga cada Retorno a um Crédito por conta, data do crédito e valor. Com mais de um candidato, desempata pelo CNPJ do pagador no histórico ou pelo nome do pagador ser Nome por prefixo do histórico (ou o contrário). Se ainda sobrar mais de um, ou nenhum, não enriquece. O Crédito enriquecido ganha o Identificador de cobrança e, quando o Retorno separa, principal, multa e juros. Retorno sem Crédito fica pendente, aparece no Resumo e é retentado na importação seguinte. Retorno nunca entra na conferência de soma nem na Data de referência.
8. **Motor (extensão).** Evidência "Identificador de cobrança": vínculo encontrado e Título em aberto leva às mesmas regras de valor do nosso número (Lista se exato ou dentro do Encargo; Encargo não pago segue normal; senão Fila com "valor não fecha"); Título já baixado leva à Fila com "Crédito sem título em aberto"; identificador desconhecido leva à Fila com "Possível fonte não integrada". Um identificador aponta um único Título; o motor não procura soma para Crédito identificado. O identificador vale mais que o pagador e nunca gera Pagador conhecido.
9. **Ranking de migração.** Calculado a partir do resultado de uma execução: Franqueados ordenados pelo número de Créditos na Fila com motivo sem identificação do pagador, nome ambíguo, mais de uma combinação possível ou pagador provável, primeira vez; desempate pelo valor desses Créditos. Dividido em Ondas de migração do tamanho configurado.
10. **Análise de impacto.** Passos:
    1. Roda a conciliação na pasta base com armazenamento temporário (o "antes") e calcula o Ranking de migração.
    2. Define a fonte da verdade de qual Título cada Crédito paga: o gabarito, quando a pasta vem do gerador; senão, as decisões confirmadas da Analista, quando um armazenamento é informado; senão, a Proposta da Lista ou a sugestão da Fila do "antes". O relatório diz quantos Créditos vieram de cada fonte.
    3. Para cada Adesão e cada onda acumulada, monta um Plano contrafactual: Créditos de Franqueados migrados com Título conhecido chegam identificados quando o sorteio do Crédito fica abaixo da Adesão. O sorteio é um único número por Crédito, fixo pela semente, então a Adesão maior contém a menor. Crédito que pagou vários Títulos vira um pagamento identificado por Título, no mesmo dia e com o mesmo total. Crédito com valor que a spec não permite com txid fica solto e é contado como "não identificável pelo valor". Crédito sem Título conhecido fica solto. Créditos que já chegavam identificados pelo nosso número continuam identificados.
    4. Emite pela porta simulada, gera a pasta do "depois" pelo simulador e roda a mesma conciliação com armazenamento temporário novo e o mesmo Parecerista de nome.
    5. Gera o workbook com abas Resumo do impacto (antes contra cada Adesão, com todos migrados), Ondas (queda da Fila a cada onda acumulada, por Adesão), Fila por motivo, Ranking de migração e Premissas (fonte da verdade, semente, proporções, parâmetros de Encargo).
11. **Armazenamento (acréscimo).** Tabelas novas, sem mudar as da fase 1: vínculos (identificador, tipo, origem plataforma ou Protheus, Título, Franqueado, valor e vencimento emitidos, data de emissão), Retornos importados (chave natural: tipo + `endToEndId` no Pix ou nosso número + data de ocorrência no boleto) e enriquecimentos (Retorno, Crédito, componentes de valor). Migração de esquema só aditiva.
12. **Página de impacto.** A análise de impacto também grava o resultado no armazenamento (tabela nova). A tela local da fase 1 ganha uma página só de leitura com antes e depois por Adesão, gráficos da Fila por Adesão e por onda acumulada (desenhados no servidor, sem recurso externo), Fila por motivo, Ranking de migração e Premissas. As páginas existentes da fase 1 não mudam, só ganham o acesso à página nova.
13. **README.** Seção de próximos passos: conta virtual por Franqueado e Pix Automático para royalty (a mesma API Pix já tem `/rec` e `/cobr`), sem implementação.

## Testing Decisions

- Bons testes exercitam comportamento externo: arquivos e configuração entram, saídas e relatório saem. Nenhum teste depende do formato interno do Plano de pagamentos, das tabelas novas ou da ordem de chamadas entre módulos.
- **Portão de entrada: a suíte da fase 1 roda sem nenhuma alteração** e precisa passar antes de qualquer teste da fase 2.
- **Ponto principal: a execução da conciliação** (o mesmo da fase 1). Os cenários montam a pasta com Extrato e Retornos e o armazenamento com vínculos:
  - Pix com txid e valor exato vai para a Lista com a explicação do identificador; com valor fora vai para a Fila com "valor não fecha";
  - boleto da plataforma liquidado com nosso número vai para a Lista igual a um boleto do Protheus;
  - boleto com parcial autorizado vai para a Fila como Diferença a menor apontando o Título;
  - CNAB com multa mostra principal, multa e juros na explicação;
  - identificador de Título baixado vai para "Crédito sem título em aberto"; identificador desconhecido vai para "Possível fonte não integrada";
  - dois Créditos iguais no mesmo dia desempatados pelo pagador; empate que persiste não enriquece e segue a fase 1;
  - Retorno sem Crédito aparece no Resumo e é ligado quando o Extrato chega na execução seguinte;
  - Retorno reimportado não duplica; arquivo de Retorno com layout estranho é recusado sozinho; movimento CNAB que não é liquidação é ignorado;
  - Crédito solto de Franqueado migrado tem exatamente o resultado da fase 1;
  - a Data de referência e a conferência de soma não mudam com Retornos na pasta.
- **Ponto 2: a análise de impacto.** Sobre a amostra de julho e sobre o gerador sintético da fase 1, com semente fixa e Parecerista falso:
  - Adesão de 0% dá "depois" igual ao "antes";
  - a Fila em quantidade e em valor nunca aumenta quando a Adesão ou as ondas aumentam;
  - com 100% de Adesão e todos migrados, todo Crédito com Título conhecido e valor permitido chega identificado;
  - a soma do dinheiro do "depois" é igual à do "antes" em todo cenário;
  - no sintético, nenhum item da Lista do "depois" diverge do gabarito;
  - o Ranking de migração não contém os três motivos excluídos.

  Os números esperados de julho vivem só na fixture do teste, nunca no código de produção, como na fase 1.
- **Ponto 3: contrato da Porta de cobrança.** Um teste de contrato que qualquer adaptador precisa passar, rodado hoje contra o simulado: emitir duas vezes não duplica; identificadores únicos e no formato; os arquivos trazidos são aceitos pelos adaptadores de Retorno; mesma semente gera os mesmos arquivos. Testes próprios do simulador: proporções respeitadas dentro de uma tolerância em volume; nenhum Pix com txid com valor diferente da cobrança; valor a menos com identificador só em boleto parcial autorizado.
- Emissão é testada pela análise de impacto e por um cenário ponta a ponta: emitir, simular por proporções, conciliar, e conferir contra o gabarito do simulador.
- Prior art: os testes da fase 1 (ponto de teste da execução, Parecerista falso, gerador sintético com gabarito). pytest como runner.

## Out of Scope

- Integração com banco ou PSP real (OAuth, mTLS, credenciais, webhook). O adaptador real da Porta de cobrança fica para quando existir o sistema.
- Conta virtual por Franqueado e Pix Automático para royalty: só no README.
- Arquivo de remessa CNAB, CNAB 400 e variações de banco sobre o CNAB 240.
- Geração de BR Code, imagem de QR, boleto em PDF e envio da cobrança ao Franqueado.
- Cancelamento ou reemissão de cobrança quando o Título muda de valor ou é baixado; o motor trata a divergência pela regra de valor e a cobrança antiga continua válida no vínculo.
- Emissão para Títulos já vencidos.
- Qualquer mudança nas regras, saídas ou interfaces da fase 1, inclusive novas abas no workbook diário. A única exceção é aditiva: a página de impacto na tela local e o acesso a ela.
- Qualquer escrita no Protheus ou no Omie.

## Further Notes

- **Separação das fases.** A spec da fase 1 é `.scratch/conciliacao-fase1/spec.md`; esta só depende dela e não a altera. As issues da fase 2 vivem em `.scratch/conciliacao-fase2/issues/`, numeradas do 01, e a primeira é bloqueada pela conclusão da fase 1.
- **Pesquisa das specs.** API Pix do Banco Central (`github.com/bacen/pix-api`, OpenAPI 3.0, v2.10.0): `cobv` com multa, juros e devedor por CNPJ; txid do recebedor com 26 a 35 caracteres; `/pix` com `endToEndId`, `txid`, `valor` e `componentesValor`. Retorno CNAB 240 FEBRABAN (leiaute v10.3, por exemplo publicado pelo Banrisul): Segmento T com nosso número, Segmento U com acréscimos, valor pago e data do crédito; pagamento parcial autorizado no campo 42.3P da remessa.
- **Ajuste em relação ao rascunho.** A decisão 13 de `docs/fase2-decisoes.md` previa gerar os pagamentos do sintético por proporções. Aqui a análise de impacto usa o mesmo método contrafactual nos dois conjuntos (julho e sintético), com o gabarito do gerador como fonte da verdade no sintético, para que as duas comparações sejam iguais. O Plano por proporções fica para o fluxo ponta a ponta e para demonstrar as imperfeições.
- **Limite da análise de julho.** Sem decisões confirmadas da Analista, a fonte da verdade de julho são as Propostas e sugestões do "antes". O relatório deixa isso explícito na aba Premissas.
- **Pontos abertos herdados da fase 1.** Juros e tolerância do Encargo (premissa: multa de 2%, juros parametrizáveis); layouts dos outros 3 bancos, que também valem para os Retornos.
- **Padrões de configuração.** Faixa de Adesão de 50%, 80% e 95%; tamanho da onda de 10 Franqueados. Os dois são ajustáveis.
