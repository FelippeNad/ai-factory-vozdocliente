#!/usr/bin/env node
'use strict';
// Executa os nodes/expressoes do workflow exportado com transporte em memoria.
// Nenhum socket, fetch, token, n8n ou API e usado.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..');
const WORKFLOW = JSON.parse(fs.readFileSync(path.join(ROOT,
  'n8n-mirror/workflows/vozdocliente-retencao-v1.json'), 'utf8'));
const NODES = Object.fromEntries(WORKFLOW.nodes.map(n => [n.name, n]));
const NOW = Date.parse('2026-11-02T12:00:00.000Z');
const BASE = 'app00000000000000', TABLE = 'tbl00000000000001', AUDIT = 'tbl00000000000002';
const ENV = { RETENTION_ENV: 'DEV', RETENTION_DEV_BASE_ID: BASE,
  RETENTION_TABLE_ID: TABLE, RETENTION_AUDIT_TABLE_ID: AUDIT, RETENTION_PAGE_SIZE: '2' };
const DELETE_ENV = { ...ENV, RETENTION_DRY_RUN: 'false', RETENTION_CONFIRM_DEV_BASE_ID: BASE,
  RETENTION_PROTECTED_BASE_IDS: 'app99999999999999', RETENTION_DELETE_CONFIRMATION: 'DELETE_DEV_EXPIRED_REVIEWS' };
const id = n => 'rec' + String(n).padStart(14, '0');
const old = '2026-09-01T00:00:00.000Z';
const record = (n, date = old) => ({ id: id(n), fields: date === undefined ? {} : { processed_at: date } });
const plain = value => JSON.parse(JSON.stringify(value));

function runNode(name, input, env = ENV, now = NOW, extra = {}, workflow = WORKFLOW) {
  class Clock extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  const node = workflow.nodes.find(node => node.name === name);
  return plain(vm.runInNewContext(`(function () { ${node.parameters.jsCode}\n})()`, {
    $input: { first: () => ({ json: input }) }, $env: env, $execution: { id: '1001' },
    Date: Clock, ...extra,
  }, { timeout: 1000 }))[0].json;
}

function schema() {
  const texts = ['run_id', 'mode', 'status', 'error_codes'];
  const dates = ['cutoff', 'started_at', 'updated_at'];
  const numbers = ['retention_days', 'analyzed', 'eligible', 'deleted', 'failures', 'invalid_dates',
    'recent', 'pages', 'attempted', 'skipped_changed', 'unknown_outcome'];
  return { tables: [
    { id: TABLE, name: 'Reviews', fields: [{ name: 'processed_at', type: 'dateTime' }] },
    { id: AUDIT, name: 'RetentionAudit', fields: [
      ...texts.map(name => ({ name, type: 'singleLineText' })),
      ...dates.map(name => ({ name, type: 'dateTime' })),
      ...numbers.map(name => ({ name, type: 'number' })),
    ] },
  ] };
}

// Percorre o grafo real, incluindo IF, expressoes HTTP e o retorno de cada loop.
function simulate({ env = ENV, pages = [{ records: [] }], handler, beforeGuard, workflow = WORKFLOW } = {}) {
  let current = 'Agenda de retencao', value = {}, previous, clock = NOW;
  const requests = [], audits = [], trace = [];
  let page = 0;
  const expression = (text, json) => vm.runInNewContext(text.slice(3, -2).trim(), { $json: json }, { timeout: 1000 });
  for (let step = 0; step < 2000; step++) {
    const node = workflow.nodes.find(node => node.name === current); trace.push(current);
    let branch = 0;
    if (node.type === 'n8n-nodes-base.code') {
      if (current === 'Validar operacao DEV') beforeGuard?.(value.state, env);
      value = runNode(current, value, env, clock, {
        $: name => { assert.equal(name, 'Validar operacao DEV'); return { item: { json: plain(previous) } }; },
      }, workflow);
      if (current === 'Validar operacao DEV') previous = plain(value);
    } else if (node.type === 'n8n-nodes-base.if') {
      const condition = node.parameters.conditions.conditions[0];
      branch = expression(condition.leftValue, value) ? 0 : 1;
    } else if (node.type === 'n8n-nodes-base.wait') clock += 1000;
    else if (node.type === 'n8n-nodes-base.httpRequest') {
      const request = { method: expression(node.parameters.method, value),
        url: expression(node.parameters.url, value) };
      if (expression(node.parameters.sendBody, value)) request.body = JSON.parse(expression(node.parameters.jsonBody, value));
      requests.push(plain(request));
      const kind = value.state.action;
      const custom = handler?.(request, kind, value.state, requests);
      if (custom !== undefined) value = custom;
      else if (kind === 'schema') value = { statusCode: 200, body: schema() };
      else if (kind === 'list') value = { statusCode: 200, body: pages[page++] };
      else if (kind === 'recheck') value = { statusCode: 200, body: { records: [record(1 + value.state.index)] } };
      else if (kind === 'delete') value = { statusCode: 200, body: { id: value.state.candidates[value.state.index].id, deleted: true } };
      else if (kind === 'audit_create' || kind === 'audit_update') {
        audits.push(plain(request.body.fields));
        value = { statusCode: 200, body: { id: id(999), fields: plain(request.body.fields) } };
      } else throw Error('Operacao inesperada no mock');
    }
    const links = workflow.connections[current]?.main?.[branch];
    if (!links?.length) return { summary: value, requests, audits, trace };
    assert.equal(links.length, 1, 'Fluxo deve ser sequencial');
    current = links[0].node;
  }
  throw Error('Loop nao terminou');
}

