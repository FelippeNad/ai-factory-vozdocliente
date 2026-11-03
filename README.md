# VozDoCliente — AI Review Router

Projeto da disciplina AI Factory da PUCPR: triagem de avaliações por sentimento e
tema, com n8n, LLM, Airtable e Slack. A Etapa 2 adiciona controles de segurança e
privacidade. A entrega da Etapa 2 está publicada na branch `etapa-2` do GitHub. A implementação foi preparada e validada sem novo deploy de produção, exclusão real de dados ou rotação de credenciais.

## Estado da entrega — 02/11/2026

### VALIDADO NO N8N

Validações locais informadas pelo responsável do projeto, com dados sintéticos e
recursos DEV. Não foram repetidas contra fornecedores nesta auditoria:

- Sanitização PII antes do LLM, sem fallback para o texto original.
- Deduplicação e classificação do **Router v4 otimizado DEV**: avaliação nova e
  duplicata interrompida antes do LLM.
- Bloqueio seguro quando a consulta de precheck falha, sem LLM nem persistência.
- Retenção **DRY_RUN** com auditoria no Airtable DEV: `retention-6`, 4 analisados,
  2 elegíveis, 0 excluídos, 0 falhas, 2 páginas, `audit_persisted=true` e
  `audit_finalized=true`.
- Alerta de falha sintética **enviado e recebido no Slack DEV**:
  `alert_status=sent`, `alert_error_code=null`, com logs e métricas.
  Essa validação pertence à observabilidade da retenção, não ao Router experimental.

### VALIDADO OFFLINE

- Benchmark com a mesma carga sintética de **120 eventos**: **120 → 30 chamadas
  LLM simuladas** (−75%), mesmos 30 registros e textos de alertas. Consultas
  Airtable simuladas: 120 → 150. Não são chamadas reais nem economia faturada.
- O harness ficou mais lento: média 458,654 → 555,445 ms/lote. Não foi demonstrado
  ganho de latência de API ou de produção. Ver [metodologia e amostras](docs/etapa-2-otimizacao-v4.md).
- Testes automatizados de sanitização, classificação, deduplicação, retenção,
  diagnóstico de schema, observabilidade, exports e barreiras de segurança.
- Exercício de rotação com 38 cenários de estados fictícios, sem troca de tokens
  ou teste criptográfico real do n8n.

### EXPERIMENTAL / PENDENTE

- Os **três workflows de observabilidade do Router** foram testados offline;
  importação, subworkflows, Error Trigger e Slack integrado no engine continuam
  pendentes. Não são o caminho recomendado para a demonstração estável.
- Dashboard com dados reais, métricas de latência e custos reais, corpus rotulado
  e acurácia de classificação ainda não foram produzidos.
- O [relatório visual de 23 eventos](docs/evidencias/router-observabilidade-simulacao.html)
  é **SIMULAÇÃO OFFLINE**. p50=5 ms, p95=31 ms e p99=31 ms descrevem somente o
  harness com mocks, N=3 execuções. **Não são métricas de produção ou do n8n.**
- O serviço Railway possui disponibilidade temporária, condicionada ao período gratuito restante. Os smoke tests de produção apresentados são históricos e não comprovam disponibilidade contínua. A entrega da Etapa 2 foi validada localmente, sem necessidade de novo deploy de produção.
- A branch `etapa-2` foi publicada em 02/11/2026, sem merge na `main` e sem comando de deploy. A captura original do Slack presente no histórico público do Git permanece pendente de remediação. A versão atual das capturas foi anonimizada.


## Workflows recomendados e referências

Todos os caminhos abaixo estão em `n8n-mirror/workflows/`.

