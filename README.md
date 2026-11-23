# VozDoCliente CX — AI Review Router

## AI Factory (PUCPR) — Entrega da Etapa 3

**Versão 1.0 da demonstração · 23/11/2026 · branch `etapa-3`**

**Aplicação web:** https://ai-factory-vozdocliente-production.up.railway.app  
**Health check:** https://ai-factory-vozdocliente-production.up.railway.app/health  
**Código e deploy da aplicação:** [`site/`](site/) · [`site/README.md`](site/README.md) · [`site/.env.example`](site/.env.example)  
**Documentos da Etapa 3:** [`docs/etapa-3/README.md`](docs/etapa-3/README.md) · [`docs/etapa-3/one-pager-executivo.md`](docs/etapa-3/one-pager-executivo.md) · [`docs/etapa-3/validacao-evidencias.md`](docs/etapa-3/validacao-evidencias.md)

> A demonstração publicada em 23/11/2026 **substitui as indicações históricas de indisponibilidade do Railway** contidas nos registros da Etapa 2. Os resultados e descrições das etapas anteriores devem continuar no README para preservar a rastreabilidade. A aplicação de demonstração é isolada no ambiente **DEV**: não é piloto com clientes reais nem comprova conformidade LGPD completa.

## Demonstração atual

O site Node.js 22.16.0 (Docker/Railway) permite entrar com senha, consultar indicadores de avaliações fictícias do Airtable DEV, submeter uma avaliação ao webhook **n8n DEV autenticado com `X-Demo-Key`**, acompanhar o resultado gravado e observar o alerta de avaliações negativas no Slack DEV. O site mostra metadados; o fluxo sanitiza texto antes do LLM. A autenticação por senha única serve à demonstração acadêmica, não a uma operação corporativa. Fornecer senha ao avaliador em canal privado; nunca em commits ou vídeo.

**Fluxo:** Navegador → Site Railway → n8n DEV (sanitização, precheck de duplicata, OpenAI, validação) → Airtable DEV → Slack DEV para negativas. O site consulta o Airtable para confirmar o processamento; o ACK do webhook não equivale a uma classificação concluída.

**Testes observados em 23/11:** classificação positiva confirmada (`ETAPA3-DEMO-1795471550245-E1F38E`, Positivo/Produto/5); avaliação negativa encaminhada ao Slack DEV; reenvio duplicado (`ETAPA3-DUP-d96c520aecc2`) encerrado antes do LLM; webhook sem autenticação devolveu HTTP 403 sem gerar execução no n8n. Unicidade no Airtable e retenção/uptime contínuo exigem verificações próprias.

**Benchmark DEV da Etapa 2 (não produção):** 15 requisições sequenciais por versão, com 10 duplicatas; chamadas LLM 15→5 (−66,67%), latência média 2.396,87→1.549,93 ms (−35,34%), custo LLM estimado US$ 0,000675→0,000225 (−66,67%), consultas Airtable 15→20 (+33,33%). Acurácia não medida nesse benchmark; avaliação separada de cinco exemplos obteve 80% de acurácia conjunta. Não projetar ROI nem faturamento a partir desses valores.

**Como executar:** consultar [`site/README.md`](site/README.md). Node.js 22, sem dependências npm, configuração por `site/.env.example`, `node server.js` e teste offline `node --test tests/smoke.test.js`. Railway: serviço web separado, branch `etapa-3`, root directory `/site`, porta de destino igual ao `PORT` (publicado com `8080`), webhook DEV **Production URL** (`/webhook/review-v4-otimizado-dev`), com `N8N_DEV_WEBHOOK_AUTH_HEADER=X-Demo-Key` e segredo só nas variáveis privadas.

**Diagnóstico rápido:** 404 em `webhook-test` exige “Execute workflow”; 404 em `webhook` indica workflow DEV não publicado/URL incorreta; 403 sem chave é bloqueio esperado; 403 com chave exige revisar Header Auth; avaliação recebida mas não confirmada exige checar Executions e Airtable; erro 502 exige conferir logs, `PORT`, target port e variáveis do site. `GET /health` não mede APIs externas nem uptime de 24h. Deduplicação sob concorrência não é atômica, PII sanitizada por padrões tem limites e o Airtable DEV guarda texto original.

