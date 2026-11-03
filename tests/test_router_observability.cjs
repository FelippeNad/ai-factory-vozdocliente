'use strict';
const assert = require('node:assert/strict');
const { simulator, input, OBS_ENV } = require('./router_observability_harness.cjs');
const tests = [], test = (name, run) => tests.push([name, run]);
const terminal = run => run.logs.filter(e => e.kind === 'run');
function privateOutputs(run) {
  const value = JSON.stringify([run.logs, run.notifications]);
  for (const forbidden of ['example.invalid', 'SECRET_SYNTHETIC', 'review_text', 'customer_name', 'SYNTH-', 'rec000', 'Authorization'])
    assert.ok(!value.includes(forbidden), forbidden);
}
test('nova: etapas, correlacao, uso e persistencia; nenhum alerta de falha', () => {
  const run = simulator(), result = run.run();
  assert.equal(result.ok, true); assert.equal(run.counts.llm, 1); assert.equal(run.counts.create, 1);
  assert.equal(run.counts.alerts, 0); assert.equal(terminal(run).length, 1);
  const report = terminal(run)[0]; assert.equal(report.status, 'success');
  assert.equal(report.metrics.llm_calls_attempted, 1); assert.equal(report.metrics.llm_responses, 1);
  assert.equal(report.metrics.classification_valid, 1); assert.equal(report.metrics.persisted, 1);
  assert.equal(report.metrics.prompt_tokens, 100); assert.equal(report.metrics.completion_tokens, 20);
  assert.equal(report.metrics.estimated_cost_usd, null); assert.ok(report.duration_ms >= 0);
  assert.ok(run.logs.filter(e => e.schema).every(e => e.run_id === 'router-600001'));
  for (const stage of ['received', 'sanitization', 'precheck', 'llm', 'final_dedup', 'persistence'])
    assert.ok(run.logs.some(e => e.stage === stage && e.status === 'success'));
  privateOutputs(run);
});
test('duplicata: zero nova chamada LLM/persistencia/alerta e evento terminal unico', () => {
  const run = simulator(); run.run(input(), 1); run.run(input(), 2);
  assert.equal(run.counts.llm, 1); assert.equal(run.counts.create, 1); assert.equal(run.counts.alerts, 0);
  const report = terminal(run).at(-1);
  assert.equal(report.status, 'duplicate'); assert.equal(report.metrics.runs_duplicate, 1);
  assert.equal(report.metrics.llm_calls_attempted, 0); assert.equal(report.metrics.estimated_cost_usd, 0);
  privateOutputs(run);
});
test('deduplicacao final: duplicata surgida durante o LLM impede persistencia', () => {
  const run = simulator({ malformed: { 'Airtable Buscar review_id': { statusCode: 200, body: {
    records: [{ id: 'rec00000000000099', fields: { review_id: 'SYNTH-0001' } }] } } } });
  assert.equal(run.run().ok, true); const report = terminal(run)[0];
  assert.equal(report.status, 'duplicate'); assert.equal(report.metrics.llm_calls_attempted, 1);
  assert.equal(run.counts.create, 0); assert.equal(run.counts.alerts, 0); privateOutputs(run);
});
test('120 entradas: classificacoes e registros identicos ao otimizado anterior', () => {
  const { optimized, makeLoad, runLoad, saved } = require('./router_optimization_harness.cjs');
  class FixedDate extends Date {
    constructor(...args) { super(...(args.length ? args : ['2026-11-02T12:00:00.000Z'])); }
    static now() { return Date.parse('2026-11-02T12:00:00.000Z'); }
  }
  const load = makeLoad(), before = runLoad(optimized, load), after = simulator({ DateType: FixedDate });
  load.forEach((payload, i) => assert.equal(after.run(payload, i + 1).ok, true));
  const actual = [...after.records.values()].map(record => record.fields).sort((a, b) => a.review_id.localeCompare(b.review_id));
  assert.deepEqual(actual, saved(before)); assert.equal(after.counts.llm, 30);
  assert.equal(terminal(after).filter(e => e.status === 'success').length, 30);
  assert.equal(terminal(after).filter(e => e.status === 'duplicate').length, 90);
  assert.equal(after.counts.alerts, 0); privateOutputs(after);
});
const failures = {
  'Sanitizar PII': ['SANITIZATION_FAILED', 0], 'Preparar deduplicacao DEV': ['DEV_CONFIG_INVALID', 0],
  'Airtable Precheck DEV': ['PRECHECK_HTTP_FAILED', 0], 'Validar busca e restaurar texto': ['PRECHECK_INVALID', 0],
  'LLM DEV': ['LLM_HTTP_FAILED', 1], 'Parse + Merge': ['CLASSIFICATION_INVALID', 1],
  'Airtable Buscar review_id': ['FINAL_DEDUP_HTTP_FAILED', 1], 'Validar busca final DEV': ['FINAL_DEDUP_INVALID', 1],
  'Airtable DEV': ['PERSISTENCE_HTTP_FAILED', 1], 'Slack DEV': ['BUSINESS_SLACK_FAILED', 1],
};
for (const [name, [code, calls]] of Object.entries(failures)) test(`falha em ${name}: evento sem PII, alerta e parada segura`, () => {
  const run = simulator({ unexpected: { [name]: true } });
  // A fixture de sentimento negativo garante a passagem pelo Slack de negocio.
  const payload = input();
  if (name === 'Slack DEV') {
    const { semantics } = require('./router_optimization_harness.cjs');
    payload.review_text = semantics.find(s => s.expected.sentiment === 'negativo').original;
  }
  const result = run.run(payload);
  assert.equal(result.ok, false); assert.equal(result.terminal, 'Interromper com seguranca');
  const report = terminal(run).at(-1); assert.equal(report.status, 'failure'); assert.equal(report.error_code, code);
  assert.equal(report.metrics.llm_calls_attempted, calls); assert.equal(run.counts.alerts, 1);
  assert.ok(run.notifications[0].text.startsWith('[DEV][P1]'));
  if (calls === 0) { assert.equal(run.counts.llm, 0); assert.equal(run.counts.create, 0); }
  privateOutputs(run);
});
test('erro HTTP realista no precheck e capturado mesmo com execution.mode manual', () => {
  const run = simulator({ executionMode: 'manual', fail: { 'Airtable Precheck DEV': true } });
  const result = run.run();
  assert.equal(result.ok, false); assert.equal(run.counts.llm, 0); assert.equal(run.counts.create, 0);
  assert.equal(terminal(run)[0].source, 'n8n'); // Harness emula modo manual; nao gerar evidencia real a partir dele.
  assert.equal(terminal(run)[0].error_code, 'PRECHECK_HTTP_FAILED'); privateOutputs(run);
});
test('resposta 200 malformada bloqueia LLM', () => {
  const run = simulator({ malformed: { 'Airtable Precheck DEV': { statusCode: 200, body: { records: null, email: 'pessoa@example.invalid' } } } });
  assert.equal(run.run().ok, false); assert.equal(run.counts.llm, 0);
  assert.equal(terminal(run)[0].error_code, 'PRECHECK_INVALID'); privateOutputs(run);
});
test('resposta LLM invalida: tentativa e resposta conhecidas, validade zero', () => {
  const run = simulator({ malformed: { 'LLM DEV': { choices: [{ message: { content: 'pessoa@example.invalid' } }] } } });
  assert.equal(run.run().ok, false); const metrics = terminal(run)[0].metrics;
  assert.equal(metrics.llm_calls_attempted, 1); assert.equal(metrics.llm_responses, 1);
  assert.equal(metrics.classification_valid, 0); assert.equal(metrics.prompt_tokens, null);
  assert.equal(run.counts.create, 0); privateOutputs(run);
});
test('PII injetada no campo sanitizado nao entra no prompt', () => {
  const run = simulator(); run.run({ ...input(), review_text_sanitized: 'SECRET_SYNTHETIC' });
  assert.equal(run.prompts.length, 1); assert.ok(!run.prompts[0].includes('SECRET_SYNTHETIC')); privateOutputs(run);
});
test('contexto correlacionavel do cliente nao substitui o run_id gerado', () => {
  const run = simulator(); run.run({ ...input(), _obs: { run_id: 'SECRET_SYNTHETIC' } });
  assert.equal(terminal(run)[0].run_id, 'router-600001'); privateOutputs(run);
});
for (const bad of [{ CLASSIFIER_ENV: 'PROD' }, { CLASSIFIER_DEV_BASE_ID: '' }, { CLASSIFIER_DEV_TABLE_ID: '' }])
  test(`configuracao bloqueada: ${Object.keys(bad)[0]}`, () => {
    const run = simulator({ env: { ...OBS_ENV, ...bad } });
    assert.equal(run.run().ok, false); assert.equal(run.counts.lookup, 0); assert.equal(run.counts.llm, 0);
    if (bad.CLASSIFIER_ENV) assert.equal(run.counts.alerts, 0);
    privateOutputs(run);
  });
