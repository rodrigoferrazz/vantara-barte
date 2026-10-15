# 01: Três visões da tela local

**What to build:** A tela local passa a ter três visões com navegação no topo, uma por usuário e sem login. A Analista de conciliação envia os arquivos e concilia pela tela, sem terminal; o time de cobrança vê só quem cobrar e o que não cobrar ainda; a gestão lê em dois minutos o resolvido sozinho, a causa raiz e o impacto da fase 2. Sem build de frontend nem recurso externo, funcionando offline e em tela de notebook sem rolar para o lado.

**Status:** ready-for-human

- [x] Navegação no topo com Conciliação, Cobrança e Gestão
- [x] Conciliação: envio de Extratos e exportações do Protheus e do Omie e botão Conciliar, que roda a mesma execução do comando `conciliar` e aplica as decisões da tela
- [x] Arquivos não reconhecidos aparecem com o motivo
- [x] Resumo simples (quanto confirmar e quanto resolver) e situação da IA
- [x] Lista de baixa em linhas curtas (Franqueado, valor, Título e por quê), com Confirmar todos e rejeição com motivo
- [x] Fila de exceções em cartões: Motivo em linguagem simples, Título sugerido, parecer da IA destacado e os botões das decisões existentes; explicação completa em "ver detalhes"
- [x] Lista do que baixar manualmente no ERP e botão para baixar o Excel, gerado igual
- [x] Cobrança: Franqueado, Título, valor, vencimento e dias de atraso; Títulos em análise separados, com motivo curto
- [x] Gestão: resolvido sozinho, causa raiz em gráfico, antes e depois por Adesão, Ondas, Ranking e Premissas em "ver detalhes"
- [x] Cores de estado (confirmado, pendente, problema), números grandes nos resumos, sem script e sem recurso externo

## Comments

- Implementado. Visões em `pagina_da_analista.py`, `pagina_da_cobranca.py` e `pagina_da_gestao.py`, sobre a base de `pagina.py`; rotas em `tela.py`; execução compartilhada com o comando em `cli.conciliar_a_pasta`. Decisões em `docs/decisoes-implementacao.md` ("Três visões da tela").
- `/impacto` deixou de existir; o conteúdo foi para `/gestao` com os mesmos identificadores, e os testes da página de impacto só mudaram a rota e a leitura do texto das barras (que ganharam `<title>`).
- Os testes da tela da fase 1 foram reescritos para a nova estrutura, mantendo os comportamentos (mesmos totais do workbook, decisões pela tela, conflito, recusa) e ganhando os de envio, conciliação, Excel, cobrança e gestão.