---

## Histórico técnico — Etapas 1 e 2

> O conteúdo a seguir registra o desenvolvimento e os resultados anteriores. Referências a indisponibilidade, publicação pendente ou ausência de deploy pertencem ao contexto histórico e não substituem o estado da demonstração da Etapa 3, descrito acima.

Projeto da disciplina AI Factory da PUCPR: triagem de avaliações por sentimento e
tema, com n8n, LLM, Airtable e Slack. **Etapa 2 consolidada localmente em
23/11/2026**, com segurança/LGPD, retenção, observabilidade e benchmark real DEV.
Esta consolidação documental não executou novas chamadas externas, não modificou
workflows ou produção e não realizou commit/push. Os novos artefatos ainda aguardam
revisão de publicação; o histórico da Etapa 1 permanece identificado abaixo.

## Resultados finais e evidências

- [Dashboard de observabilidade real DEV](docs/evidencias/router-observabilidade-dev-real.html):
  coleta separada de **11 execuções** (7 sucessos, 1 duplicata, 3 falhas intencionais),
  com avaliação manual limitada de cinco exemplos e **80% de acurácia conjunta**.
- [Relatório do benchmark real antes/depois](docs/evidencias/benchmark-dev-real.html),
  [JSON agregado](docs/evidencias/benchmark-dev-real.json),
  [amostras numéricas sanitizadas](docs/evidencias/benchmark-dev-amostras.json) e
  [manifesto SHA-256](docs/evidencias/etapa-2-evidencias-manifesto.json).
- Benchmark **`097ec2ffc37c4e4081bb54d9a0c174c0`**: cinco avaliações sintéticas distintas,
  três passagens por versão, 15 requisições sequenciais por versão, IDs inéditos
  em namespaces separados, mesmo modelo/prompt/configuração. Baseline instrumentado
  classifica antes de deduplicar; otimizado mantém precheck e consulta final.
  [Método, reprodução e limites](docs/benchmark-real-deduplicacao-dev.md).

| Métrica real DEV | Antes | Depois |
| --- | ---: | ---: |
| Requisições / terminais reconciliados | 15 / 15 | 15 / 15 |
| Sucessos | 5 | 5 |
| Duplicatas | 10 | 10 |
| Falhas | 0 | 0 |
| Chamadas LLM (tentativas com resposta) | 15 | 5 |
| Consultas Airtable (GETs) | 15 | 20 |
| Registros persistidos confirmados | 5 | 5 |
| Tokens de entrada | 1611 | 537 |
| Tokens de saída | 294 | 98 |
| Custo estimado LLM (USD) | 0,000675 | 0,000225 |
| Latência média (ms) | 2396,87 | 1549,93 |
| p50 (ms) | 1950 | 695 |
| p95 (ms) | 5770 | 3437 |
| p99 (ms) | 5770 | 3437 |
| Validade estrutural | 100% (15/15) | 100% (5/5) |
| Acurácia das classificações persistidas | Não avaliada | Não avaliada |

Houve **redução de 66,67% nas chamadas LLM e no custo estimado**, e de **35,34%
na latência média** deste lote. Foram **cinco consultas Airtable adicionais
(+33,33%)**; incluindo cinco criações por versão, operações Airtable passaram
de 20 para 25 (+25%). O custo médio por classificação com custo conhecido ficou
em **US$ 0,000045 nas duas versões**: a economia veio de evitar chamadas, não
de baratear cada classificação. Todos os custos e durações deste par são conhecidos.

O precheck acrescenta consulta/latência ao caminho dos casos novos e dependência
do Airtable. A consulta final foi preservada, mas leitura/criação não são atômicas.
Economia LLM não comprova economia total: consultas Airtable, Slack e infraestrutura
não foram monetizados. A latência é `report.duration_ms` até o evento terminal,
**não o ACK HTTP**. Os percentis incluem duplicatas; N=15 faz p95/p99 selecionarem
o máximo. Amostra sintética, sequencial, com 2/3 de duplicatas, ordem antes/depois
fixa e variação/cache possíveis: **não representa produção**.

