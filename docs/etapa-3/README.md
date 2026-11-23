# Etapa 3 — VozDoCliente CX | AI Factory / PUCPR

**Entrega:** 23/11/2026 · **Versão da demonstração:** 1.0 · **Branch:** `etapa-3`.

## Aplicação publicada

- **URL:** https://ai-factory-vozdocliente-production.up.railway.app
- **Health:** https://ai-factory-vozdocliente-production.up.railway.app/health
- **Frontend e backend web:** [`../../site/`](../../site/)
- **Workflow DEV:** [`../../n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json`](../../n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json)
- **README técnico do site:** [`../../site/README.md`](../../site/README.md)
- **Briefing:** [`../../BRIEFING.md`](../../BRIEFING.md)

A aplicação possui senha de demonstração: fornecer ao avaliador **somente em campo privado**, sem incluir em commits, vídeo, capturas de tela ou arquivos públicos. O serviço web, a base consultada e o webhook de demonstração usam o **ambiente DEV**. Não confundir o nome do domínio do Railway com uso de dados de produção.

## Entregáveis

- [One-pager executivo](one-pager-executivo.md) — síntese de problema, solução, resultados e riscos.
- [Validação e evidências](validacao-evidencias.md) — verificações realizadas, evidências a capturar e limites.
- Análise crítica de 1–2 páginas — **a seção C deve ser escrita integralmente pelo estudante, sem IA**, conforme o enunciado da atividade. Não incluída como texto gerado neste pacote.
- Pitch em vídeo de 4min30s a 5min30s — ainda deve ser gravado, publicado no YouTube como não listado e incluído na entrega.

## Arquitetura da demonstração

```text
Navegador ─HTTPS/sessão─> Node.js 22 / Railway (site/)
                         ├─ GET /api/reviews ──> Airtable DEV (leitura de metadados)
                         └─ POST /api/submit ──> Webhook n8n DEV (X-Demo-Key)
                                                    │
                                 Sanitização PII -> precheck por review_id
                                                    │
                                    [duplicado] encerra sem LLM
                                    [novo] OpenAI -> validação -> consulta final
                                                     -> Airtable DEV -> Slack DEV (negativos)
                         <── consulta Airtable DEV até confirmar classificação
```

O site mostra um recorte de até 100 registros DEV, e até 20 linhas na tabela. O original da avaliação pode ficar guardado no Airtable DEV, embora o site exiba apenas campos permitidos. Não utilizar dados reais. A resposta inicial do webhook indica apenas recebimento; o site só confirma classificação quando encontra o registro processado.

## Execução local e deploy

Requisito do site: Node.js **22.16.0**, fixado na imagem `node:22.16.0-alpine` em `site/Dockerfile`, sem dependências npm. O n8n e os serviços de desenvolvimento usam as versões especificadas em seus próprios Dockerfiles e Compose. O site roda com `node server.js` dentro da pasta `site`; requer `APP_PASSWORD` (mínimo 10 caracteres) e `SESSION_SECRET` (mínimo 24 caracteres) para iniciar. Sem as integrações, a interface sobe, mas não consegue consultar/classificar.

Para publicar no Railway, criar **serviço web separado**, branch `etapa-3`, root directory `/site`, variáveis conforme `site/.env.example`, domínio HTTPS com target port correspondente ao `PORT` efetivo (na configuração publicada, **8080**). Configurar o webhook do workflow DEV publicado por meio da **Production URL** `/webhook/review-v4-otimizado-dev`, não `/webhook-test/`. Chave Header Auth `X-Demo-Key` no n8n; mesmas credenciais nas variáveis `N8N_DEV_WEBHOOK_AUTH_HEADER` e `N8N_DEV_WEBHOOK_AUTH_VALUE` do site. Não versionar nenhuma senha/token.

```powershell
cd site
$env:APP_PASSWORD='UMA_SENHA_LOCAL_FORTE'
$env:SESSION_SECRET='uma-chave-local-aleatoria-com-mais-de-24-caracteres'
node server.js
# Outro terminal, dentro de site:
node --test tests/smoke.test.js
```

A rota `GET /health` verifica apenas se o servidor web responde; não mede disponibilidade de Airtable/n8n/OpenAI/Slack nem prova uptime contínuo. Registrar em captura o horário em que estiver acessível, sem declarar 24h de observação se não ocorreu.

## Resultados DEV e limitações

Benchmark real **controlado** da Etapa 2, com 15 requisições sequenciais por versão e 10 duplicatas por versão: chamadas LLM **15 -> 5** (−66,67%), latência média **2.396,87 -> 1.549,93 ms** (−35,34%), custo LLM estimado **US$ 0,000675 -> US$ 0,000225** (−66,67%) e consultas Airtable **15 -> 20** (+33,33%). Persistidos 5 registros em cada versão. Dados sintéticos, ordem fixa e pequena amostra; não representar como resultado de produção, ROI ou economia total. Acurácia não avaliada nesse benchmark. Amostra *diferente* de 5 exemplos rotulados obteve 80% de acurácia conjunta, abaixo da meta inicial de 90%.

Segurança e governança possuem limitações: senha única para demo; rate limiting em memória; sanitização regex não cobre todos os dados pessoais; texto original permanece no Airtable DEV; deduplicação consulta-criação não é atômica; sem prova de conformidade LGPD integral; não existem evidências de piloto com 3 clientes ou SLA real de resposta às reclamações. Retenção com exclusão real, contratos e bases legais dependem de aprovação.

## Suporte e troubleshooting

| Sintoma | Como verificar |
| --- | --- |
| 404 em `/webhook-test/` | Webhook de teste exige clicar em **Execute workflow** e aceita uma chamada por ativação. |
| 404 em `/webhook/` | Publicar/ativar o fluxo DEV e conferir a Production URL. |
| 403 sem `X-Demo-Key` | Bloqueio esperado — no teste de 23/11 não houve execução n8n. |
| 403 com autenticação | Comparar exatamente nome/valor de `X-Demo-Key`, redeploy e credencial do n8n. |
| Recebido mas não confirmado | Verificar **Executions** no n8n e o registro no Airtable; ACK não garante classificação. |
| Site 502/inacessível | Verificar logs Railway, variáveis mínimas, root `/site`, `PORT` e target port. |
| Dashboard vazio | Verificar PAT Airtable DEV de leitura, IDs da base/tabela e limite de 100 registros. |

Para os resultados e métodos completos, consultar [`../benchmark-real-deduplicacao-dev.md`](../benchmark-real-deduplicacao-dev.md), [`../etapa-2-sanitizacao-pii.md`](../etapa-2-sanitizacao-pii.md), [`../etapa-2-observabilidade-router.md`](../etapa-2-observabilidade-router.md) e os ADRs históricos [`../adr/ADR-001-stack.md`](../adr/ADR-001-stack.md) e [`../adr/ADR-002-deploy-e-ambientes.md`](../adr/ADR-002-deploy-e-ambientes.md).
