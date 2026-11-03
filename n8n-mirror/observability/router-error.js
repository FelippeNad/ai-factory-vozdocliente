const input = $input.first().json;
const expected = $env.ROUTER_OBSERVED_WORKFLOW_ID;
// Nao aceitar erros de outros workflows/ambientes, nem copiar sua mensagem.
if ($env.CLASSIFIER_ENV !== 'DEV' || typeof expected !== 'string'
    || !/^[A-Za-z0-9_-]{1,64}$/.test(expected) || input.workflow?.id !== expected) return [];
const execution = input.execution || {};
// Esta parada ja teve evento terminal/alerta no ramo de erro, inclusive em modo manual.
if (execution.lastNodeExecuted === 'Interromper com seguranca') return [];
const stages = { 'Webhook Review': 'received', 'Sanitizar PII': 'sanitization',
  'Preparar deduplicacao DEV': 'precheck', 'Airtable Precheck DEV': 'precheck',
  'Validar busca e restaurar texto': 'precheck', 'LLM DEV': 'llm', 'Parse + Merge': 'llm',
  'Airtable Buscar review_id': 'final_dedup', 'Validar busca final DEV': 'final_dedup',
  'Airtable DEV': 'persistence', 'Slack DEV': 'business_slack' };
const stage = stages[execution.lastNodeExecuted] || 'unknown';
// Error Trigger nao fornece contagens/timing confiaveis: desconhecido e null, nao zero.
const parentKnown = /^\d{1,30}$/.test(String(execution.id));
const handlerId = String($execution.id);
if (!parentKnown && !/^\d{1,30}$/.test(handlerId)) return [];
const ctx = { run_id: parentKnown ? 'router-' + execution.id : 'router-error-' + handlerId,
  received: parentKnown ? 1 : null, started_ms: null, stage_ms: {},
  persisted: null, llm_calls_attempted: null, llm_responses: null, classification_valid: null,
  prompt_tokens: null, completion_tokens: null };
const report = obsEmit(ctx, stage, 'failure', 'WORKFLOW_INTERRUPTED', true);
return [{ json: { report }, pairedItem: { item: 0 } }];