Não foram coletados snapshots de classificação persistida neste benchmark:
**não há comprovação de equivalência semântica**. Os 80% de acurácia conjunta
(sentimento 80%, tema 100%, cinco rótulos) pertencem à avaliação separada da
coleta de 11 execuções. Validade estrutural de 100% não substitui acurácia.

## Observabilidade: cinco famílias de métricas

| Família | Evidência e interpretação |
| --- | --- |
| Volume | Benchmark: 15 envios/15 terminais em cada versão, reconciliação de 100%. Coleta operacional separada: 11 terminais; não inferir seu total enviado apenas pelos logs. |
| Latência | Benchmark: média/p50/p95/p99 na tabela; coleta de 11 runs: p50=3742 ms, p95/p99=6730 ms, 10 durações conhecidas. Sem misturar denominadores. |
| Custo | Benchmark com cobertura completa: US$ 0,000675 → 0,000225. Na coleta de 11 runs, média US$ 0,0000434 nas cinco classificações com custo conhecido; outras duas têm custo desconhecido, nunca zero. |
| Erro | Benchmark: 0/15 por versão, apenas neste lote. Coleta de falhas controladas: 3/11=27,27%, incluindo três falhas intencionais; não é taxa de operação normal. |
| Qualidade | Validade estrutural independente: 100% em ambos os lotes. Acurácia conjunta separada: 80% (4/5), abaixo da meta de 90%; sem acurácia medida no benchmark. |

### Thresholds iniciais DEV

| Indicador | Limite |
| --- | --- |
| Latência p50 / p95 / p99 | Até 8 s / 12 s / 15 s |
| Custo médio por classificação com custo conhecido | Até US$ 0,0001 |
| Taxa de erro em operação normal | Até 5%; não aferida como indicador representativo pelos lotes controlados |
| Volume reconciliado em lote controlado | 100% dos envios vinculados a terminais |
| Acurácia conjunta de sentimento e tema | Pelo menos 90%; não atendida nos cinco exemplos separados (80%) |
| Validade estrutural | 100% |

