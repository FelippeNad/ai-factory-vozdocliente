// OBS_CONTRACT e injetado pelo gerador. Nunca inspecionar mensagens/headers externos.
const obsClone = value => JSON.parse(JSON.stringify(value));
const obsCount = value => Number.isSafeInteger(value) && value >= 0 && value <= 1e12 ? value : null;
const obsDuration = start => Number.isFinite(start) && Date.now() >= start ? Date.now() - start : null;
function obsContext(previous) {
  const ctx = obsClone(previous ? $(previous).first().json._obs : $input.first().json._obs);
  if (!ctx || !/^router-\d{1,30}$/.test(ctx.run_id)) throw new Error('Contexto de observabilidade invalido.');
  return ctx;
}
function obsPrice(value) {
  if (typeof value !== 'string' || !/^(?:0|[1-9]\d*)(?:\.\d{1,8})?$/.test(value)) return null;
  const number = Number(value);
  return number > 0 && number <= 1e6 ? number : null;
}
function obsUsage(ctx) {
  const usage = $('LLM DEV').first().json.usage;
  ctx.llm_responses = 1;
  ctx.prompt_tokens = obsCount(usage?.prompt_tokens);
  ctx.completion_tokens = obsCount(usage?.completion_tokens);
  return ctx;
}
function obsMetrics(ctx, terminal, status) {
  const inputPrice = obsPrice($env.OBS_LLM_INPUT_USD_PER_MILLION);
  const outputPrice = obsPrice($env.OBS_LLM_OUTPUT_USD_PER_MILLION);
  const cost = ctx.llm_calls_attempted === 0 ? 0
    : ctx.prompt_tokens !== null && ctx.completion_tokens !== null && inputPrice !== null && outputPrice !== null
      ? (ctx.prompt_tokens * inputPrice + ctx.completion_tokens * outputPrice) / 1e6 : null;
  return { runs_total: terminal ? 1 : 0, runs_success: terminal && status === 'success' ? 1 : 0,
    runs_duplicate: terminal && status === 'duplicate' ? 1 : 0, runs_failure: terminal && status === 'failure' ? 1 : 0,
    received: terminal ? Object.prototype.hasOwnProperty.call(ctx, 'received') ? ctx.received : 1 : 0,
    persisted: ctx.persisted, llm_calls_attempted: ctx.llm_calls_attempted,
    llm_responses: ctx.llm_responses, classification_valid: ctx.classification_valid,
    prompt_tokens: ctx.prompt_tokens, completion_tokens: ctx.completion_tokens, estimated_cost_usd: cost };
}
function obsCanonical(raw) {
  const invalid = () => { throw new Error('Evento de observabilidade invalido.'); };
  const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|');
  if (!exact(raw, OBS_CONTRACT.fields) || raw.schema !== OBS_CONTRACT.schema
      || !/^router-(?:\d{1,30}|error-\d{1,30})$/.test(raw.run_id)
      || !['execution', 'error_handler'].includes(raw.correlation)
      || (raw.correlation === 'error_handler') !== raw.run_id.startsWith('router-error-')
      || !OBS_CONTRACT.sources.includes(raw.source) || !['stage', 'run'].includes(raw.kind)
      || !OBS_CONTRACT.stages.includes(raw.stage) || !OBS_CONTRACT.statuses.includes(raw.status)
      || !OBS_CONTRACT.codes.includes(raw.error_code)
      || raw.event_id !== [raw.run_id, raw.kind, raw.stage, raw.status].join(':')
      || typeof raw.at !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(raw.at)
      || !Number.isFinite(Date.parse(raw.at)) || new Date(raw.at).toISOString() !== raw.at
      || !(raw.duration_ms === null || Number.isSafeInteger(raw.duration_ms) && raw.duration_ms >= 0 && raw.duration_ms <= 1e12)
      || raw.kind === 'run' && raw.status === 'started'
      || (raw.status === 'failure') !== (raw.error_code !== 'NONE')
      || !exact(raw.metrics, [...OBS_CONTRACT.counters, ...OBS_CONTRACT.measures])) invalid();
  for (const key of OBS_CONTRACT.counters) if (!(raw.metrics[key] === null || obsCount(raw.metrics[key]) !== null)) invalid();
  const cost = raw.metrics.estimated_cost_usd;
  if (!(cost === null || typeof cost === 'number' && Number.isFinite(cost) && cost >= 0 && cost <= 1e12)) invalid();
  if (raw.metrics.classification_valid !== null && raw.metrics.llm_responses !== null
      && raw.metrics.classification_valid > raw.metrics.llm_responses) invalid();
  if (raw.metrics.llm_responses !== null && raw.metrics.llm_calls_attempted !== null
      && raw.metrics.llm_responses > raw.metrics.llm_calls_attempted) invalid();
  if (raw.metrics.runs_total !== (raw.kind === 'run' ? 1 : 0)
      || raw.metrics.runs_success !== (raw.kind === 'run' && raw.status === 'success' ? 1 : 0)
      || raw.metrics.runs_duplicate !== (raw.kind === 'run' && raw.status === 'duplicate' ? 1 : 0)
      || raw.metrics.runs_failure !== (raw.kind === 'run' && raw.status === 'failure' ? 1 : 0)) invalid();
  return obsClone(raw);
}
function obsEmit(ctx, stage, status, code = 'NONE', terminal = false) {
  const report = obsCanonical({ schema: OBS_CONTRACT.schema,
    event_id: [ctx.run_id, terminal ? 'run' : 'stage', stage, status].join(':'),
    run_id: ctx.run_id, correlation: ctx.run_id.startsWith('router-error-') ? 'error_handler' : 'execution', at: new Date().toISOString(),
    source: $execution.mode === 'offline_simulation' ? 'offline_simulation' : 'n8n',
    kind: terminal ? 'run' : 'stage', stage, status,
    duration_ms: obsDuration(terminal ? ctx.started_ms : ctx.stage_ms[stage]),
    error_code: code, metrics: obsMetrics(ctx, terminal, status) });
  console.log(JSON.stringify(report));
  return report;
}
function obsStart() {
  const id = String($execution.id);
  if (!/^\d{1,30}$/.test(id)) throw new Error('Identificador de execucao invalido.');
  const ctx = { run_id: 'router-' + id, started_ms: Date.now(), stage_ms: { received: Date.now(), sanitization: Date.now() },
    persisted: 0, llm_calls_attempted: 0, llm_responses: 0, classification_valid: 0, prompt_tokens: 0, completion_tokens: 0 };
  obsEmit(ctx, 'received', 'success');
  obsEmit(ctx, 'sanitization', 'started');
  return [{ json: { ...$input.first().json, _obs: ctx }, pairedItem: { item: 0 } }];
}
function obsStep(stage, status, previous) {
  const ctx = obsContext(previous);
  if (status === 'started') {
    ctx.stage_ms[stage] = Date.now();
    if (stage === 'llm') {
      ctx.llm_calls_attempted = 1; ctx.prompt_tokens = null; ctx.completion_tokens = null;
    }
  }
  if (stage === 'llm' && status === 'success') { obsUsage(ctx); ctx.classification_valid = 1; }
  if (stage === 'persistence' && status === 'success') ctx.persisted = 1;
  obsEmit(ctx, stage, status);
  return [{ json: { ...$input.first().json, _obs: ctx }, pairedItem: { item: 0 } }];
}
function obsFinish(status, previous, stage = 'run', code = 'NONE', responseReceived = false) {
  const ctx = obsContext(previous);
  if (responseReceived) obsUsage(ctx);
  const report = obsEmit(ctx, stage, status, code, true);
  // Apenas o evento permitido sai para outro workflow; nenhum payload de negocio.
  return [{ json: { report }, pairedItem: { item: 0 } }];
}
function obsDelivery() {
  const report = obsCanonical($input.first().json.report);
  const id = $env.ROUTER_OBSERVER_WORKFLOW_ID;
  const configured = $env.CLASSIFIER_ENV === 'DEV' && typeof id === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(id);
  return [{ json: { report, send_observation: configured, observer_workflow_id: configured ? id : null }, pairedItem: { item: 0 } }];
}
