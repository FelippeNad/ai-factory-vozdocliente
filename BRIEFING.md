# Briefing Oficial — VozDoCliente

**Empresa:** VozDoCliente Tecnologia Ltda. (fictícia)
**Missão:** Nenhuma reclamação sem resposta.
**O que fazemos:** SaaS de Customer Experience (CX) para varejo e marketplaces — centralizamos avaliações, feedbacks e reclamações de múltiplos canais e ajudamos os times a responder rápido.
**Tamanho:** ~140 colaboradores, sede em Florianópolis (SC), ~320 contas de clientes B2B (lojas e marketplaces).
**Área:** Squad CX Ops & Automação.

---

## Sua nova função

Olá, e bem-vindo(a) à VozDoCliente!

Eu sou a **Letícia Prado**, head de CX Ops. Você está assumindo a vaga de **AI Automation Engineer** dentro do squad CX Ops & Automação — o time que mantém os fluxos que conectam o feedback do cliente final às pessoas certas dentro das lojas que são nossas clientes.

A vaga é nova. Antes de você, quem tocava esses fluxos era a **Sther Ramos**, nossa estagiária de CX Ops (por cerca de seis meses, até o início deste ano). A Sther foi excelente, mas o estágio dela acabou e ela voltou pro último ano da faculdade. O protótipo que ela construiu ficou órfão — e é justamente o que mais usamos hoje.

---

## Contexto do problema

Nossos clientes recebem **muita** avaliação: app stores, formulários de pós-compra, Reclame Aqui, marketplaces. O problema nunca foi receber — foi **não deixar reclamação sem resposta**. Avaliação negativa que fica 3 dias sem ninguém ver vira nota 1, vira print no Twitter, vira churn.

A Sther atacou isso com um **roteador de avaliações**: quando chega uma review nova (via webhook), um LLM classifica **sentimento** e **tema**, grava tudo no Airtable e, se for **negativa**, dispara um alerta no Slack pro time responsável. Simples e eficaz — o time de CX passou a responder negativas no mesmo dia.

Funciona. Mas nunca saiu de um protótipo montado no Make.com, na conta pessoal da Sther.

---

## Estado atual do protótipo

- **Stack C — no-code:** Make.com (cenário em produção desde o fim do ano passado).
- Espelho rodável em **n8n** (Docker) pra vocês testarem local — Make não roda local.
- Cenário no **espaço pessoal** da Sther; scheduler em modo **manual**.
- **API key de LLM pessoal** da Sther (sai do cartão dela).
- Sem error handling, sem deduplicação, sem rastreio de custo.
- LGPD **não endereçada** — reviews carregam nome do cliente.
- Documentação esparsa em `docs/notas-sther.md`.

Considere isto **dívida técnica herdada**. Não jogue fora — refatore. A lista completa está no `README.md`, seção "Dívida técnica herdada".

---

## Expectativas em 12 semanas

1. **Semana 3 — Auditoria e baseline:** mapear o fluxo real, subir o espelho n8n localmente, documentar arquitetura e custos atuais, plano de evolução.
2. **Semana 6 — Hardening:** error handling, deduplicação por `review_id`, validação do output do LLM contra a lista de temas, logging e rastreio de custo por execução.
3. **Semana 9 — Migração e staging:** cenário migrado pra conta corporativa, credenciais corporativas, ambiente de staging com monitoramento básico e conformidade LGPD documentada.
4. **Semana 12 — Piloto em produção:** rollout controlado com 3 clientes-piloto, SLA de resposta a negativas e dashboard de acompanhamento (volume, % negativo por tema, tempo até resposta).

---

## Restrições

- **Orçamento de infra/IA:** **US$ 100/mês** no piloto (LLM + hosting do n8n/Make + Airtable).
- **Provedores permitidos:** OpenAI, Anthropic, Google (modelos via API). Automação em Make.com ou n8n (self-host). Hospedagem em Render, Railway, Fly.io ou VPS própria.
- **LGPD:** avaliação contém **dado pessoal** de cliente final (nome, às vezes telefone/nº de pedido no texto). Nada de PII em prompt sem definição de base legal e anonimização quando aplicável. Retenção de logs: no máximo 90 dias. Os dados de cliente final pertencem às lojas que são nossas clientes — atenção redobrada.
- **Segurança:** nada de credencial pessoal. Tudo em conta corporativa, auditável.
- **Idioma:** PT-BR no produto e na comunicação com o time. Documentação técnica pode ser bilíngue.

Conta com a gente. Qualquer dúvida, me chama.

— Letícia Prado
Head de CX Ops, VozDoCliente
