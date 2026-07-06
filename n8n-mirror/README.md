# n8n-mirror — VozDoCliente Review Router

Espelho **rodável** do cenário Make.com. O Make não roda local, então pra vocês testarem o fluxo de verdade eu refiz os mesmos passos no n8n (self-host via Docker). É o mesmo pipeline:

```
Webhook /review → OpenAI (sentiment + theme) → Parse+Merge → Airtable Create → IF negativo? → Slack #cx-alertas
```

> Os nodes de OpenAI, Airtable e Slack aqui são **HTTP Request genéricos** (batem direto na API REST), não os nodes nativos. Foi de propósito: deixa explícito o request e fica fácil de inspecionar/mockar. Em produção vocês podem trocar pelos nodes nativos.

## Subir o n8n

```bash
cd n8n-mirror
cp ../.env.example .env   # preencha AIRTABLE_BASE_ID (o resto é credencial da UI)
docker compose up
```

Abre em http://localhost:5678 — login `admin` / `admin` (troquem isso, é dívida herdada, ver README raiz).

## Importar o workflow

1. No menu do n8n: **Workflows → Import from File**.
2. Escolha `workflows/vozdocliente-router-v0.json`.
3. O workflow vem com **3 credenciais por nome** (não exportam valores — igual o Make):
   - `OpenAI Sther (pessoal - ROTACIONAR)` → tipo **Header Auth**, header `Authorization`, valor `Bearer sk-...`
   - `Airtable PAT Sther (base corporativa)` → tipo **Header Auth**, header `Authorization`, valor `Bearer patXXXX...`
   - `Slack VozDoCliente Bot` → tipo **Header Auth**, header `Authorization`, valor `Bearer xoxb-...`
4. Abra cada node HTTP, recrie/aponte a credencial Header Auth correspondente.
5. Clique **Active** no canto superior direito (senão o webhook responde 404).

## Teste manual (sem app real)

O fluxo recebe um POST no webhook. Veja `../docs/exemplos-reviews.md` para mais payloads.

```bash
curl -X POST http://localhost:5678/webhook/review \
  -H "Content-Type: application/json" \
  -d '{
    "review_id": "R-1001",
    "customer_name": "Marina Souza",
    "source": "app-store",
    "rating": 1,
    "review_text": "Comprei e o produto chegou quebrado, ninguem do SAC responde. Pessimo."
  }'
```

Esperado:
- `200` no curl.
- 1 linha nova na tabela `Reviews` do Airtable.
- Como `sentiment` deve sair `negativo`, **uma mensagem no canal `#cx-alertas`** do Slack.

Para um review positivo (`"review_text": "App rapido e entrega no prazo, recomendo!"`), grava no Airtable mas **não** dispara Slack — o IF barra.

## Atenção: isto NÃO sobe sozinho aqui

O enunciado/CI **não** roda `docker compose up`. Os testes automatizados (validador de JSON + teste de lógica com LLM mockado) estão em `../tests/` e rodam sem subir o n8n. O passo Docker acima é pra vocês rodarem na máquina de vocês.

## Diferenças vs. Make

| Aspecto | Make | n8n mirror |
| --- | --- | --- |
| Roteamento do negativo | Router + filter na rota | node `IF` (saída true → Slack) |
| Parse do JSON do LLM | módulo `JSON > Parse JSON` | node `Code` (Parse + Merge) |
| Chamadas de API | módulos nativos (OpenAI/Airtable/Slack) | HTTP Request genérico |
| Credenciais | Connections (não exportam) | Credentials Header Auth (não exportam) |
