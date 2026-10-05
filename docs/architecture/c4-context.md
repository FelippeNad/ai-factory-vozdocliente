# Arquitetura C4 — Nível 1: Contexto do Sistema

## Visão geral

O VozDoCliente automatiza o processamento de avaliações de clientes. O sistema recebe uma avaliação, utiliza um modelo de linguagem para classificar seu sentimento e tema, registra o resultado e gera um alerta quando identifica uma avaliação negativa.

```mermaid
flowchart TB

    CX["👤 Equipe de CX<br/>Acompanha avaliações e trata reclamações"]

    SOURCE["Canal de avaliações<br/>Origem das avaliações"]

    VDC["VozDoCliente<br/><br/>Classifica avaliações,<br/>registra resultados e<br/>gera alertas"]

    LLM["Serviço de LLM<br/>Classificação de sentimento e tema"]

    AIR["Airtable<br/>Armazenamento dos resultados"]

    SLACK["Slack<br/>Alertas de avaliações negativas"]

    SOURCE -->|"Envia avaliação"| VDC

    VDC -->|"Solicita classificação"| LLM
    LLM -->|"Retorna sentimento e tema"| VDC

    VDC -->|"Registra resultado"| AIR
    VDC -->|"Envia alerta se negativo"| SLACK

    VDC -->|"Disponibiliza resultados e alertas"| CX
```

## Elementos

### Equipe de CX

Usuário operacional do VozDoCliente. Acompanha avaliações processadas e atua sobre casos que demandam atendimento.

### Canal de avaliações

Representa o sistema ou serviço responsável por enviar avaliações de clientes ao VozDoCliente.

### VozDoCliente

Sistema responsável por coordenar o processamento das avaliações, classificação, persistência e geração de alertas.

### Serviço de LLM

Sistema externo responsável por classificar o texto da avaliação por sentimento e tema.

### Airtable

Serviço externo utilizado para persistir avaliações processadas e suas classificações.

### Slack

Serviço externo utilizado para entregar alertas de avaliações negativas à equipe de CX.