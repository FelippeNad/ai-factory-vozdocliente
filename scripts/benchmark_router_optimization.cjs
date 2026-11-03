#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { performance } = require('node:perf_hooks');
const { baseline, optimized, makeLoad, runLoad, saved } = require('../tests/router_optimization_harness.cjs');
const ROOT = path.join(__dirname, '..');
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const inputs = makeLoad(), trials = 9, warmup = 1;
const originalNodes = Object.fromEntries(baseline.nodes.map(n=>[n.name,n]));
const candidateNodes = Object.fromEntries(optimized.nodes.map(n=>[n.name,n]));
for (const name of ['Sanitizar PII','Parse + Merge']) assert.deepEqual(candidateNodes[name].parameters, originalNodes[name].parameters);
assert.equal(candidateNodes['LLM DEV'].parameters.jsonBody, originalNodes['LLM PROD'].parameters.jsonBody);
assert.equal(optimized.connections['Parse + Merge'].main[0][0].node, 'Airtable Buscar review_id');
const samples = { before: [], after: [] };
let counts, quality;
for (let trial = -warmup; trial < trials; trial++) {
  const runs = {};
  for (const key of trial % 2 === 0 ? ['before', 'after'] : ['after', 'before']) {
    const start = performance.now();
    const run = runLoad(key === 'before' ? baseline : optimized, inputs);
    const elapsed = performance.now() - start;
    assert.deepEqual(run.errors, []);
    runs[key] = run;
    if (trial >= 0) samples[key].push(elapsed);
  }
  assert.deepEqual(saved(runs.before), saved(runs.after));
  assert.deepEqual(runs.before.notifications.map(n => n.text), runs.after.notifications.map(n => n.text));
  counts = { before: runs.before.counts, after: runs.after.counts };
  quality = { saved_reviews_identical: true, identical_reviews: runs.after.records.size,
    slack_texts_identical: true, sanitizer_prompt_parser_unchanged: true };
}
const rounded = value => Math.round(value * 1000) / 1000;
const stats = values => {
  const sorted = [...values].sort((a, b) => a - b);
  return { samples_batch_ms: values.map(rounded), mean_batch_ms: rounded(values.reduce((a,b)=>a+b,0)/values.length),
    median_batch_ms: rounded(sorted[Math.floor(sorted.length / 2)]),
    p95_batch_ms: rounded(sorted[Math.ceil(sorted.length * 0.95) - 1]) };
};
const report = { schema_version: 1, scope: 'OFFLINE_GRAPH_HARNESS', measured_at_utc: new Date().toISOString(),
  runtime: { node: process.version, platform: process.platform, arch: process.arch },
  real_external_api_calls: 0, real_llm_calls: 0, real_n8n_engine: false,
  remote_llm_latency_ms: null, production_latency_ms: null, artificial_delays: false,
  methodology: { trials, warmup_batches_per_variant: warmup, alternating_order: true, sequential_events: true,
    store_reset_every_batch: true, mock_llm: 'deterministic_fixture_lookup', timing: 'performance.now',
    post_llm_dedup_preserved: true,
    includes: 'VM/expression/code/memory-transport execution of exported graph; no network/server latency' },
  sources: { benchmark_sha256: digest(fs.readFileSync(__filename)),
    harness_sha256: digest(fs.readFileSync(path.join(ROOT,'tests/router_optimization_harness.cjs'))) },
  workload: { events: inputs.length, unique_review_ids: new Set(inputs.map(i=>i.review_id)).size,
    sha256: digest(JSON.stringify(inputs)) },
  workflows: Object.fromEntries([['before', 'vozdocliente-router-v4.json'], ['after', 'vozdocliente-router-v4-otimizado-dev.json']]
    .map(([key, file])=>[key, { file, sha256: digest(fs.readFileSync(path.join(ROOT,'n8n-mirror/workflows',file))) }])),
  simulated_calls: counts, llm_calls_avoided: counts.before.llm-counts.after.llm,
  llm_calls_reduction_percent: rounded(100*(counts.before.llm-counts.after.llm)/counts.before.llm),
  offline_wall_clock: { before: stats(samples.before), after: stats(samples.after) }, quality };
const output = path.join(ROOT, 'docs/evidencias/otimizacao-v4-benchmark.json');
if (process.argv.slice(2).includes('--write')) fs.writeFileSync(output, JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
