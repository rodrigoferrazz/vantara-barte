# 04: Calendário de dias úteis e Encargo

**What to build:** Atraso e Encargo passam a ser calculados pelo Vencimento efetivo (próximo dia útil quando o vencimento cai em fim de semana ou feriado bancário nacional). Multa, juros pro rata e tolerância ficam em configuração (multa padrão de 2%). Pagamento dentro do Encargo vai para a Lista com principal e Encargo separados; atraso pago só pelo valor original segue normal com aviso de Encargo não pago; Diferença a menor e Valor a maior vão para a Fila com Motivo 'valor não fecha'.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Vencimento em sábado, domingo ou feriado bancário nacional é prorrogado para o próximo dia útil
- [ ] Pagamento até o Vencimento efetivo não tem Encargo
- [ ] Pagamento atrasado dentro de multa + juros + tolerância vai para a Lista com principal e Encargo na explicação
- [ ] Pagamento atrasado só com o valor original vai para a Lista com a nota de Encargo não pago
- [ ] Valor abaixo do Título vai para a Fila como 'valor não fecha'; valor acima do Título + Encargo também
- [ ] Parâmetros de Encargo alteráveis por configuração sem mudar código

Spec: `.scratch/conciliacao-fase1/spec.md`