for (const bad of [{ ROUTER_ALERTS_ENABLED: 'false' }, { CLASSIFIER_SLACK_DEV_CHANNEL_ID: '#canal' }])
  test(`alerta opt-in/fail-closed: ${Object.keys(bad)[0]}`, () => {
    const run = simulator({ env: { ...OBS_ENV, ...bad }, fail: { 'Airtable Precheck DEV': true } });
    assert.equal(run.run().ok, false); assert.equal(run.counts.alerts, 0); privateOutputs(run);
  });
for (const response of [{ statusCode: 200, body: { ok: false, error: 'pessoa@example.invalid' } }, { error: { message: 'SECRET_SYNTHETIC' } }])
  test('entrega Slack falha sem retry nem perda do erro original', () => {
    const run = simulator({ slackResponse: response, fail: { 'Airtable Precheck DEV': true } });
    const result = run.run(); assert.equal(result.ok, false); assert.equal(run.counts.alerts, 1);
    assert.equal(result.outputs['Resultado Router DEV'].alert_status, 'failed');
    assert.ok(run.logs.some(e => e.stage === 'telemetry' && e.error_code === 'OBS_DELIVERY_FAILED'));
    assert.equal(terminal(run)[0].error_code, 'PRECHECK_HTTP_FAILED'); privateOutputs(run);
  });