| Arquivo | Uso nesta entrega | Estado do export |
| --- | --- | --- |
| `vozdocliente-router-v4-otimizado-dev.json` | **Router DEV recomendado**, validado localmente pelo responsável | Inativo, sem referências de credenciais |
| `vozdocliente-retencao-v1.json` | **Retenção DEV recomendada**, apenas DRY_RUN na demonstração | Inativo, sem referências de credenciais |
| `vozdocliente-retencao-demo.json` | **Demonstração sem APIs**: transportes Code e alerta simulado | Inativo, sem credenciais |
| `vozdocliente-router-v4-observavel-dev.json` | Router instrumentado **experimental**, offline | Inativo, sem credenciais |
| `vozdocliente-observabilidade-router-dev.json` | Subworkflow de alerta **experimental**, offline | Inativo, sem credenciais |
| `vozdocliente-erros-router-dev.json` | Error Workflow **experimental**, offline | Inativo, sem credenciais |
| `vozdocliente-router-v4.json` | Baseline de PII preservada; não usar como configuração DEV pronta | Inativo; referências antigas de credenciais, sem valores |
| `vozdocliente-router-v3.json` | Referência histórica de produção; **não importar/ativar** para demonstração | `active=true` histórico, preservado; referências sem valores |
| `vozdocliente-router-v0.json`, `v1.json`, `v2.json` | Protótipos históricos; não recomendados | Inativos; referências antigas sem valores |

Referências de credenciais no JSON são metadados, não tokens, mas podem vincular
credenciais existentes ao importar na mesma instância. Não reutilizar as versões
históricas como configuração DEV. Export inativo não torna uma execução manual
HTTP uma simulação: os workflows operacionais fazem chamadas reais quando usados.

## Fluxo recomendado: Router v4 otimizado DEV

```text
Webhook Review → Sanitizar PII → Preparar deduplicacao DEV
  → Airtable Precheck DEV → Validar busca e restaurar texto → Ja existe? DEV
       true: encerra sem LLM
       false: LLM DEV → Parse + Merge → Airtable Buscar review_id
         → Validar busca final DEV → Confirmar novo? DEV
              true: encerra (duplicata)
              false: Airtable DEV → É negativo? → Slack DEV se negativo
```

Sentimentos: `positivo`, `neutro`, `negativo`. Temas: `entrega`, `produto`,
`atendimento`, `preco`, `app_bug`. A validação rejeita saídas fora desse contrato.
O precheck falha fechado; a consulta final continua obrigatória. Leitura e criação
não são atômicas: a corrida concorrente não foi eliminada.

Somente `review_text_sanitized` segue ao LLM. Airtable mantém o original para
tratativa; Slack v4 recebe tema/nota e instrução fixa. Regex não detecta toda PII,
não anonimiza o dado e não estabelece conformidade integral com a LGPD.

## Configuração local

- Classificação: `n8n-mirror/docker-compose.yml`, n8n **2.28.7**, porta
  `127.0.0.1:5678`, volume próprio.
- Retenção: `n8n-mirror/docker-compose.retention.yml`, n8n **2.28.7**, porta
  `127.0.0.1:5680`, volume independente.
- Usar `--env-file` explícito: na raiz, `--env-file n8n-mirror/.env` seleciona
  esse arquivo; `--env-file .env` seleciona o arquivo da raiz. Não presumir que
  editar um deles altera a outra instância. Credenciais são selecionadas na UI.
- O Router otimizado exige `CLASSIFIER_ENV=DEV`, `CLASSIFIER_DEV_BASE_ID`,
  `CLASSIFIER_DEV_TABLE_ID` e `CLASSIFIER_SLACK_DEV_CHANNEL_ID` para alertas.
  Não usa fallback para `AIRTABLE_BASE_ID`.
- Retenção usa `RETENTION_ENV=DEV`, `RETENTION_DRY_RUN=true`, IDs DEV e
  `RETENTION_TABLE_NAME=ReviewsRetentionTest` para a tabela de testes isolada.
  `RetentionAudit` e seus 18 campos permanecem obrigatórios. Prazo de 30 dias
  é demonstrativo, não exigência legal. Não habilitar DELETE para apresentar.
- O candidato otimizado chama OpenAI; LM Studio/Qwen pertence ao protótipo
  histórico. Modelo/projeto precisam corresponder à configuração DEV validada.

Validação sintética sem iniciar serviços e sem imprimir valores de `.env` reais:

