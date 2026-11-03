# Etapa 2 — observabilidade mínima DEV

Atualização da entrega: o responsável informou falha sintética com alerta
**enviado e recebido no Slack DEV**, `alert_status=sent` e erro nulo. Essa validação
não abrange os três workflows experimentais de observabilidade do Router.

Esta página descreve o componente de **retenção**. A integração posterior ao
[Router DEV observável](etapa-2-observabilidade-router.md) reutiliza o transporte
Slack, adiciona captura explícita/ Error Workflow e relatório HTML; suas
validações no engine são independentes das evidências da retenção.

## Escopo e evidência anterior

Reaproveita o motor, o resumo e a auditoria de retenção. Não altera classificação
v3/v4, PROD, schema Airtable nem as barreiras de exclusão. Não instala serviço de
monitoramento. A cobertura desta entrega é **retenção DEV**, não toda a cadeia de
classificação, LLM ou infraestrutura produtiva.

O usuário informou validação operacional anterior `retention-6`: DRY_RUN, 4
analisados, 2 elegíveis, 0 excluídos, 0 falhas, 2 páginas, `audit_persisted=true` e
`audit_finalized=true`. Estão disponíveis o [recorte do resumo sem preview](evidencias/retention-6-resumo-redigido.png)
e a [auditoria agregada](evidencias/retention-6-RetentionAudit-table.png). O original
local do resumo com IDs correlacionáveis ficou excluído da publicação. Esse resultado não é
uma execução feita nesta implementação e não valida o Slack ou a latência novos.
Revisar/redigir as imagens antes de apresentação; não foram modificadas aqui.

## Implementação

```text
Resumo sem PII -> Observabilidade DEV -> Alertar falha DEV?
  não -> Resultado observabilidade
  sim -> Slack DEV falha -> Resultado observabilidade
```

Os nodes são acrescentados somente depois do encerramento da retenção. Falha de
notificação não reinicia a retenção nem autoriza DELETE. `Resultado observabilidade`
preserva o resumo original, inclusive seu preview transitório, e acrescenta
`observability`. Não copia a resposta ou mensagens de erro do Slack.

`observe.js` monta por lista de campos permitidos um evento com `run_id`, `stage`,
`status`, `duration_ms` e `error_code`. Somente códigos fixos são aceitos;
valores desconhecidos tornam-se `UNKNOWN_ERROR` ou `OBS_INPUT_INVALID`.
Não loga input completo, preview, record IDs, nomes, avaliações, datas de registros,
tokens, headers, corpo de respostas ou mensagens do provedor. O identificador da
execução permite correlação operacional e não prova anonimização dos dados.

Métricas por execução em `observability.metrics` e no evento JSON:

| Campo | Significado |
| --- | --- |
| `runs_total` | 1 para cada resumo observado |
| `runs_success` / `runs_failure` | 0/1, mutuamente exclusivos; `partial`, `blocked`, falhas ou auditoria não finalizada contam como falha |
| `processed` | Quantidade `analyzed`, não quantidade excluída |
| `failures` | Contador existente do motor; pode haver mais de um código por incidente |
| `latency_ms` | `finished_at - started_at`, duração total da retenção, incluindo esperas; não é latência isolada da API ou LLM |

Datas inválidas produzem latência `null`, nunca um valor inventado. Somar os
contadores por execuções distintas permite calcular sucesso/falha e volume; uma
taxa exige uma janela definida. Não foram medidos p95 ou disponibilidade real.
Essas métricas são snapshots JSON; não há servidor Prometheus ou dashboard.
Os 18 campos existentes de `RetentionAudit` permanecem inalterados. Métricas novas
não passam a ser persistidas no Airtable: dependem da coleta dos logs/saídas.

## Logs: destino comprovado e retenção

Na implementação instalada no container DEV, n8n **2.28.7**:

- `@n8n/task-runner/dist/js-task-runner/js-task-runner.js`, `buildCustomConsole`,
  encaminha `console.log` para `logNodeOutput`; os demais métodos são no-op.
