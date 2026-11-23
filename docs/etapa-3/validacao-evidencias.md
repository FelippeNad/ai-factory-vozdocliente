# Validação da Etapa 3 — evidências e limites

**Data:** 23/11/2026 · **Ambiente:** site Railway + workflow n8n **DEV** + Airtable DEV + Slack DEV.

| Teste | Resultado observado | Evidência / ressalva |
| --- | --- | --- |
| Disponibilidade do site e login | Site aberto com senha, dashboard exibido | Tirar captura sem senha/tokens. Não há prova de 24h de uptime. |
| Classificação positiva via site | `Positivo · Produto · 5/5` | ID: `ETAPA3-DEMO-1795471550245-E1F38E`; site só confirmou após consulta ao Airtable DEV. |
| Alerta de avaliação negativa | Usuário confirmou chegada ao Slack DEV | Salvar captura sem nomes, textos pessoais, tokens, IDs sensíveis. |
| Deduplicação com ID repetido | Duas requisições aceitas; segunda execução encerrou antes de `LLM DEV` | ID `ETAPA3-DUP-d96c520aecc2`; conferir separadamente que há apenas uma linha Airtable com o ID. |
| Webhook sem `X-Demo-Key` | **HTTP 403**; usuário confirmou ausência de execução no n8n | Bloqueio de requisição não autenticada. Conferir também ausência do ID de teste no Airtable, se necessário. |
| Sanitização PII | Implementação/testes existentes da Etapa 2 | Não afirmar teste específico dessa rodada. |

## Capturas recomendadas

1. Dashboard com cards/gráficos e URL visível.
2. Resultado positivo com ID sintético.
3. Resultado negativo e alerta recebido no Slack DEV.
4. Execução de duplicata no n8n encerrada em `Já existe? DEV`, sem passagem pelo LLM.
5. Terminal PowerShell com HTTP 403 sem exibir segredos.
6. Benchmark DEV publicado em `docs/evidencias/benchmark-dev-real.html`.

Não registrar em vídeo a senha de login, token Airtable, chave `X-Demo-Key`, credenciais OpenAI ou textos reais. O n8n pode mostrar detalhes de execução sensíveis: ocultar painéis de credenciais e conteúdo original.

## Critérios de interpretação

- `Workflow was started` é ACK HTTP, **não garante** persistência.
- `GET /health` só comprova que o servidor web está respondendo.
- Dashboard DEV mostra recorte de até 100 avaliações, não o volume total de produção.
- Benchmark de 15 envios por versão não representa distribuição real de avaliações.
- Execução duplicada que não chamou LLM comprova desvio do fluxo, mas não comprova sozinha unicidade de persistência sob concorrência.
