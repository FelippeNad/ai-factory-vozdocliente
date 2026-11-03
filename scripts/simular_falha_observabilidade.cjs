#!/usr/bin/env node
'use strict';
// Percorre o export real com respostas em memoria. Nao usa fetch, sockets ou .env.
const { simulate } = require('../tests/test_retention.cjs');
const { ALERT_ENV, failSchema } = require('../tests/test_observability.cjs');
const run = simulate({ env: ALERT_ENV, handler: failSchema });
console.log(JSON.stringify({ scope: 'SIMULACAO_OFFLINE', real_slack_delivery: false, real_airtable_access: false,
  scenario: 'schema_http_503', retention_status: run.summary.status, deleted: run.summary.deleted,
  observability: run.summary.observability, logs: run.logs,
  simulated_slack_requests: run.notifications }, null, 2));