- `n8n-core/dist/execution-engine/node-execution-context/execute-context.js`,
  linhas 83–91, encaminha execução **manual ao navegador**; em modo não manual,
  escreve no stdout somente quando `CODE_ENABLE_STDOUT=true`.

Por isso o código usa `console.log` com um objeto de campos permitidos. O Compose
dedicado prevê `CODE_ENABLE_STDOUT=true`, mantendo `N8N_LOG_LEVEL=warn`. O stdout
pode conter prefixo do n8n antes do JSON; o coletor deve extrair o objeto, não
presumir que toda linha do container seja JSON puro. O resultado do node também
expõe o mesmo evento sem exigir guardar payload de execução.

O driver Docker `json-file` é configurado com `max-size=5m`, `max-file=3`.
Isso limita armazenamento **por tamanho**, não garante descarte por idade. Para
o limite de até 90 dias de logs do briefing, definir responsável e limpeza por
idade no ambiente efetivo/coletor; isso permanece pendente. Pruning n8n não limpa
Docker, navegador, Slack ou backups. Não habilitar stdout global em uma instância
com outros workflows que possam imprimir PII. Nada foi aplicado ao container nesta
sessão; a configuração exige recriação manual da instância DEV.

## Alerta Slack DEV opt-in

No arquivo `.env` efetivamente usado pelo Compose dedicado:

```dotenv
RETENTION_ENV=DEV
RETENTION_DRY_RUN=true
RETENTION_ALERTS_ENABLED=false
RETENTION_SLACK_DEV_CHANNEL_ID=
```

O padrão não envia Slack. Para teste manual posterior, usar `true` literal e um
ID de canal DEV válido; nomes como `#canal` são rejeitados. `RETENTION_ENV=DEV`
continua obrigatório para enviar. Validar no Slack que workspace, canal e bot são
realmente DEV: o formato do ID e o nome da variável não comprovam isolamento.

Selecionar uma credencial Header Auth **exclusiva Slack DEV**, autorizada apenas
ao necessário, no node `Slack DEV falha`: `Authorization: Bearer <token DEV>`.
Não colocar token no `.env.example`, workflow ou evidências; não reaproveitar a
credencial Airtable nem Slack PROD. Nenhuma credencial real foi alterada aqui.

Reaproveita o padrão HTTP Request **4.1** do projeto, com `sendBody: true` literal,
JSON, endpoint fixo `https://slack.com/api/chat.postMessage`, timeout de 5 segundos,
sem redirect ou retry. Envia texto fixo, run ID validado, código fixo, contagem e
duração; sem preview ou detalhes da avaliação. `mrkdwn` e unfurl estão desativados.

Somente falhas geram tentativa. A confirmação exige HTTP 2xx **e** `body.ok=true`;
HTTP 200 com `ok=false` falha. Erros de canal/configuração não fazem HTTP.
`alert_status` distingue `not_needed`, `disabled`, `blocked`, `sent`, `failed` e
`simulated` (DEMO). Falha de entrega usa apenas `SLACK_DELIVERY_FAILED` e um segundo
evento de etapa `slack_alert`; não modifica as métricas/status do motor de retenção.
Timeout pode ocorrer depois da entrega; sem retry evita repetição automática,
mas reexecuções manuais podem duplicar alertas. Não há deduplicação durável.

## Demonstração reproduzível sem APIs

Na raiz, Node.js 22+ e Python 3.12+, sem dependências adicionais:

```powershell
node tests/test_observability.cjs
node scripts/simular_falha_observabilidade.cjs
python scripts/build_retention_workflow.py --check
python tests/validate_workflows.py
```

O simulador percorre o workflow exportado com transporte em memória: injeta HTTP
503 no schema e confirma uma tentativa Slack **simulada**, 0 exclusões,
`runs_failure=1`, `error_code=HTTP_5XX`. Sua saída marca
`scope=SIMULACAO_OFFLINE`, `real_slack_delivery=false` e
`real_airtable_access=false`. `sent` nesse teste é confirmação do mock, não do Slack.
Um relatório dessa execução está em
[observabilidade-falha-simulada.json](evidencias/observabilidade-falha-simulada.json).
Os tempos são do relógio sintético do harness, não desempenho real.