```powershell
docker compose --env-file .env.example -f n8n-mirror/docker-compose.yml config --quiet
docker compose --env-file .env.example -f n8n-mirror/docker-compose.retention.yml config --quiet
```

O primeiro acesso local cria uma conta owner; não há login padrão `admin/admin`.
Importação e execução manual: [guia local](n8n-mirror/README.md),
[otimização](docs/etapa-2-otimizacao-v4.md) e
[retenção](docs/etapa-2-retencao-exclusao.md). A DEMO não exige APIs/credenciais.

## Testes e evidências offline

Python 3.12+ e Node.js 22+, sem instalação npm. Nenhum comando abaixo faz deploy,
rotação real, DELETE ou chamadas aos fornecedores:

```powershell
python tests/validate_workflows.py
python tests/test_routing_logic.py
python -m unittest discover -s tests -v
python scripts/build_retention_workflow.py --check
python scripts/build_router_optimized_workflow.py --check
python scripts/build_router_observability.py --check
node tests/test_pii_sanitization.cjs
node tests/test_retention.cjs
node tests/test_retention_schema_diagnostic.cjs
node tests/test_observability.cjs
node tests/test_router_optimization.cjs
node tests/test_router_observability.cjs
python scripts/simular_rotacao_credenciais.py --verify docs/security/evidencias/rotacao-simulada.json
git diff --check
```

O benchmark pode ser repetido separadamente, sem outras suítes concorrentes:
`node scripts/benchmark_router_optimization.cjs`. Sem `--write`, não sobrescreve
as amostras entregues. Logs e relatórios de simulação não comprovam latência real,
recebimento Slack ou qualidade humana. A [auditoria da entrega](docs/entrega-etapa-2.md)
registra resultados, arquivos candidatos e bloqueios de publicação.

## CI e segurança antes de publicar

O único workflow GitHub Actions é `.github/workflows/ci.yml`: testes offline,
sem job de deploy, secrets de provedores, Docker build/run ou chamadas às APIs do
produto. Token limitado a `contents: read`. Dispara em push para `main`, PR com
base `main` e execução manual; **push apenas para `etapa-2` não dispara esse CI**.
Checkout e setup dos runtimes acessam infraestrutura do GitHub, não PROD.

Autodeploy de uma integração Railway/GitHub App é independente do YAML. Seu
estado não foi confirmado; indisponibilidade por fim do período gratuito não
comprova que gatilhos estejam desabilitados. Conferir manualmente source branch,
autodeploy, webhooks, apps e deploy hooks antes de autorizar publicação. Não houve
commit, push, merge, force push, alteração externa ou deploy nesta preparação.

`.env` reais, ferramenta Gitleaks baixada, relatórios brutos de scanner e coletas
`router-local*` ficam ignorados. Uma captura local de retenção com preview de IDs
foi excluída da lista de publicação. Gitleaks verifica segredos, não garante
anonimização de imagens ou ausência de todos os dados pessoais no histórico.

## Documentação

- [Índice e classificação dos documentos](docs/README.md).
- [Sanitização PII](docs/etapa-2-sanitizacao-pii.md),
  [schema Airtable](docs/airtable-schema.md) e
  [diagnóstico de schema](docs/diagnostico-schema-retencao.md).
- [Retenção e exclusão](docs/etapa-2-retencao-exclusao.md),
  [observabilidade de retenção](docs/etapa-2-observabilidade.md) e
  [observabilidade Router experimental](docs/etapa-2-observabilidade-router.md).
- [Mapa LGPD](docs/lgpd/mapa-dados-pessoais.md),
  [transferência internacional](docs/lgpd/transferencia-internacional.md),
  [rotação de credenciais](docs/security/rotacao-credenciais.md),
  [checklist](docs/lgpd/checklist-etapa-2.md) e
  [roteiro de apresentação](docs/lgpd/roteiro-evidencias.md).

Contratos, bases legais, papéis, regiões de processamento, prazos e responsáveis
continuam sujeitos à validação operacional/jurídica. Os documentos históricos de
arquitetura, smoke tests, deploy e rollback preservam o contexto da Etapa 1;
não são instruções para reativar ou testar produção nesta entrega.