test('precos sinteticos explicitos: estimativa por uso; ausente nao vira custo zero', () => {
  const run = simulator({ env: { ...OBS_ENV, OBS_LLM_INPUT_USD_PER_MILLION: '2', OBS_LLM_OUTPUT_USD_PER_MILLION: '8' } });
  run.run(); assert.equal(terminal(run)[0].metrics.estimated_cost_usd, .00036);
});
test('observador indisponivel nao libera ramo de erro nem vaza resposta', () => {
  const run = simulator({ env: { ...OBS_ENV, ROUTER_OBSERVER_WORKFLOW_ID: 'missing' }, fail: { 'Airtable Precheck DEV': true } });
  const result = run.run(); assert.equal(result.ok, false); assert.equal(run.counts.llm, 0);
  assert.equal(result.outputs['Resultado Router DEV'].alert_status, 'delivery_failed'); privateOutputs(run);
});
test('Error Trigger: correlacao original, metricas desconhecidas e nenhum texto externo', () => {
  const run = simulator();
  const result = run.error({ workflow: { id: 'router_synthetic' }, execution: { id: '123',
    lastNodeExecuted: 'Airtable Precheck DEV', error: { message: 'pessoa@example.invalid SECRET_SYNTHETIC' } } });
  assert.equal(result.ok, true); const report = terminal(run)[0];
  assert.equal(report.run_id, 'router-123'); assert.equal(report.error_code, 'WORKFLOW_INTERRUPTED');
  assert.equal(report.duration_ms, null); assert.equal(report.metrics.llm_calls_attempted, null);
  assert.equal(run.counts.alerts, 1); privateOutputs(run);
});
for (const change of [{ workflow: { id: 'outro' } }, { execution: { id: '123', lastNodeExecuted: 'Interromper com seguranca' } }])
  test('Error Trigger ignora origem diversa ou parada ja reportada', () => {
    const run = simulator(); run.error({ workflow: { id: 'router_synthetic' }, execution: { id: '123' }, ...change });
    assert.equal(run.logs.length, 0); assert.equal(run.counts.alerts, 0);
  });
for (const execution of [null, { id: 'pessoa@example.invalid' }])
  test('Error Trigger sem ID original: correlacao apenas com handler, nunca inventar volume', () => {
    const run = simulator(); run.error({ workflow: { id: 'router_synthetic' }, execution,
      trigger: { error: { message: 'SECRET_SYNTHETIC' } } });
    const report = terminal(run)[0];
    assert.equal(report.run_id, 'router-error-700001'); assert.equal(report.correlation, 'error_handler');
    assert.equal(report.metrics.received, null); assert.equal(report.metrics.llm_calls_attempted, null);
    assert.equal(run.counts.alerts, 1); privateOutputs(run);
  });
test('observador rejeita campos extras/PII em vez de emitir alerta', () => {
  const first = simulator(); first.run();
  const report = terminal(first)[0]; report.extra = 'pessoa@example.invalid';
  const run = simulator(); const result = run.observe(report);
  assert.equal(result.ok, false); assert.equal(run.counts.alerts, 0); privateOutputs(run);
});
let failed = 0;
for (const [name, run] of tests) {
  try { run(); console.log('[OK] ' + name); }
  catch (error) { failed++; console.error('[FALHA] ' + name + ': ' + error.message); }
}
console.log(`RESULTADO: ${tests.length - failed} passaram, ${failed} falharam`);
process.exitCode = failed ? 1 : 0;
