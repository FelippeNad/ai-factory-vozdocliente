# n8n local — VozDoCliente / Etapa 2

## Escolha do workflow

Para a entrega estável, usar:

- **Router DEV:** `workflows/vozdocliente-router-v4-otimizado-dev.json`.
  Avaliação nova, duplicata antes do LLM e falha segura do precheck foram
  validadas no n8n pelo responsável. Export inativo, sem credenciais vinculadas.
- **Retenção DEV:** `workflows/vozdocliente-retencao-v1.json`, somente DRY_RUN.
  `retention-6` teve 4 analisados, 2 elegíveis, 0 exclusões/falhas e auditoria real
  confirmada no Airtable DEV. Export inativo, sem credenciais vinculadas.
- **Sem APIs:** `workflows/vozdocliente-retencao-demo.json`. Transportes Code,
  métricas e Slack simulados. Manter inativo e executar manualmente. Esperado:
  6 analisados, 2 elegíveis, 0 excluídos, 3 páginas e 2 datas inválidas (`partial`).

Os três arquivos `vozdocliente-router-v4-observavel-dev.json`,
`vozdocliente-observabilidade-router-dev.json` e `vozdocliente-erros-router-dev.json`
são **experimentais**, testados offline e pendentes de integração no engine.
Não são a demonstração principal. Ver [observabilidade experimental](../docs/etapa-2-observabilidade-router.md).

V0/v1/v2 são protótipos históricos. V3 é referência antiga de produção com
`active=true`, e v4 original é a baseline de PII inativa. Essas versões conservam
metadados de credenciais (IDs/nomes, sem tokens); não importar como DEV pronto.
Os exports v3/v4 foram preservados. Não ativar workflows históricos ou agendas.

## Instâncias e arquivo de ambiente

A classificação usa `docker-compose.yml`, porta **5678**, n8n **2.28.7** e
volume `n8n_data`. A retenção usa `docker-compose.retention.yml`, porta **5680**
e volume próprio. Não são a mesma instância, e as credenciais não são compartilhadas
implicitamente. O primeiro acesso cria uma conta owner; não usar `admin/admin`.

Executar na raiz do repositório. Para validar sem iniciar contêineres e sem
imprimir variáveis reais:

```powershell
docker compose --env-file .env.example -f n8n-mirror/docker-compose.yml config --quiet
docker compose --env-file .env.example -f n8n-mirror/docker-compose.retention.yml config --quiet
```

Ao configurar uma instância depois da revisão, usar `--env-file` explicitamente.
`--env-file n8n-mirror/.env` aponta ao arquivo desta pasta; `--env-file .env` ao
arquivo da raiz. Credenciais são selecionadas na UI; não copiar tokens ao JSON.
Os roteiros de cada componente explicam recriação local, sem remover volumes.
Esta revisão não iniciou/recriou contêineres nem alterou `.env` reais.

## Router recomendado

Exige `CLASSIFIER_ENV=DEV`, `CLASSIFIER_DEV_BASE_ID`, `CLASSIFIER_DEV_TABLE_ID`
e `CLASSIFIER_SLACK_DEV_CHANNEL_ID` para alertas negativos. O Compose repassa essas
variáveis; escrever em um `.env` diferente do selecionado não altera o serviço.
Selecionar OpenAI DEV em `LLM DEV`, Airtable DEV nos dois GETs e em `Airtable DEV`,
e Slack DEV em `Slack DEV`. Validar projeto/base/tabela/canal nas contas: o nome
DEV da variável não comprova segregação.

Importar como **novo workflow inativo**, sem substituir v3/v4. Escutar
`Webhook Review` e enviar apenas fixture sintética para:

```text
POST http://localhost:5678/webhook-test/review-v4-otimizado-dev
```

A primeira execução deve classificar e persistir; repetir o ID deve encerrar em
`Ja existe? DEV`, sem executar `LLM DEV`. Falha do GET deve interromper antes do
LLM. O corpo do LLM continua usando somente `review_text_sanitized`.
Este workflow faz chamadas reais DEV quando executado; não tem DRY_RUN.
O protótipo LM Studio/Qwen das capturas antigas não descreve este export OpenAI.

## Retenção recomendada

Manter `RETENTION_ENV=DEV` e `RETENTION_DRY_RUN=true`. Seleção por IDs e nome exato
`RETENTION_TABLE_NAME` (padrão `Reviews`; `ReviewsRetentionTest` no teste isolado).
A auditoria exige `RetentionAudit` e 18 campos. Não mudar as confirmações DELETE.
Selecionar a mesma credencial Airtable DEV em `Airtable DEV operacao` e
`Airtable DEV sem body`. HTTP Request 4.1 usa `sendBody` literal, com IF separando
POST/PATCH JSON de GET/DELETE. A DEMO usa Code no lugar desses transportes.

O alerta de falha da retenção usa `Slack DEV falha`, opt-in via
`RETENTION_ALERTS_ENABLED`, `RETENTION_ENV=DEV` e `RETENTION_SLACK_DEV_CHANNEL_ID`.
O responsável informou recebimento real de alerta sintético, `alert_status=sent`
e erro nulo. Isso não valida o Slack integrado dos workflows experimentais.

## Documentação e segurança

- [Estado da entrega e catálogo](../README.md).
- [Sanitização PII](../docs/etapa-2-sanitizacao-pii.md).
- [Otimização, benchmark e limites](../docs/etapa-2-otimizacao-v4.md).
- [Retenção e auditoria](../docs/etapa-2-retencao-exclusao.md).
- [Observabilidade da retenção](../docs/etapa-2-observabilidade.md).
- [Auditoria de publicação](../docs/entrega-etapa-2.md).
- [Mapa LGPD](../docs/lgpd/mapa-dados-pessoais.md) e
  [rotação de credenciais](../docs/security/rotacao-credenciais.md).

Produção Railway está indisponível após o período gratuito, conforme informado
pelo responsável. Não usar os endpoints ou instruções de ativação dos protótipos
históricos. Os testes/exports rodam offline; publicação exige revisão de privacidade
das capturas históricas e conferência de autodeploy/webhooks nas contas.
