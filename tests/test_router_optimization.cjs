#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const { baseline, optimized, semantics, ENV, makeLoad, simulator, runLoad, saved } = require('./router_optimization_harness.cjs');
function runTests(report = console.log) {
  const tests = [], test = (name, fn) => tests.push({ name, fn });
  test('mesmos 120 eventos: 120 -> 30 chamadas simuladas, 30 resultados identicos', () => {
    const load = makeLoad(), before = runLoad(baseline, load), after = runLoad(optimized, load);
    assert.deepEqual(before.errors, []); assert.deepEqual(after.errors, []);
    assert.equal(before.counts.llm, 120); assert.equal(after.counts.llm, 30);
    assert.equal(before.counts.lookup, 120); assert.equal(after.counts.lookup, 150);
    assert.equal(before.counts.create, 30); assert.equal(after.counts.create, 30);
    assert.deepEqual(saved(after), saved(before));
    assert.deepEqual(after.notifications.map(n => n.text), before.notifications.map(n => n.text));
    assert.deepEqual(after.prompts, before.prompts.slice(0, 30));
    assert.ok(after.prompts.every(text => semantics.some(s => s.sanitized === text)));
    assert.equal(new Set(saved(after).map(r => r.theme)).size, 5);
    assert.equal(new Set(saved(after).map(r => r.sentiment)).size, 3);
  });
  test('sem duplicatas: nenhuma chamada eliminada e classificacao preservada', () => {
    const load = makeLoad({ unique: 30, passes: 1 });
    const before = runLoad(baseline, load), after = runLoad(optimized, load);
    assert.equal(before.counts.llm, 30); assert.equal(after.counts.llm, 30);
    assert.deepEqual(saved(after), saved(before)); assert.deepEqual(after.errors, []);
  });
  test('todos ja existentes: 30 -> 0 chamadas, nenhum novo registro/alerta', () => {
    const load = makeLoad({ unique: 30, passes: 1 });
    const before = runLoad(baseline, load, { seed: load }), after = runLoad(optimized, load, { seed: load });
    assert.equal(before.counts.llm, 30); assert.equal(after.counts.llm, 0);
    assert.equal(after.counts.create, 0); assert.equal(after.counts.slack, 0);
    assert.deepEqual(saved(after), saved(before)); assert.deepEqual(after.errors, []);
  });
  test('mesmo ID com texto alterado continua sem atualizar classificacao persistida', () => {
    const load = makeLoad({ unique: 1, passes: 1 });
    const changed = { ...load[0], review_text: semantics[1].original };
    const before = runLoad(baseline, [changed], { seed: load }), after = runLoad(optimized, [changed], { seed: load });
    assert.equal(before.counts.llm, 1); assert.equal(after.counts.llm, 0);
    assert.deepEqual(saved(after), saved(before)); assert.equal(after.counts.create, 0);
  });
  test('consulta final preservada: duplicata que aparece durante LLM nao e gravada', () => {
    const run = runLoad(optimized, makeLoad({ unique: 1, passes: 1 }), {
      lookupResponse: name => name === 'Airtable Buscar review_id' ? { statusCode: 200, body: {
        records: [{ id: 'rec00000000000099', fields: { review_id: 'SYNTH-0001' } }] } } : undefined,
    });
    assert.equal(run.counts.llm, 1); assert.equal(run.counts.lookup, 2);
    assert.equal(run.counts.create, 0); assert.equal(run.counts.slack, 0); assert.deepEqual(run.errors, []);
  });
  const invalidLookup = [null, {}, { statusCode: 503, body: { error: 'email@example.invalid' } },
    { statusCode: 200, body: {} }, { statusCode: 200, body: { records: null } },
    { statusCode: 200, body: { records: [{ id: 'invalid', fields: {} }] } },
    { statusCode: 200, body: { records: [{ id: 'rec00000000000001', fields: { review_id: 'OTHER' } }] } },
    { statusCode: 200, body: { records: [null, null] } }];
  invalidLookup.forEach((lookupResponse, i) => test(`busca invalida ${i}: falha fechada antes do LLM`, () => {
    const run = runLoad(optimized, makeLoad({ unique: 1, passes: 1 }), { lookupResponse });
    assert.equal(run.counts.llm, 0); assert.equal(run.counts.create, 0);
    assert.equal(run.errors.length, 1); assert.ok(!run.errors[0].includes('example.invalid'));
  }));
  for (const [i, review_id] of [null, '', {}, "id' OR TRUE()", 'id\n', 'x'.repeat(129)].entries()) {
    test(`review_id invalido ${i}: nenhuma consulta ou chamada`, () => {
      const run = runLoad(optimized, [{ ...makeLoad({ unique: 1, passes: 1 })[0], review_id }]);
      assert.equal(run.counts.llm, 0); assert.equal(run.counts.lookup, 0);
      assert.deepEqual(run.errors, ['review_id invalido para deduplicacao.']);
    });
  }
  for (const [i, review_text] of [null, '', ' ', {}, 'x'.repeat(20001)].entries()) {
    test(`texto invalido ${i}: sanitizador continua bloqueando antes de HTTP`, () => {
      for (const workflow of [baseline, optimized]) {
        const run = runLoad(workflow, [{ ...makeLoad({ unique: 1, passes: 1 })[0], review_text }]);
        assert.equal(run.counts.llm, 0); assert.equal(run.counts.lookup, 0);
        assert.deepEqual(run.errors, ['Entrada invalida para sanitizacao.']);
      }
    });
  }
  for (const bad of [{ CLASSIFIER_ENV: 'PROD' }, { CLASSIFIER_DEV_BASE_ID: '' },
    { CLASSIFIER_DEV_TABLE_ID: '' }, { CLASSIFIER_DEV_BASE_ID: 'app00000000000000\n' }]) {
    test(`DEV fail-closed: ${Object.keys(bad)[0]}`, () => {
      const run = runLoad(optimized, makeLoad({ unique: 1, passes: 1 }), { env: { ...ENV, ...bad, AIRTABLE_BASE_ID: ENV.CLASSIFIER_DEV_BASE_ID } });
      assert.deepEqual(run.errors, ['Configuracao DEV de classificacao invalida.']);
      assert.equal(run.counts.lookup, 0); assert.equal(run.counts.llm, 0);
    });
  }
  for (const llmResponse of ['email@example.invalid', '{"sentiment":"errado","theme":"app_bug"}']) {
    test('parser continua rejeitando LLM invalido sem expor conteudo', () => {
      const run = runLoad(optimized, makeLoad({ unique: 1, passes: 1 }), { llmResponse });
      assert.equal(run.counts.llm, 1); assert.equal(run.counts.create, 0); assert.equal(run.counts.slack, 0);
      assert.equal(run.errors.length, 1); assert.ok(!run.errors[0].includes('example.invalid'));
    });
  }
  test('sanitizador ignora campo sanitizado injetado pelo cliente', () => {
    const input = { ...makeLoad({ unique: 1, passes: 1 })[0], review_text_sanitized: 'PII_INJETADA' };
    const run = simulator(optimized); run.run(input);
    assert.deepEqual(run.prompts, [semantics[0].sanitized]); assert.deepEqual(run.errors, []);
  });
  let failed = 0;
  for (const { name, fn } of tests) {
    try { fn(); report(`[OK] ${name}`); }
    catch (error) { failed++; report(`[FALHA] ${name}: ${error.message}`); }
  }
  report(`RESULTADO: ${tests.length - failed} passaram, ${failed} falharam`);
  return { passed: tests.length - failed, failed, total: tests.length };
}
module.exports = { runTests };
if (require.main === module) process.exitCode = runTests().failed ? 1 : 0;
