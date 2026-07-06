# VozDoCliente — Review Router (passagem de bastão da Sther)

Oi! Eu sou a **Sther** 👋 (estagiária de CX Ops por cerca de seis meses, até o início deste ano).

Esse é o roteador de avaliações que eu montei. Quando chega uma review/feedback novo (da loja de apps ou do formulário), o fluxo usa um LLM pra classificar **sentimento** (positivo / neutro / negativo) e **tema** (entrega, produto, atendimento, preço, app/bug), grava no Airtable e, **se for negativa**, dispara um alerta no Slack pro time responsável. A ideia é a missão da casa: **"Nenhuma reclamação sem resposta."**

Tá rodando em **Make.com** desde o fim do ano passado. Como Make não roda local (e você não vai conseguir testar de imediato), eu **espelhei o fluxo no n8n** (em `n8n-mirror/`) pra você conseguir subir num Docker e ver funcionando de verdade.

## O que tem aqui

```
vozdocliente-review-router/
├── README.md                         ← você está aqui
├── BRIEFING.md                       ← carta de onboarding da Letícia (sua gestora)
├── CHANGELOG.md
├── .env.example
├── .gitignore
├── workflows/
│   └── vozdocliente-make-blueprint.json   ← blueprint Make.com (importável)
├── n8n-mirror/                       ← espelho rodável (Docker + n8n)
│   ├── docker-compose.yml
│   ├── README.md
│   └── workflows/vozdocliente-router-v0.json
├── docs/
│   ├── notas-sther.md                ← minhas notas soltas (LEIA)
│   ├── exemplos-reviews.md           ← 10 avaliações de exemplo
│   └── airtable-schema.md
└── tests/
    ├── validate_workflows.py         ← valida os 2 JSONs
    └── test_routing_logic.py         ← teste de lógica com LLM mockado
```

## Pipeline

```
Webhook (review novo)
   → OpenAI: classifica sentiment + theme (JSON)
   → grava no Airtable (sempre)
   → se sentiment == "negativo": Slack #cx-alertas
```

## Rodar — Make.com

O Make não roda local. Pra ver o cenário:

1. Entre no Make.com → **Create a new scenario** → menu `...` → **Import Blueprint**.
2. Suba `workflows/vozdocliente-make-blueprint.json`.
3. O Make importa os módulos, mas **as Connections não vêm no blueprint** (limitação do Make — aprendi do jeito difícil). Você vai reconfigurar na mão:
   - OpenAI (API key)
   - Airtable (PAT + base/tabela)
   - Slack (OAuth do bot)
4. No módulo Webhook, copie a URL gerada e plugue na origem (form de feedback / integração da app store).
5. Ligue o scheduler (hoje tá **manual**, ver dívida técnica).

## Rodar — espelho n8n (recomendado pra testar)

Passo a passo completo em `n8n-mirror/README.md`. Resumo:

```bash
cd n8n-mirror
docker compose up
# abre http://localhost:5678  (1º acesso: cria uma conta de dono — email/senha local)
# Import from File → workflows/vozdocliente-router-v0.json
# recria as 3 credenciais Header Auth, clica Active
```

E testa com:

```bash
curl -X POST http://localhost:5678/webhook/review \
  -H "Content-Type: application/json" \
  -d '{"review_id":"R-1001","customer_name":"Marina Souza","source":"app-store","rating":1,"review_text":"Produto chegou quebrado e o SAC nao responde."}'
```

## Testes (rodam sem Docker)

```bash
python tests/validate_workflows.py     # valida estrutura dos 2 JSONs
python tests/test_routing_logic.py     # lógica de sentiment/theme + alerta, LLM mockado
```

> Os testes **não** chamam API real e **não** sobem o n8n. Mockam o LLM.

## LLM

Hoje uso um modelo **GPT** pequeno da **OpenAI** (barato, rápido o bastante pra classificação). Dá pra trocar por **Anthropic Claude** (ex.: um modelo Haiku) sem mudar o fluxo — só o módulo/endpoint e o parsing da resposta. O prompt já pede JSON, então a migração é tranquila. (Confere preço/modelo atual antes de decidir.)

---

## Dívida técnica herdada

Tô deixando isso documentado de propósito — **não joguei fora, mas também não consegui arrumar**. É o que você herda:

1. **Scheduler/conexão na minha conta pessoal.** O cenário Make tá no meu espaço pessoal e o scheduler tá rodando **manual** porque a Letícia desligou o automático pra não estourar minha quota quando eu saí. Precisa migrar pra conta corporativa VozDoCliente.
2. **API key da OpenAI é minha pessoal.** Tá saindo do meu cartão (uns US$ 12/mês). Vou **revogar** quando minha conta de aluno expirar. Gera uma chave corporativa e troca — tá hardcoded como credencial nomeada nos dois workflows.
3. **Sem error handling.** Se o LLM devolve algo que não é JSON, o node `Parse + Merge` (n8n) / o `JSON Parse` (Make) **quebra e o fluxo morre silencioso**. Já perdi reviews assim e ninguém viu.
4. **Sem deduplicação.** Se a app store reenvia o mesmo review (ou o form dá duplo-submit), processa **duas vezes** e grava linha duplicada no Airtable. Não tem checagem por `review_id`.
5. **Sem rastreio de custo.** Não gravo tokens nem custo por execução. Impossível auditar o gasto de LLM por review hoje.
6. **Sem mapa LGPD.** As reviews **vêm com nome do cliente** (campo `customer_name`) e às vezes a pessoa escreve telefone/pedido no texto livre — e isso vai inteiro pro prompt do OpenAI (EUA) e pro Airtable. Ninguém mapeou base legal / anonimização / retenção.
7. **Matching de tema frágil.** A rota do negativo e os relatórios dependem da string exata do LLM (`negativo`, `entrega`, `app_bug`...). Se o modelo responder com acento diferente, maiúscula, ou um tema fora da lista, **fura silenciosamente**. No n8n eu faço `.toLowerCase().trim()` como gambiarra, mas não valido contra a lista permitida.

Detalhes e mais contexto em `docs/notas-sther.md`.

Boa sorte! O fluxo é simples e o time de CX já depende dele. Qualquer coisa me chama. 💛

— Sther
