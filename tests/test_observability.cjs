#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { simulate, runNode, record, ENV } = require('./test_retention.cjs');
const ALERT_ENV = { ...ENV, RETENTION_ALERTS_ENABLED: 'true', RETENTION_SLACK_DEV_CHANNEL_ID: 'C00000000' };
const failSchema = (request, kind) => kind === 'schema'
  ? { statusCode: 503, body: { error: 'PII pessoa@example.invalid' }, headers: { authorization: 'SECRET_SYNTHETIC' } } : undefined;

function runTests(report = console.log) {
  const tests = [], test = (name, fn) => tests.push({ name, fn });
  test('sucesso sintetico com numeros de retention-6: evento, contadores e latencia', () => {
    const run = simulate({ env: ALERT_ENV, pages: [
      { records: [record(1), record(2)], offset: 'page-2' },
      { records: [record(3, '2026-11-01T00:00:00Z'), record(4, '2026-11-01T00:00:00Z')] },
    ] });
    const obs = run.summary.observability;
    assert.equal(run.summary.analyzed, 4); assert.equal(run.summary.eligible, 2); assert.equal(run.summary.pages, 2);
    assert.equal(run.summary.audit_finalized, true); assert.equal(run.summary.deleted, 0);
    assert.equal(obs.event.status, 'success'); assert.equal(obs.event.error_code, 'NONE');
    assert.deepEqual(obs.metrics, { runs_total: 1, runs_success: 1, runs_failure: 0, processed: 4, failures: 0,
      latency_ms: Date.parse(run.summary.finished_at) - Date.parse(run.summary.started_at) });
    assert.ok(obs.metrics.latency_ms > 0); assert.equal(obs.event.duration_ms, obs.metrics.latency_ms);
    assert.equal(run.notifications.length, 0); assert.equal(run.logs.length, 1);
  });
  test('falha reproduzivel: um alerta permitido e sem PII; retencao permanece bloqueada', () => {
    const run = simulate({ env: ALERT_ENV, handler: failSchema });
    assert.equal(run.summary.status, 'blocked'); assert.equal(run.summary.deleted, 0);
    assert.equal(run.summary.observability.metrics.runs_failure, 1);
    assert.equal(run.summary.observability.event.error_code, 'HTTP_5XX');
    assert.equal(run.notifications.length, 1); assert.equal(run.requests.length, 1);
    assert.equal(run.notifications[0].url, 'https://slack.com/api/chat.postMessage');
    assert.equal(run.notifications[0].method, 'POST');
    assert.deepEqual(Object.keys(run.notifications[0].body).sort(), ['channel', 'mrkdwn', 'text', 'unfurl_links', 'unfurl_media']);
    assert.ok(run.notifications[0].body.text.includes('retention-1001'));
    assert.equal(run.summary.observability.alert_status, 'sent'); // Confirmacao SIMULADA pelo helper.
    assert.equal(run.logs.length, 2);
    const output = JSON.stringify([run.logs, run.notifications, run.summary.observability]);
    for (const forbidden of ['pessoa@example.invalid', 'SECRET_SYNTHETIC', 'headers', 'processed_at', 'preview', 'rec000'])
      assert.ok(!output.includes(forbidden));
  });
  test('alerta desligado por padrao nao faz HTTP Slack', () => {
    const run = simulate({ handler: failSchema });
    assert.equal(run.notifications.length, 0); assert.equal(run.summary.observability.alert_status, 'disabled');
  });
  for (const bad of [{ RETENTION_ENV: 'PROD' }, { RETENTION_ENV: '' }, { RETENTION_SLACK_DEV_CHANNEL_ID: '' },
    { RETENTION_SLACK_DEV_CHANNEL_ID: '#cx-alertas' }, { RETENTION_SLACK_DEV_CHANNEL_ID: 'C00000000\n' }]) {
    test(`configuracao de alerta invalida: ${Object.keys(bad)[0]} ${JSON.stringify(Object.values(bad)[0])}`, () => {
      const run = simulate({ env: { ...ALERT_ENV, ...bad }, handler: failSchema });
      assert.equal(run.notifications.length, 0);
      assert.equal(run.summary.observability.alert_error_code, 'ALERT_CONFIG_INVALID');
    });
  }
  for (const response of [{ statusCode: 200, body: { ok: false, error: 'email@example.invalid' } },
    { statusCode: 429 }, { statusCode: 500, body: { error: 'SECRET_SYNTHETIC' } },
    { error: { message: 'email@example.invalid' } }]) {
    test(`falha de entrega Slack ${response.statusCode ?? 'rede'} tratada sem mensagem externa/retry`, () => {
      const run = simulate({ env: ALERT_ENV, handler: (request, kind) => kind === 'slack' ? response : failSchema(request, kind) });
      assert.equal(run.notifications.length, 1); assert.equal(run.summary.status, 'blocked');
      assert.equal(run.summary.observability.alert_status, 'failed');
      assert.equal(run.summary.observability.alert_error_code, 'SLACK_DELIVERY_FAILED');
      assert.equal(run.logs.at(-1).error_code, 'SLACK_DELIVERY_FAILED');
      assert.ok(!JSON.stringify([run.logs, run.summary]).includes('example.invalid'));
      assert.ok(!JSON.stringify([run.logs, run.summary]).includes('SECRET_SYNTHETIC'));
    });
  }
  test('preview correlacionavel e texto indevido nao entram em logs/Slack', () => {
    const logs = [];
    const summary = { run_id: 'retention-6', status: 'partial', failures: 1, analyzed: 4,
      started_at: '2026-11-02T12:00:00Z', finished_at: '2026-11-02T12:00:02Z', error_codes: ['DATE_INVALID'],
      preview: [{ record_id: 'rec00000000000001' }], review_text: 'pessoa@example.invalid', token: 'SECRET_SYNTHETIC' };
    const result = runNode('Observabilidade DEV', summary, ALERT_ENV, undefined,
      { console: { log: value => logs.push(value) } });
    const output = JSON.stringify([logs, result.slack_body]);
    for (const forbidden of ['rec000', 'example.invalid', 'SECRET_SYNTHETIC', 'preview', 'review_text']) assert.ok(!output.includes(forbidden));
    assert.equal(result.event.duration_ms, 2000);
    assert.deepEqual(Object.keys(logs[0]).sort(), ['duration_ms', 'error_code', 'metrics', 'run_id', 'stage', 'status']);
  });
  test('run_id, datas e codigos arbitrarios nao sao interpolados', () => {
    const logs = [];
    const result = runNode('Observabilidade DEV', { run_id: 'email@example.invalid', status: 'SECRET_SYNTHETIC',
      error_codes: ['SECRET_SYNTHETIC'], started_at: 'invalid', finished_at: 'invalid' }, ALERT_ENV, undefined,
      { console: { log: value => logs.push(value) } });
    assert.equal(result.event.error_code, 'OBS_INPUT_INVALID'); assert.equal(result.event.duration_ms, null);
    assert.equal(result.event.run_id, 'retention-unknown');
    assert.ok(!JSON.stringify([logs, result.slack_body]).includes('SECRET_SYNTHETIC'));
    assert.ok(!JSON.stringify([logs, result.slack_body]).includes('example.invalid'));
  });
  test('DEMO demonstra partial e entrega simulada sem HTTP, mesmo com ambiente externo PROD', () => {
    const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '../n8n-mirror/workflows/vozdocliente-retencao-demo.json'), 'utf8'));
    const run = simulate({ workflow, env: { RETENTION_ENV: 'PROD' } });
    assert.equal(run.requests.length, 0); assert.equal(run.notifications.length, 0);
    assert.equal(run.summary.observability.alert_status, 'simulated');
    assert.equal(run.summary.observability.event.error_code, 'DATE_INVALID');
    assert.equal(run.summary.observability.metrics.runs_failure, 1);
  });
  let failed = 0;
  for (const { name, fn } of tests) {
    try { fn(); report(`[OK] ${name}`); }
    catch (error) { failed++; report(`[FALHA] ${name}: ${error.message}`); }
  }
  report(`RESULTADO: ${tests.length - failed} passaram, ${failed} falharam`);
  return { passed: tests.length - failed, failed, total: tests.length };
}
module.exports = { runTests, ALERT_ENV, failSchema };
if (require.main === module) process.exitCode = runTests().failed ? 1 : 0;
