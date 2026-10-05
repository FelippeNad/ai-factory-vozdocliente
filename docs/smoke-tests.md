# Smoke Tests — VozDoCliente

## Objetivo

Validar o funcionamento do fluxo principal do VozDoCliente no ambiente de produção publicado no Railway.

Os testes foram executados utilizando a URL pública de produção do webhook, sem necessidade de iniciar manualmente o workflow pelo editor do n8n.

## Ambiente testado

- **Ambiente:** Produção
- **Orquestrador:** n8n
- **Hospedagem:** Railway
- **LLM:** OpenAI
- **Persistência:** Airtable PROD
- **Notificações:** Slack PROD
- **Endpoint:**

```text
POST https://n8n-production-7813.up.railway.app/webhook/review
```

## Smoke Test 1 — Avaliação negativa

### Objetivo

Validar o processamento completo de uma avaliação negativa, incluindo persistência no Airtable e envio de alerta para o Slack.

### Payload

```json
{
  "review_id": "SMOKE-PROD-NEG-001",
  "customer_name": "Cliente Teste",
  "source": "app-store",
  "rating": 1,
  "review_text": "O produto chegou quebrado e o atendimento nao respondeu."
}
```

### Resultado esperado

1. O webhook recebe a avaliação.
2. O LLM classifica a avaliação.
3. A classificação passa pela validação.
4. A busca de deduplicação não encontra o `review_id`.
5. Um novo registro é criado no Airtable PROD.
6. O sentimento é identificado como negativo.
7. Um alerta é enviado ao Slack PROD.

### Resultado obtido

**PASSOU**

- Avaliação processada com sucesso.
- Registro criado no Airtable PROD.
- Sentimento classificado como `negativo`.
- Alerta enviado com sucesso ao Slack PROD.

---

## Smoke Test 2 — Avaliação positiva

### Objetivo

Validar que uma avaliação positiva seja persistida normalmente, mas não gere alerta no Slack.

### Payload

```json
{
  "review_id": "SMOKE-PROD-POS-001",
  "customer_name": "Cliente Teste",
  "source": "app-store",
  "rating": 5,
  "review_text": "Produto excelente, entrega rapida e estou muito satisfeito."
}
```

### Resultado esperado

1. O webhook recebe a avaliação.
2. O LLM classifica a avaliação.
3. A busca de deduplicação não encontra o `review_id`.
4. Um novo registro é criado no Airtable PROD.
5. O sentimento é identificado como positivo.
6. Nenhum alerta é enviado ao Slack.

### Resultado obtido

**PASSOU**

- Avaliação processada com sucesso.
- Registro criado no Airtable PROD.
- Sentimento classificado como `positivo`.
- Nenhum alerta foi enviado ao Slack, conforme esperado.

---

## Smoke Test 3 — Avaliação duplicada

### Objetivo

Validar a proteção contra processamento duplicado utilizando o campo `review_id`.

### Payload

Foi enviado novamente o mesmo payload do Smoke Test 1:

```json
{
  "review_id": "SMOKE-PROD-NEG-001",
  "customer_name": "Cliente Teste",
  "source": "app-store",
  "rating": 1,
  "review_text": "O produto chegou quebrado e o atendimento nao respondeu."
}
```

### Resultado esperado

1. O webhook recebe novamente a avaliação.
2. O fluxo consulta o Airtable pelo `review_id`.
3. O registro existente é encontrado.
4. A condição de deduplicação é avaliada como verdadeira.
5. Nenhum novo registro é criado.
6. Nenhum novo alerta é enviado ao Slack.

### Resultado obtido

**PASSOU**

- O `review_id` existente foi identificado.
- O fluxo foi interrompido na etapa de deduplicação.
- Nenhum registro duplicado foi criado no Airtable PROD.
- Nenhum segundo alerta foi enviado ao Slack PROD.

---

## Resultado geral

| Teste | Resultado |
| --- | --- |
| Avaliação negativa | PASSOU |
| Avaliação positiva | PASSOU |
| Avaliação duplicada | PASSOU |

**Resultado final: 3 de 3 smoke tests aprovados.**

Os testes demonstram que o endpoint público de produção está funcional e que o fluxo principal executa corretamente classificação, persistência, roteamento de alertas e deduplicação.

## Evidências

A execução dos smoke tests em produção está registrada na imagem:

`docs/evidencias/smoke-tests.png`