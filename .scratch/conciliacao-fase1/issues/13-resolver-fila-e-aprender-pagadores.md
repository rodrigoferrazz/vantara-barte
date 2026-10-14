# 13: Resolver a Fila pelo Excel e aprender Pagadores conhecidos

**What to build:** A Analista resolve itens da Fila no workbook: escolhe o(s) Título(s), classifica Crédito sem título em aberto (antecipação, devolução, erro), marca Conciliado fora com Franqueado e referência livre, ou decide Possível duplicidade ('mesma dívida' escolhendo o Título oficial, ou 'dívidas distintas'). Confirmar um match que identificou o pagador por nome cria um Pagador conhecido.

**Blocked by:** 06, 12

**Status:** ready-for-agent

- [x] Item da Fila resolvido com Título escolhido sai da Fila e segue o mesmo caminho de uma confirmação da Lista
- [x] Uma confirmação por nome cria Pagador conhecido; o próximo Crédito com o mesmo histórico e Valor único vai para a Lista
- [x] Mesmo histórico confirmado para outro Franqueado desativa o Pagador conhecido e o histórico volta sempre para a Fila
- [x] Confirmações por valor ou soma não criam regra
- [x] 'Mesma dívida' tira o outro Título da cobrança para sempre e o lista para cancelamento na origem
- [x] Conciliado fora tira o Crédito da Fila e mantém a contagem no relatório de causa raiz
- [x] Decisões registram modelo e versão do prompt quando o item teve parecer da IA

Spec: `.scratch/conciliacao-fase1/spec.md`