Justificativas individuais, cobertura e denominadores estão no
[registro dos thresholds](docs/etapa-2-observabilidade-router.md#thresholds-iniciais-dev-e-resultados-observados).
São limites iniciais DEV, sem SLA/SLO de produção. O benchmark atende aos limites
numéricos de latência/custo, volume e validade neste lote; não avalia a meta semântica.

| Prioridade | Público | Canal / estado | Ação esperada |
| --- | --- | --- | --- |
| P1 — falha terminal | Responsável técnico | Slack DEV, automático opt-in implementado e validado | Correlacionar run/etapa/código, distinguir falha intencional e investigar antes de reprocessar. |
| P2 — falha de entrega da observabilidade | Responsável técnico | Diagnóstico local; sem notificação automática | Conferir pareamento, permissões e entrega; corrigir e revalidar sem repetir negócio automaticamente. |
| P3 — desvio de threshold | Responsável técnico | Revisão manual do dashboard; sem notificação automática | Conferir cobertura/denominador, registrar ação e repetir avaliação controlada se necessário. |

## Segurança, LGPD, rotação e retenção

- **Sanitização:** somente `review_text_sanitized` chega ao LLM, sem fallback.
  JSON/enums inválidos e falhas de consulta bloqueiam o fluxo. Regex reduz exposição,
  mas não cobre toda PII ou anonimiza nomes/contexto. O Airtable ainda conserva
  o original para tratativa; Slack minimiza o conteúdo.
- **Isolamento:** `CLASSIFIER_ENV=DEV`, destinos DEV explícitos, sem fallback PROD;
  exports de entrega inativos, sem credenciais/pinData. Configurações de não salvar
  payloads foram restauradas e verificadas nas duas cópias publicadas antes do par.
  Logs globais não foram habilitados para coletar o benchmark.
- **Rotação:** procedimento e **38 cenários simulados** verificáveis; nenhuma
  rotação/revogação real ou migração criptográfica foi demonstrada. Custódia,
  escopos e titularidade corporativa continuam sujeitos à revisão.
- **Retenção/exclusão:** `retention-6` em DRY_RUN: 4 analisados, 2 elegíveis,
  0 excluídos/falhas, 2 páginas e auditoria persistida/finalizada. Agenda/30 dias
  são demonstrativos; DELETE real não foi executado. Pruning proposto de 7 dias/
  1000 execuções e descarte de logs por idade exigem validação própria; rotação
  Docker por tamanho não comprova o máximo de 90 dias do briefing.
- **Governança:** mapa de dados, hipóteses de base legal, transferências, direitos,
  acessos e recuperação estão documentados; contratos, prazos e aprovações humanas
  permanecem pendentes. Não há declaração de conformidade integral com a LGPD.

## Histórico offline e Etapa 1

O [benchmark offline de 120 eventos](docs/etapa-2-otimizacao-v4.md) teve 120 → 30
chamadas LLM simuladas (−75%) e média do harness 458,654 → 555,445 ms/lote, mais
lenta. São outras carga e metodologia; não combinar seus números com o par real
de 15 envios. A [simulação de 23 eventos](docs/evidencias/router-observabilidade-simulacao.html)
tem três runs com mocks, p50=5 ms e p95/p99=31 ms, sem chamadas externas.

ADRs, C4, smoke tests, deploy/rollback e capturas da Etapa 1 são históricos e
permanecem preservados nos links de documentação ao final. Não comprovam estado
atual do Railway nem autorizam reativação/novo deploy. A publicação histórica da
branch `etapa-2` em 02/11/2026 não inclui automaticamente estes novos artefatos.
Remediação das capturas antigas no histórico público, revisão de autodeploy e
aprovações de publicação continuam pendentes.

Referências da Etapa 1: [stack](docs/adr/ADR-001-stack.md),
[deploy e ambientes](docs/adr/ADR-002-deploy-e-ambientes.md),
[C4 contexto](docs/architecture/c4-context.md),
[C4 containers](docs/architecture/c4-container.md),
[smoke tests](docs/smoke-tests.md), [rollback](docs/rollback.md),
[postmortem](docs/postmortem-n8n-encryption-key.md) e
[capturas históricas](docs/evidencias/evidencias-projeto.md).

## Workflows recomendados e referências

Todos os caminhos abaixo estão em `n8n-mirror/workflows/`.

| Arquivo | Uso nesta entrega | Estado do export |
| --- | --- | --- |
| `vozdocliente-router-v4-otimizado-dev.json` | Router DEV otimizado sem instrumentação integrada, validado localmente | Inativo, sem referências de credenciais |
| `vozdocliente-retencao-v1.json` | **Retenção DEV recomendada**, apenas DRY_RUN na demonstração | Inativo, sem referências de credenciais |
| `vozdocliente-retencao-demo.json` | **Demonstração sem APIs**: transportes Code e alerta simulado | Inativo, sem credenciais |
| `vozdocliente-router-v4-observavel-dev.json` | **Router atual observável DEV**; coleta real e base da cópia otimizada do benchmark | Inativo, sem credenciais |
| `vozdocliente-observabilidade-router-dev.json` | Subworkflow de alerta P1 validado no Slack DEV | Inativo, sem credenciais |
| `vozdocliente-erros-router-dev.json` | Error Workflow DEV; cenários nativos exigem evidência específica conforme roteiro | Inativo, sem credenciais |
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
python scripts/build_router_benchmark.py --check
python scripts/export_etapa2_evidence.py --check
python scripts/validate_doc_links.py
node tests/test_pii_sanitization.cjs
node tests/test_retention.cjs
node tests/test_retention_schema_diagnostic.cjs
node tests/test_observability.cjs
node tests/test_router_optimization.cjs
node tests/test_router_observability.cjs
node tests/test_router_real_benchmark.cjs
python scripts/simular_rotacao_credenciais.py --verify docs/security/evidencias/rotacao-simulada.json
git diff --check
```

O benchmark pode ser repetido separadamente, sem outras suítes concorrentes:
`node scripts/benchmark_router_optimization.cjs`. Sem `--write`, não sobrescreve
as amostras offline entregues. A reprodução do benchmark real exige um plano novo
e autorização para chamadas DEV; não executar novamente apenas para gerar documentação.
Com a coleta local existente, `python scripts/export_etapa2_evidence.py` regenera
os seis artefatos públicos sem rede; `--check` confere o checkout sem logs locais.
Logs e relatórios de simulação não comprovam latência real,
recebimento Slack ou qualidade humana. A [auditoria da entrega](docs/entrega-etapa-2.md)
registra resultados, arquivos candidatos e bloqueios de publicação.

## Troubleshooting DEV

| Sintoma | Diagnóstico / ação |
| --- | --- |
| `Parametros/protecoes da copia DEV alterados` | Conferir tipo/versão e valores reais. O comparador recompõe somente defaults comprovados no n8n 2.28.7, em memória; não ignora código/expressões ou mudanças de segurança. |
| `Persistencia de payloads/configuracao do workflow alterada` | Os quatro campos de retenção precisam estar explícitos: erro/sucesso=`none`, manual/progresso=`false`. Corrigir nas cópias, salvar e republicar; nunca contornar a verificação. |
| Plano contém `started.json` | Plano de uso único já reservado. Não remover o marcador nem completar/repetir o lote; criar novo plano/namespace. `local-02` já foi concluído. |
| Custo `null` / qualidade não medida | Conferir cobertura de usage/preços. Não tratar desconhecido como zero. Zero snapshots no benchmark significa acurácia não avaliada, não equivalência semântica. |
| ACK HTTP rápido ou timeout | Usar pacote terminal validado e duração instrumentada. Não reenviar automaticamente: pode ter ocorrido persistência antes da perda de resposta. |
| Credencial/DEV inválido ou precheck falha | Corrigir destino/configuração DEV; preservar sanitização, consulta final e interrupção segura, sem fallback PROD. |

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
`router-local*`, `router-benchmark-local*` e exports reimportados com referências
de credenciais ficam ignorados. Somente agregados/amostras numéricas permitidas
e manifestos sanitizados do benchmark são candidatos à publicação. Uma captura local de retenção com preview de IDs
foi excluída da lista de publicação. Gitleaks verifica segredos, não garante
anonimização de imagens ou ausência de todos os dados pessoais no histórico.

## Documentação

- [Índice e classificação dos documentos](docs/README.md).
- [Benchmark real DEV e reprodução](docs/benchmark-real-deduplicacao-dev.md).
- [Sanitização PII](docs/etapa-2-sanitizacao-pii.md),
  [schema Airtable](docs/airtable-schema.md) e
  [diagnóstico de schema](docs/diagnostico-schema-retencao.md).
- [Retenção e exclusão](docs/etapa-2-retencao-exclusao.md),
  [observabilidade de retenção](docs/etapa-2-observabilidade.md) e
  [observabilidade Router DEV e thresholds](docs/etapa-2-observabilidade-router.md).
- [Mapa LGPD](docs/lgpd/mapa-dados-pessoais.md),
  [transferência internacional](docs/lgpd/transferencia-internacional.md),
  [rotação de credenciais](docs/security/rotacao-credenciais.md),
  [checklist](docs/lgpd/checklist-etapa-2.md) e
  [roteiro de apresentação](docs/lgpd/roteiro-evidencias.md).

Contratos, bases legais, papéis, regiões de processamento, prazos e responsáveis
continuam sujeitos à validação operacional/jurídica. Os documentos históricos de
arquitetura, smoke tests, deploy e rollback preservam o contexto da Etapa 1;
não são instruções para reativar ou testar produção nesta entrega.
