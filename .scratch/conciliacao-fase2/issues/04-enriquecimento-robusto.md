# 04: Enriquecimento robusto

**What to build:** A ligação entre Retorno de cobrança e Crédito aguenta o volume real: dois Franqueados pagando o mesmo valor no mesmo dia são separados pelo pagador, Extrato atrasado não perde Retorno e arquivo ruim não derruba a execução.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Com mais de um Crédito candidato, desempata pelo CNPJ do pagador no histórico ou por Nome por prefixo entre pagador e histórico
- [ ] Empate que persiste, ou nenhum candidato, não enriquece; o Crédito segue o caminho da fase 1
- [ ] Retorno sem Crédito aparece no Resumo e é ligado quando o Extrato chega numa execução seguinte
- [ ] Reimportar o mesmo Retorno não duplica (chave: `endToEndId` no Pix, nosso número + data de ocorrência no boleto)
- [ ] Arquivo de Retorno com layout estranho é recusado sozinho com motivo, e o resto segue (ADR 0005)
- [ ] Retornos na pasta não mudam a Data de referência nem a conferência de soma
