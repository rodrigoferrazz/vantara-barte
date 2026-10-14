# 03: Boleto da plataforma e retorno CNAB 240

**What to build:** Título sem nosso número no Protheus (por exemplo, do Omie) passa a receber boleto e Pix na emissão; Título com nosso número do Protheus continua só com Pix. O retorno CNAB 240 FEBRABAN na pasta de entrada enriquece o Crédito, e o boleto da plataforma é resolvido como um boleto do Protheus.

**Blocked by:** 01

**Status:** ready-for-human

- [x] Nosso número gerado dentro da faixa configurada do beneficiário por conta, único, nunca reaproveitado
- [x] Nenhum Título fica com dois boletos registrados
- [x] Adaptador CNAB 240 lê cabeçalhos de arquivo e lote e Segmentos T e U; só movimento de liquidação vira Retorno, os demais são ignorados
- [x] Boleto da plataforma liquidado com nosso número no Extrato vai para a Lista com a mesma regra de valor do nosso número da fase 1
- [x] Parcial de boleto com pagamento parcial autorizado vai para a Fila como Diferença a menor, com o Título apontado
- [ ] Multa e juros do Segmento U aparecem separados na explicação (o Segmento U da FEBRABAN não separa: a explicação mostra principal e acréscimos, ver Comments)
- [x] A regra de nosso número do Protheus da fase 1 continua igual

## Comments

- Implementado. Testes em `tests/test_boleto_da_plataforma.py`; decisões em `docs/decisoes-implementacao.md` (seções "Fase 2, ticket 03"). Escritor de retorno CNAB 240 e configuração com faixa em `tests/arquivos.py`; `[migracao.boleto]` e a `[[contas]]` do retorno CNAB ficam comentadas no `conciliacao.toml`.
- Status `ready-for-human`, como nos tickets 01 e 02: o `triage-labels.md` não tem papel de concluído.
- Critério não atendido como escrito: o Segmento U do CNAB 240 FEBRABAN tem um campo só para juros, multa e encargos ("acréscimos"). A explicação mostra principal e acréscimos; separar multa e juros seria inventar a divisão. Se algum banco separar, entra no adaptador dele.
- A faixa de nosso número é de uma conta beneficiária só (`[migracao.boleto]`); a spec não diz como escolher a conta de cada Título se houver mais de uma. Sem a faixa, a emissão segue só com Pix.
- "Nenhum Título com dois boletos" vale na emissão: Título com nosso número do Protheus não recebe boleto da plataforma, nem quando o nosso número aparece antes do envio. Se ele aparecer no Protheus depois de o boleto da plataforma ser enviado, ficam dois, porque cancelar cobrança está fora do escopo da spec.
- Pagamento parcial autorizado não é distinguido: o retorno não traz essa marca, e valor abaixo do Título com identificador já vai para a Fila como Diferença a menor apontando o Título.
- Fora do ticket, por coerência: o Retorno CNAB de um boleto do Protheus também enriquece o Crédito (regra da fase 1, evidência "nosso número", com os acréscimos na explicação), e o boleto da plataforma ganha a janela de 2 dias úteis de compensação na Lista de cobrança, como o do Protheus.
- Coluna nova `acrescimos_centavos` na tabela de Retornos, sem migração (banco local recriado).
