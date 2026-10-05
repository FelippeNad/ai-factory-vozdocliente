# C4 — Nível 1: Contexto do Sistema

## Objetivo

Representar o VozDoCliente no seu contexto operacional, destacando usuários, sistemas externos e principais integrações.

```mermaid
C4Context
title VozDoCliente — Diagrama de Contexto

Person(cx, "Equipe de CX", "Recebe e trata avaliações de clientes")

System(vozdocliente, "VozDoCliente", "Classifica avaliações por sentimento e tema, persiste os resultados e gera alertas para casos negativos")

System_Ext(canalEntrada, "Canal de entrada", "Envia avaliações ao webhook do sistema")
System_Ext(llm, "Serviço de LLM", "Classifica sentimento e tema")
System_Ext(airtable, "Airtable", "Armazena avaliações processadas")
System_Ext(slack, "Slack", "Recebe alertas de avaliações negativas")

Rel(canalEntrada, vozdocliente, "Envia avaliação", "HTTPS/JSON")
Rel(vozdocliente, llm, "Solicita classificação", "HTTPS/JSON")
Rel(vozdocliente, airtable, "Persiste resultado", "HTTPS/REST")
Rel(vozdocliente, slack, "Envia alerta", "HTTPS/REST")
Rel(cx, airtable, "Consulta avaliações processadas")
Rel(cx, slack, "Recebe e acompanha alertas")