Para mostrar no canvas, importar **`vozdocliente-retencao-demo.json`** inativo.
Verificar que todos os transportes, inclusive `Slack DEV falha`, são **Code**.
Executar manualmente: os mesmos 6 analisados/2 elegíveis/2 datas inválidas produzem
`partial`, um evento de falha e `alert_status=simulated`. A DEMO fixa ambiente e
destino sintéticos e não faz chamadas, mesmo com variáveis externas configuradas.
Capturar canvas, `observability.event`, métricas, Console do navegador e resultado
simulado. Não apresentar a DEMO como recebimento real no Slack.

## Validações manuais indispensáveis

1. **Importação e regressão DEV:** importar nova v1 inativa; selecionar as mesmas
   credenciais Airtable DEV nos dois transportes e Slack DEV apenas no terceiro.
   Manter DRY_RUN e confirmações de DELETE vazias. Repetir um lote sintético saudável
   e conferir auditoria, reviews intactas, evento `success`, duração plausível e
   ausência de alerta. `retention-6` comprova a versão anterior, não esta importação.
2. **Destino dos logs:** testar a DEMO manualmente e observar evento no navegador.
   Para stdout, somente numa **cópia da DEMO sem HTTP**, agendar temporariamente
   um intervalo curto, aguardar um evento não manual em `docker logs`, e desativar
   a cópia. Não ativar a agenda operacional. Confirmar rotação Docker, acesso e
   política de descarte por idade; manual não aparecer em stdout é comportamento
   esperado desta versão, não prova de perda do evento.
3. **Entrega real Slack DEV:** verificar workspace/canal/bot, escopo `chat:write`
   e associação ao canal. Em cópia de teste, manter **apenas** Manual Trigger,
   fixture abaixo e os quatro nodes de observabilidade (sem nodes Airtable).
   Configurar alertas opt-in e credencial DEV; executar pelo responsável e
   conferir `alert_status=sent` e recebimento da mesma run ID no canal DEV.
   Capturar a mensagem sem abrir credenciais. Essa chamada não foi executada aqui.
4. **Privacidade das evidências:** revisar JSON, Console, mensagem Slack e imagens;
   não anexar `.env`, token, headers, respostas completas ou preview correlacionável.
   Registrar versão do n8n, quem validou e se a evidência é real ou simulada.

Fixture para o Code que antecede `Observabilidade DEV` na cópia manual sem Airtable:

```javascript
const now = Date.now();
return [{ json: {
  run_id: 'retention-900001', status: 'blocked', analyzed: 0, failures: 1,
  deleted: 0, error_codes: ['HTTP_5XX'], audit_persisted: false, audit_finalized: false,
  started_at: new Date(now - 1000).toISOString(), finished_at: new Date(now).toISOString()
} }];
```

Para aplicar configurações **somente localmente**, pelo responsável, na raiz:

```powershell
docker compose -p vozdocliente-retencao --env-file .env -f n8n-mirror/docker-compose.retention.yml config --quiet
docker compose -p vozdocliente-retencao --env-file .env -f n8n-mirror/docker-compose.retention.yml up -d --force-recreate n8n
```

Se usar `n8n-mirror/.env`, substituir o caminho em ambos os comandos. Não imprimir
`config` completo nem remover volume. Nenhum desses comandos de aplicação foi
executado nesta entrega.

## Limites

Observa encerramentos controlados do motor. Crash, encerramento do container,
timeout global antes do resumo ou erro inesperado de Code podem impedir log e
alerta. Não há watchdog externo nem integração global Error Trigger; esses casos
e a classificação DEV completa permanecem fora desta solução mínima. A auditoria
existente ajuda a investigar runs incompletas, mas não substitui monitor externo.
Logs e Slack têm retenção/acesso próprios; a solução não comprova conformidade
integral com LGPD nem o nível final da rubrica sem as validações/evidências humanas.
