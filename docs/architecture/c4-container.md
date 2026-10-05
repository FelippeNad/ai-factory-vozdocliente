# C4 — Nível 2: Contêineres do Sistema

## Objetivo

Detalhar os principais componentes técnicos do VozDoCliente e as relações entre eles.

```mermaid
C4Container
title VozDoCliente — Diagrama de Contêineres

Person(cx, "Equipe de CX", "Consulta resultados e recebe alertas")

System_Boundary(sistema, "VozDoCliente") {

    Container(webhook, "Webhook", "n8n", "Recebe avaliações em formato JSON")

    Container(orchestrator, "Workflow de processamento", "n8n", "Orquestra classificação, validação, persistência e roteamento")

    Container(llmAdapter, "Integração com LLM", "HTTP Request / API compatível com OpenAI", "Envia o texto da avaliação para classificação")

    Container(parser, "Parse e validação", "n8n Code Node", "Interpreta e normaliza a resposta do modelo")

    Container(router, "Roteamento", "n8n IF Node", "Identifica avaliações negativas")
}

System_Ext(llm, "LLM", "Qwen3-4B em desenvolvimento ou API externa em produção")
System_Ext(airtable, "Airtable", "Persistência das avaliações processadas")
System_Ext(slack, "Slack", "Canal de alertas da equipe de CX")
System_Ext(source, "Canal de entrada", "Sistema que envia avaliações")

Rel(source, webhook, "POST /review", "HTTPS/JSON")
Rel(webhook, orchestrator, "Dispara workflow")
Rel(orchestrator, llmAdapter, "Solicita classificação")
Rel(llmAdapter, llm, "Prompt + review_text", "HTTP/JSON")
Rel(llm, llmAdapter, "sentiment + theme", "JSON")
Rel(llmAdapter, parser, "Resposta do modelo")
Rel(parser, orchestrator, "Dados normalizados")
Rel(orchestrator, airtable, "Cria registro", "REST API")
Rel(orchestrator, router, "Avaliação processada")
Rel(router, slack, "Envia alerta se negativo", "REST API")
Rel(cx, airtable, "Consulta resultados")
Rel(cx, slack, "Recebe alertas")