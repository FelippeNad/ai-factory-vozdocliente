'use strict';
// Executa os exports em VM, somente mocks. Nunca cria evidencias de benchmark real.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { simulator, OBS_ENV } = require('./router_observability_harness.cjs');
const root = path.join(__dirname, '..');
const cases = JSON.parse(fs.readFileSync(path.join(root, 'n8n-mirror/benchmarks/cases.json'), 'utf8'));
const classificationCases = cases.map(c => ({ sanitized: c.text, expected: { sentiment: c.sentiment, theme: c.theme } }));
const workflow = v => JSON.parse(fs.readFileSync(path.join(root, 'n8n-mirror/benchmarks', `router-${v}-benchmark-dev.json`), 'utf8'));
const body = (variant, sequence=1) => {
  const c = cases[(sequence-1)%5], id = 'a'.repeat(32);
  return { review_id: `BMR-${id}-${variant}-0${c.case_id}`, customer_name: 'BENCHMARK_SINTETICO',
    source: 'formulario', rating: c.rating, review_text: c.text, benchmark_id: id, benchmark_sequence: sequence,
    dev_base_id: OBS_ENV.CLASSIFIER_DEV_BASE_ID, dev_table_id: OBS_ENV.CLASSIFIER_DEV_TABLE_ID,
    dev_slack_channel_id: OBS_ENV.CLASSIFIER_SLACK_DEV_CHANNEL_ID };
};
const run = (v, extra={}) => simulator({ workflow: workflow(v), semantics: classificationCases, ...extra });
for (const variant of ['before','after']) {
  const sim = run(variant);
  const packets = [];
  for (let i=1; i<=15; i++) {
    const result = sim.run(body(variant,i), i);
    assert.equal(result.ok, true, JSON.stringify(result));
    const packet = result.outputs['Coletar benchmark DEV'];
    packets.push(packet);
    assert.equal(packet.sequence, i);
    assert.equal(packet.report.source, 'offline_simulation');
    assert.equal(packet.report.status, i<=5 ? 'success' : 'duplicate');
    assert.equal(packet.airtable_queries_attempted.precheck, variant==='after' ? 1 : 0);
    assert.equal(packet.airtable_queries_attempted.final, variant==='before' || i<=5 ? 1 : 0);
    assert.equal(packet.persisted_classification === null, i>5);
    if (i<=5) assert.deepEqual(packet.persisted_classification, { sentiment: cases[i-1].sentiment, theme: cases[i-1].theme });
    for (const forbidden of ['review_text', 'customer_name', 'BMR-', 'rec000', 'choices', 'Authorization'])
      assert.ok(!JSON.stringify(packet).includes(forbidden), forbidden);
  }
  assert.equal(sim.counts.llm, variant==='before' ? 15 : 5);
  assert.equal(sim.counts.lookup, variant==='before' ? 15 : 20);
  assert.equal(sim.counts.create, 5);
  assert.equal(sim.records.size, 5);
  assert.equal(packets.filter(p=>p.report.status==='duplicate').length,10);
  console.log('[OK] ' + variant + ': 15 envios offline, chamadas, consultas, qualidade e pacotes minimos');
  for (const mutation of [{ review_text: 'REJECTED_MARKER' }, { review_id: 'EXISTING' },
    { customer_name: 'REJECTED_MARKER' }, { extra: 'REJECTED_MARKER' }, { dev_table_id: 'tbl11111111111111' }]) {
    const blocked = run(variant); assert.equal(blocked.run({ ...body(variant), ...mutation }).ok,false);
    assert.equal(blocked.counts.llm,0); assert.equal(blocked.counts.lookup,0); assert.equal(blocked.counts.create,0);
  }
  for (const env of [{ CLASSIFIER_ENV: 'PROD' }, { ROUTER_OBSERVER_WORKFLOW_ID: '' }]) {
    const blocked = run(variant,{env:{...OBS_ENV,...env}});
    assert.equal(blocked.run(body(variant)).ok,false); assert.equal(blocked.counts.llm,0); assert.equal(blocked.counts.lookup,0);
  }
  const failed = run(variant,{fail:{'Airtable Buscar review_id':true}});
  const result = failed.run(body(variant));
  assert.equal(result.ok,false); assert.equal(result.terminal,'Interromper com seguranca');
  assert.equal(result.outputs['Coletar benchmark DEV'].report.status,'failure');
  assert.equal(failed.counts.create,0);
  assert.equal(result.outputs['Responder falha benchmark DEV'].report.error_code,'FINAL_DEDUP_HTTP_FAILED');
  const invalid = run(variant,{malformed:{'LLM DEV':{choices:[{message:{content:'REJECTED_MARKER'}}]}}});
  assert.equal(invalid.run(body(variant)).ok,false); assert.equal(invalid.counts.create,0);
  if (variant==='after') {
    const precheck = run(variant,{fail:{'Airtable Precheck DEV':true}});
    assert.equal(precheck.run(body(variant)).ok,false); assert.equal(precheck.counts.llm,0); assert.equal(precheck.counts.create,0);
  }
  console.log('[OK] ' + variant + ': entrada restrita, DEV, falhas seguras e parada preservados');
}
console.log('RESULTADO: benchmark em VM aprovado; zero chamadas externas, nenhum resultado real produzido.');