function runTests(report = console.log) {
  const tests = [];
  const test = (name, fn) => tests.push({ name, fn });
  const deletes = run => run.requests.filter(r => r.method === 'DELETE');
  test('workflow inativo, Schedule diario e fuso explicito', () => {
    assert.equal(WORKFLOW.active, false);
    assert.equal(WORKFLOW.settings.timezone, 'America/Sao_Paulo');
    assert.equal(NODES['Agenda de retencao'].parameters.rule.interval[0].expression, '0 3 * * *');
    assert.equal(WORKFLOW.nodes.filter(n => n.type.endsWith('.httpRequest')).length, 1);
    assert.ok(!JSON.stringify(WORKFLOW).includes('credentials'));
  });
  test('dry run padrao, preview e auditoria agregada', () => {
    const run = simulate({ pages: [{ records: [record(1), record(2, '2026-11-01T00:00:00Z')] }] });
    assert.equal(run.summary.mode, 'DRY_RUN'); assert.equal(run.summary.retention_days, 30);
    assert.equal(run.summary.status, 'dry_run'); assert.equal(run.summary.analyzed, 2);
    assert.equal(run.summary.eligible, 1); assert.equal(run.summary.deleted, 0);
    assert.equal(run.summary.audit_finalized, true);
    assert.deepEqual(run.summary.preview, [{ record_id: id(1), processed_at: old }]);
    assert.equal(deletes(run).length, 0); assert.equal(run.audits.length, 1);
    assert.ok(!JSON.stringify(run.audits).includes(id(1)));
  });
  test('limite temporal estrito, nao exclui igualdade, preserva UTC e offset', () => {
    const run = simulate({ env: { ...ENV, RETENTION_PAGE_SIZE: '100' }, pages: [{ records: [
      record(1, '2026-10-03T11:59:59.999Z'), record(2, '2026-10-03T12:00:00.000Z'),
      record(3, '2026-10-03T09:00:00-03:00'), record(4, '2026-11-01T00:00:00Z'),
    ] }] });
    assert.equal(run.summary.eligible, 1); assert.equal(run.summary.recent, 3);
  });
  const invalidDates = [null, '', 123, {}, '2026-02-30T00:00:00Z', '2026-02-29T00:00:00Z',
    '2026-13-01T00:00:00Z', '2026-01-00T00:00:00Z', '2026-01-01T24:00:00Z',
    '2026-01-01T00:60:00Z', '2026-01-01T00:00:60Z', '01/01/2026', '2026-01-01',
    '2026-01-01T00:00:00', '2026-01-01T00:00:00+15:00', '2026-01-01T00:00:00+14:30',
    '2026-01-01T00:00:00+01:60', '2027-01-01T00:00:00Z'];
  invalidDates.forEach((date, i) => test(`data invalida/futura ${i}: nao elegivel`, () => {
    const run = simulate({ pages: [{ records: [record(1, date)] }] });
    assert.equal(run.summary.eligible, 0); assert.equal(run.summary.invalid_dates, 1);
    assert.equal(run.summary.failures, 1); assert.equal(deletes(run).length, 0);
  }));
  test('campo ausente e ano bissexto', () => {
    const run = simulate({ pages: [{ records: [record(1, '2024-02-29T00:00:00.000Z'), { id: id(2), fields: {} }] }] });
    assert.equal(run.summary.eligible, 1); assert.equal(run.summary.invalid_dates, 1);
  });
  test('politica configuravel', () => {
    const run = simulate({ env: { ...ENV, RETENTION_DAYS: '90' }, pages: [{ records: [record(1)] }] });
    assert.equal(run.summary.retention_days, 90); assert.equal(run.summary.eligible, 0);
  });
  const badConfigs = [{ RETENTION_ENV: 'PROD' }, { RETENTION_ENV: '' }, { RETENTION_DRY_RUN: 'FALSE' },
    { RETENTION_DRY_RUN: '0' }, { RETENTION_DRY_RUN: 'false' }, { RETENTION_DAYS: '0' },
    { RETENTION_DAYS: '-1' }, { RETENTION_DAYS: '1.5' }, { RETENTION_DAYS: ' 30 ' },
    { RETENTION_DAYS: '3651' }, { RETENTION_MAX_DELETE: '101' }, { RETENTION_MAX_PAGES: '51' },
    { RETENTION_MAX_ANALYZED: '5001' }, { RETENTION_PAGE_SIZE: '101' }, { RETENTION_DEV_BASE_ID: 'evil.invalid' },
    { RETENTION_PROTECTED_BASE_IDS: BASE }, { RETENTION_AUDIT_TABLE_ID: TABLE }, { RETENTION_TABLE_ID: '' }];
  badConfigs.forEach((bad, i) => test(`configuracao invalida ${i}: nenhuma chamada`, () => {
    const run = simulate({ env: { ...ENV, ...bad } });
    assert.equal(run.requests.length, 0); assert.equal(run.summary.status, 'blocked');
    assert.deepEqual(run.summary.error_codes, ['CONFIG_INVALID']);
  }));
  test('DEV nao configurado bloqueia inclusive dry run', () => assert.equal(simulate({ env: {} }).requests.length, 0));
  for (const bad of [{ RETENTION_CONFIRM_DEV_BASE_ID: 'app11111111111111' },
    { RETENTION_PROTECTED_BASE_IDS: '' }, { RETENTION_DELETE_CONFIRMATION: 'yes' }]) {
    test(`bloqueio de confirmacao de exclusao ${Object.keys(bad)[0]}`, () => {
      assert.equal(simulate({ env: { ...DELETE_ENV, ...bad } }).requests.length, 0);
    });
  }
  test('paginacao completa e offset codificado; somente processed_at solicitado', () => {
    const run = simulate({ pages: [{ records: [record(1), record(2)], offset: 'itr/page+2=' }, { records: [record(3)] }] });
    assert.equal(run.summary.pages, 2); assert.equal(run.summary.analyzed, 3);
    assert.equal(run.summary.eligible, 3); assert.equal(run.summary.scan_complete, true);
    const url = new URL(run.requests[2].url);
    assert.equal(url.searchParams.get('offset'), 'itr/page+2=');
    assert.deepEqual(url.searchParams.getAll('fields[]'), ['processed_at']);
  });
  for (const [name, pages] of [
    ['offset repetido', [{ records: [record(1)], offset: 'abc' }, { records: [record(2)], offset: 'abc' }]],
    ['offset invalido', [{ records: [record(1)], offset: '\n' }]],
    ['offset vazio', [{ records: [record(1)], offset: '' }]],
    ['pagina vazia com offset', [{ records: [], offset: 'abc' }]],
    ['registro repetido', [{ records: [record(1)], offset: 'abc' }, { records: [record(1)] }]],
    ['id invalido', [{ records: [{ id: 'teste@example.invalid', fields: {} }] }]],
    ['resposta sem records', [{}]],
  ]) test(name, () => {
    const run = simulate({ env: DELETE_ENV, pages });
    assert.equal(run.summary.status, 'blocked'); assert.equal(deletes(run).length, 0);
  });
  for (const limit of [{ RETENTION_MAX_PAGES: '1' }, { RETENTION_MAX_ANALYZED: '2' }]) {
    test(`limite de scan ${Object.keys(limit)[0]} bloqueia lote inteiro`, () => {
      const run = simulate({ env: { ...DELETE_ENV, ...limit }, pages: [{ records: [record(1), record(2)], offset: 'abc' }] });
      assert.equal(deletes(run).length, 0); assert.ok(run.summary.error_codes.includes('SCAN_LIMIT'));
      assert.equal(run.summary.audit_finalized, true);
    });
  }
  test('limite de exclusao nao trunca silenciosamente', () => {
    const run = simulate({ env: { ...DELETE_ENV, RETENTION_MAX_DELETE: '1' }, pages: [{ records: [record(1), record(2)] }] });
    assert.equal(deletes(run).length, 0); assert.ok(run.summary.error_codes.includes('DELETE_LIMIT'));
  });
  test('exclusao DEV explicita: auditoria anterior e checkpoint por registro', () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1), record(2)] }] });
    assert.equal(deletes(run).length, 2); assert.equal(run.summary.deleted, 2);
    assert.equal(run.summary.attempted, 2); assert.equal(run.summary.status, 'completed');
    assert.deepEqual(run.requests.map(r => r.method), ['GET', 'GET', 'POST', 'GET', 'DELETE', 'PATCH', 'GET', 'DELETE', 'PATCH']);
    assert.deepEqual(run.audits.map(a => a.status), ['planned', 'running', 'completed']);
    assert.deepEqual(run.audits.map(a => a.deleted), [0, 1, 2]); assert.deepEqual(run.summary.preview, []);
  });
  test('todas as paginas precedem o primeiro DELETE', () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1)], offset: 'abc' }, { records: [record(2)] }] });
    assert.deepEqual(run.requests.slice(0, 4).map(r => r.method), ['GET', 'GET', 'GET', 'POST']);
    assert.equal(run.summary.deleted, 2);
  });
  for (const [name, response] of [
    ['alterada', { records: [record(1, '2026-11-01T00:00:00Z')] }],
    ['alterada mas ainda antiga', { records: [record(1, '2026-08-01T00:00:00Z')] }],
    ['removida por outro processo', { records: [] }],
    ['data invalida na releitura', { records: [record(1, 'invalida')] }],
  ]) test(`releitura ${name} impede DELETE`, () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1)] }],
      handler: (r, kind) => kind === 'recheck' ? { statusCode: 200, body: response } : undefined });
    assert.equal(deletes(run).length, 0); assert.equal(run.summary.skipped_changed, 1);
  });
  for (const phase of ['schema', 'list', 'audit_create', 'recheck', 'delete', 'audit_update']) {
    for (const code of [401, 429, 500, null]) test(`falha ${phase} ${code} encerra sem repeticao`, () => {
      const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1), record(2)] }],
        handler: (r, kind) => kind === phase ? (code === null ? { error: { message: 'PII teste@example.invalid' } }
          : { statusCode: code, body: { error: 'PII teste@example.invalid' } }) : undefined });
      assert.equal(run.summary.status, 'blocked'); assert.ok(run.summary.failures > 0);
      assert.ok(deletes(run).length <= 1); assert.ok(!JSON.stringify(run.summary).includes('example.invalid'));
      assert.ok(!JSON.stringify(run.audits).includes('example.invalid'));
      if (phase === 'delete' && (code === null || code === 500)) assert.equal(run.summary.unknown_outcome, 1);
    });
  }
  test('schema date-only bloqueia qualquer exclusao', () => {
    const bad = schema(); bad.tables[0].fields[0].type = 'date';
    const run = simulate({ env: DELETE_ENV, handler: (r, kind) => kind === 'schema' ? { statusCode: 200, body: bad } : undefined });
    assert.equal(run.requests.length, 1); assert.ok(run.summary.error_codes.includes('SCHEMA_INVALID'));
  });
  test('auditoria com schema incompleto bloqueia', () => {
    const bad = schema(); bad.tables[1].fields.pop();
    const run = simulate({ handler: (r, kind) => kind === 'schema' ? { statusCode: 200, body: bad } : undefined });
    assert.equal(run.requests.length, 1); assert.equal(run.summary.audit_persisted, false);
  });
  test('auditoria nao confirmada impede DELETE', () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1)] }],
      handler: (r, kind) => kind === 'audit_create' ? { statusCode: 200, body: { id: id(999), fields: {} } } : undefined });
    assert.equal(deletes(run).length, 0); assert.equal(run.summary.audit_persisted, false);
  });
  test('checkpoint com metricas divergentes impede proxima exclusao', () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1), record(2)] }],
      handler: (r, kind) => kind === 'audit_update' ? { statusCode: 200,
        body: { id: 'rec00000000000999', fields: { ...r.body.fields, deleted: 0 } } } : undefined });
    assert.equal(deletes(run).length, 1); assert.equal(run.summary.deleted, 1);
    assert.equal(run.summary.audit_finalized, false); assert.ok(run.summary.error_codes.includes('AUDIT_FAILED'));
  });
  test('campo vazio omitido pelo Airtable nao invalida auditoria', () => {
    const run = simulate({ handler: (r, kind) => {
      if (kind === 'audit_create') {
        const fields = { ...r.body.fields }; delete fields.error_codes;
        return { statusCode: 200, body: { id: 'rec00000000000999', fields } };
      }
    } });
    assert.equal(run.summary.audit_finalized, true); assert.equal(run.summary.failures, 0);
  });
  test('DELETE nao confirmado contabiliza desfecho desconhecido', () => {
    const run = simulate({ env: DELETE_ENV, pages: [{ records: [record(1)] }],
      handler: (r, kind) => kind === 'delete' ? { statusCode: 200, body: { id: id(1), deleted: false } } : undefined });
    assert.equal(run.summary.deleted, 0); assert.equal(run.summary.unknown_outcome, 1);
  });
  test('mudanca para dry run antes do DELETE bloqueia', () => {
    const run = simulate({ env: { ...DELETE_ENV }, pages: [{ records: [record(1)] }],
      beforeGuard: (s, env) => { if (s.action === 'delete') env.RETENTION_DRY_RUN = 'true'; } });
    assert.equal(deletes(run).length, 0); assert.ok(run.summary.error_codes.includes('GUARD_BLOCKED'));
  });
  test('prazo maximo interrompe scan e tenta auditoria final', () => {
    const run = simulate({ pages: [{ records: [record(1)] }],
      beforeGuard: s => { if (s.action === 'list') s.deadline = NOW - 1; } });
    assert.equal(deletes(run).length, 0); assert.ok(run.summary.error_codes.includes('TIME_LIMIT'));
    assert.equal(run.summary.audit_finalized, true);
  });
  test('guard nao aceita DELETE injetado em dry run', () => {
    const initial = runNode('Motor de retencao', {});
    initial.state.action = 'delete';
    const result = runNode('Validar operacao DEV', initial);
    assert.equal(result.has_request, false); assert.equal(result.state.blocked, true);
  });
  test('PII recebida indevidamente nao persiste no estado, resumo ou auditoria', () => {
    const item = record(1); item.fields.review_text = 'teste@example.invalid'; item.fields.customer_name = 'Pessoa Sintetica';
    const run = simulate({ pages: [{ records: [item] }] });
    assert.ok(!JSON.stringify(run.summary).includes('Pessoa Sintetica'));
    assert.ok(!JSON.stringify(run.audits).includes('example.invalid'));
  });
  test('demo exportada percorre o grafo sem HTTP ou configuracao externa', () => {
    const demo = JSON.parse(fs.readFileSync(path.join(ROOT, 'n8n-mirror/workflows/vozdocliente-retencao-demo.json'), 'utf8'));
    assert.equal(demo.active, false);
    assert.equal(demo.nodes.filter(node => node.type.endsWith('.httpRequest')).length, 0);
    const run = simulate({ workflow: demo, env: { RETENTION_DRY_RUN: 'false', RETENTION_ENV: 'PROD' } });
    assert.equal(run.requests.length, 0); assert.equal(run.summary.mode, 'DRY_RUN');
    assert.equal(run.summary.analyzed, 6); assert.equal(run.summary.eligible, 2);
    assert.equal(run.summary.deleted, 0); assert.equal(run.summary.invalid_dates, 2);
    assert.equal(run.summary.pages, 3); assert.equal(run.summary.audit_finalized, true);
    assert.equal(run.summary.status, 'partial');
  });
  let failed = 0;
  for (const { name, fn } of tests) {
    try { fn(); report(`[OK] ${name}`); }
    catch (error) { failed++; report(`[FALHA] ${name}: ${error.message}`); }
  }
  const result = { passed: tests.length - failed, failed, total: tests.length };
  report(`RESULTADO: ${result.passed} passaram, ${failed} falharam`);
  return result;
}

module.exports = { runTests, simulate, schema, record, ENV, DELETE_ENV };
if (require.main === module) process.exitCode = runTests().failed ? 1 : 0;
