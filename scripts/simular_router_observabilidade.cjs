'use strict';
// Exerce os exports com HTTP/LLM/Slack em memoria; nunca le .env ou abre sockets.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { simulator, input } = require('../tests/router_observability_harness.cjs');
const healthy = simulator();
const results = [healthy.run(input(), 600001), healthy.run(input(), 600002)];
const failed = simulator({ fail: { 'Airtable Precheck DEV': true } });
results.push(failed.run(input(), 600003));
if (!results[0].ok || !results[1].ok || results[2].terminal !== 'Interromper com seguranca')
  throw Error('Simulacao nao corresponde aos tres cenarios esperados.');
const events = [...healthy.logs, ...failed.logs].filter(event => event.schema);
const serialized = events.map(event => JSON.stringify(event)).join('\n') + '\n';
const outputIndex = process.argv.indexOf('--output');
if (outputIndex >= 0) fs.writeFileSync(process.argv[outputIndex + 1], serialized, 'utf8');
else process.stdout.write(serialized);
const metadata = { scope: 'SIMULACAO_OFFLINE', real_n8n_engine: false, real_external_calls: 0,
  real_llm_calls: 0, real_slack_delivery: false, events: events.length,
  simulated_llm_calls: healthy.counts.llm + failed.counts.llm,
  simulated_alerts: healthy.counts.alerts + failed.counts.alerts,
  node: process.version, platform: process.platform, generated_at: new Date().toISOString(),
  terminal_events: events.filter(event => event.kind === 'run'),
  events_sha256: crypto.createHash('sha256').update(serialized).digest('hex'),
  workflow_sha256: Object.fromEntries(['vozdocliente-router-v4-observavel-dev.json', 'vozdocliente-observabilidade-router-dev.json',
    'vozdocliente-erros-router-dev.json'].map(name => [name, crypto.createHash('sha256').update(fs.readFileSync(
      path.join(__dirname, '../n8n-mirror/workflows', name))).digest('hex')])),
  note: 'Tempos do harness local com mocks imediatos; nao sao latencias do n8n, Airtable ou LLM.' };
const metadataIndex = process.argv.indexOf('--metadata-output');
if (metadataIndex >= 0) fs.writeFileSync(process.argv[metadataIndex + 1], JSON.stringify(metadata, null, 2) + '\n', 'utf8');
console.error(JSON.stringify({ scope: metadata.scope, events: metadata.events, real_external_calls: 0,
  simulated_llm_calls: metadata.simulated_llm_calls, simulated_alerts: metadata.simulated_alerts }));
