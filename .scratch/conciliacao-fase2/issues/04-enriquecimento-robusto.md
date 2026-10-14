# 04: Enriquecimento robusto

**What to build:** A ligação entre Retorno de cobrança e Crédito aguenta o volume real: dois Franqueados pagando o mesmo valor no mesmo dia são separados pelo pagador, Extrato atrasado não perde Retorno e arquivo ruim não derruba a execução.

**Blocked by:** 01

**Status:** ready-for-human

- [x] Com mais de um Crédito candidato, desempata pelo CNPJ do pagador no histórico ou por Nome por prefixo entre pagador e histórico
- [x] Empate que persiste, ou nenhum candidato, não enriquece; o Crédito segue o caminho da fase 1
- [x] Retorno sem Crédito aparece no Resumo e é ligado quando o Extrato chega numa execução seguinte
- [x] Reimportar o mesmo Retorno não duplica (chave: `endToEndId` no Pix, nosso número + data de ocorrência no boleto)
- [x] Arquivo de Retorno com layout estranho é recusado sozinho com motivo, e o resto segue (ADR 0005)
- [x] Retornos na pasta não mudam a Data de referência nem a conferência de soma

## Comments

- Implementado. Testes em `tests/test_enriquecimento_robusto.py`; decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 04").
- Status `ready-for-human`, como nos tickets 01 a 03: o `triage-labels.md` não tem papel de concluído.
- Já vinham do ticket 01 (não refeito): Retornos guardados com chave natural, retentativa dos sem Crédito e Retorno fora da conferência de soma e da Data de referência. Do ticket 03: recusa por arquivo do CNAB 240. Este ticket acrescenta testes para esses critérios.
- Novo: pagador lido nos dois adaptadores (`pagador` do Pix e Segmento T do CNAB), desempate por CNPJ ou CPF no histórico ou Nome por prefixo entre os nomes, e Retornos sem Crédito no Resumo, com o motivo (nenhum Crédito ou empate). Pagador fora do formato recusa o arquivo.
- O desempate vale para os dois lados: empate entre Retornos (dois para um Crédito) também é desfeito pelo pagador ou não enriquece. Desfeito um empate, o que sobra do par é olhado de novo na mesma execução.
- O CPF do pagador também desempata, pelo mesmo princípio do CNPJ, embora o ticket só cite CNPJ.
- Colunas novas na tabela de Retornos e tabela nova `retornos_sem_credito`, sem migração (banco local recriado).
- Ponto em aberto: Retorno cujo Crédito já foi encerrado por decisão da Analista antes de o Retorno chegar fica sem Crédito para sempre e aparece em todo Resumo; a spec não diz quando parar de retentar.
