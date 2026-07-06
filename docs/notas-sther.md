# Notas da Sther — o que eu queria ter resolvido

Oi, sou eu. Anotando do jeito que tá na minha cabeça antes de eu esquecer. Não tá organizado, desculpa. Ordem mais ou menos de urgência.

## 🔴 Crítico

- **API key da OpenAI é a MINHA pessoal.** Tá como credencial nomeada nos dois workflows (Make e n8n). Sai uns **US$ 12/mês** do meu cartão. Quando minha conta de estudante expirar eu vou **revogar** a chave — aí o fluxo para. Gera uma chave da conta corporativa e troca **antes disso**.

- **Scheduler / conexão no meu espaço pessoal Make.** A Letícia desligou o automático quando eu saí pra não estourar minha quota. Hoje roda **manual** (alguém clica "Run once"). Migrar pra conta corporativa não é trivial — o Make não migra workspace, vocês vão reimportar o blueprint e reconfigurar as Connections na mão.

- **Sem error handling, em lugar nenhum.** Se o LLM responde algo que não é JSON (acontece de vez em quando, ele "explica" a resposta), o parse quebra e o fluxo **morre calado**. Já perdi review assim e só descobri dias depois. Precisa de try/catch + uma fila de falhas (DLQ) ou pelo menos um alerta.

## 🟡 Importante

- **Sem deduplicação.** A app store às vezes reenvia o mesmo review (mesmo `review_id`), e o form de feedback aceita duplo-submit. Resultado: linha duplicada no Airtable e, se for negativo, **dois alertas no Slack** pro mesmo caso. O time já reclamou disso. Precisa checar `review_id` antes de gravar (ou unique no Airtable, mas o Airtable não força unique de verdade).

- **Matching de tema/sentimento é por string exata.** A rota do negativo compara `sentiment == "negativo"`. Se o modelo responder `"Negativo"`, `"negativa"` ou em inglês, **não dispara o Slack** e ninguém vê. No n8n eu botei `.toLowerCase().trim()` de gambiarra, mas não valido o `theme` contra a lista permitida (entrega/produto/atendimento/preco/app_bug) — se vier `"frete"` vai gravar `"frete"` e bagunçar os relatórios.

- **As Connections não exportam no blueprint do Make.** Tanto OpenAI quanto Airtable e Slack: o JSON sai sem credencial. Tem que recriar. (No n8n é igual — as credentials saem só com o nome.)

## 🟢 Nice to have (não cheguei a fazer)

- **Rastreio de custo por review.** Não gravo tokens nem custo. Queria um campo `cost_usd` no Airtable e um total mensal. Sem isso a gente não sabe quanto custa por loja.
- **Mapa LGPD.** As reviews vêm com **nome do cliente** e às vezes a pessoa escreve telefone ou número de pedido no texto livre — e isso vai inteiro pro OpenAI (EUA) e pro Airtable. Levantei a bandeira pro jurídico, não responderam. Precisa: base legal, anonimização do texto antes do prompt, e política de retenção.
- **Dashboard.** Volume por tema, % de negativos, tempo até resposta. Nem comecei.
- **Hardening do n8n pra produção (TLS, exposição, credenciais).** O mirror local já usa conta de dono e porta só no loopback; produção precisa do resto.

## Sobre o LLM

Uso um modelo GPT pequeno da OpenAI com `temperature 0.1` e `response_format json_object`. Funciona bem pra classificar. Se quiserem testar a **Anthropic (Claude)**, dá — é trocar o endpoint/módulo e ajustar o parsing (Claude devolve em `content[0].text`). O prompt já força JSON então migra fácil. Confiram preço atual antes.

Valeu, e desculpa a bagunça. 💛
— Sther
