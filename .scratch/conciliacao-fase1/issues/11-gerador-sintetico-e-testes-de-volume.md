# 11: Gerador sintético e testes de volume

**What to build:** Um gerador com semente fixa e proporções configuráveis produz exportações Protheus e Omie e Extratos de 4 contas com a mesma bagunça da amostra, em volume real (~1.900 Títulos/mês), e um gabarito com o destino esperado de cada Crédito. Testes de volume rodam a plataforma sobre esses dados.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Mesma semente gera exatamente os mesmos arquivos
- [ ] Arquivos gerados são aceitos pelos adaptadores sem nenhum ajuste
- [ ] Proporções configuráveis de: nome truncado, abreviado e invertido, CNPJ no histórico, soma de Títulos, parcial, multa, Encargo não pago, duplicidade entre sistemas, depósito sem nome, antecipação, débitos
- [ ] Gabarito com destino esperado, Título(s) e Motivo de cada Crédito
- [ ] Teste de volume: nenhum item da Lista de baixa diverge do gabarito
- [ ] Teste de volume: conferência de soma fecha e todo item da Fila tem um único Motivo
- [ ] Execução com ~1.900 Títulos termina em tempo aceitável no MacBook Air M2 com a IA falsa

Spec: `.scratch/conciliacao-fase1/spec.md`
