'use strict';
// Executa Code/expressoes/grafo exportados. Todo transporte e subworkflow sao locais.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { ENV, makeLoad, semantics } = require('./router_optimization_harness.cjs');
const root = path.join(__dirname, '..');
const load = name => JSON.parse(fs.readFileSync(path.join(root, 'n8n-mirror/workflows', name), 'utf8'));
const router = load('vozdocliente-router-v4-observavel-dev.json');
const observer = load('vozdocliente-observabilidade-router-dev.json');
const errorWorkflow = load('vozdocliente-erros-router-dev.json');
const plain = value => JSON.parse(JSON.stringify(value));
const OBS_ENV = { ...ENV, ROUTER_OBSERVER_WORKFLOW_ID: 'observer_synthetic', ROUTER_OBSERVED_WORKFLOW_ID: 'router_synthetic',
  ROUTER_ALERTS_ENABLED: 'true' };
const input = () => ({ ...makeLoad({ unique: 1, passes: 1 })[0], source: 'formulario' });

function simulator({ env = OBS_ENV, fail = {}, malformed = {}, slackResponse, DateType = Date,
  executionMode = 'offline_simulation', unexpected = {} } = {}) {
  const logs = [], notifications = [], outputs = {}, records = new Map(), prompts = [];
  const counts = { llm: 0, lookup: 0, create: 0, business_slack: 0, alerts: 0, subworkflows: 0, real_external_calls: 0 };
  const scripts = new Map();
  function execute(workflow, start, initial, id) {
    let name = start, value = plain(initial);
    const local = {};
    const context = () => vm.createContext({ $json: value, $env: env, Date: DateType,
      $execution: { id: String(id), mode: executionMode }, console: { log: item => logs.push(typeof item === 'string' ? JSON.parse(item) : plain(item)) },
      $input: { all: () => [{ json: value }], first: () => ({ json: value }) },
      $: node => { if (!(node in local)) throw Error('Node pareado ausente.');
        return { first: () => ({ json: local[node] }), item: { json: local[node] } }; },
    });
    const evaluate = text => {
      if (!scripts.has(text)) scripts.set(text, new vm.Script(text));
      return scripts.get(text).runInContext(context(), { timeout: 1000 });
    };
    const expression = text => typeof text !== 'string' || !text.startsWith('=') ? text
      : text.startsWith('={{') && text.endsWith('}}') ? evaluate('(' + text.slice(3, -2) + ')')
        : text.slice(1).replace(/\{\{([\s\S]*?)\}\}/g, (_, exp) => String(evaluate('(' + exp + ')')));
    const body = parameters => { const result = expression(parameters.jsonBody); return typeof result === 'string' ? JSON.parse(result) : result; };
    const nodes = Object.fromEntries(workflow.nodes.map(node => [node.name, node]));
    for (let step = 0; step < 150; step++) {
      const node = nodes[name]; let branch = 0;
      if (!node) throw Error('Node inexistente.');
      try {
        if (unexpected[name]) throw Error('Interrupcao sintetica.');
        if (node.type.endsWith('.code')) {
          const items = evaluate('(function(){' + node.parameters.jsCode + '\n})()');
          if (!items.length) return { ok: true, terminal: name, value: null, outputs: local };
          if (items.length !== 1) throw Error('Contrato de itens invalido.');
          value = plain(items[0].json);
        } else if (node.type.endsWith('.if')) {
          const condition = node.parameters.conditions.conditions[0], left = expression(condition.leftValue);
          const operation = condition.operator.operation;
          branch = (operation === 'true' ? left === true : operation === 'gt' ? left > condition.rightValue : left === condition.rightValue) ? 0 : 1;
        } else if (node.type.endsWith('.executeWorkflow')) {
          counts.subworkflows++;
          if (expression(node.parameters.workflowId) !== 'observer_synthetic') throw Error('Observador sintetico nao configurado.');
          const run = execute(observer, 'Receber evento Router DEV', value, Number(id) + 1000000);
          if (!run.ok) throw Error('Observador sintetico falhou.');
          value = run.value;
        } else if (node.type.endsWith('.stopAndError')) {
          throw Error(node.parameters.errorMessage);
        } else if (node.type.endsWith('.httpRequest')) {
          const url = expression(node.parameters.url);
          if (typeof url !== 'string') throw Error('URL invalida.');
          if (name === 'Airtable Precheck DEV' || name === 'Airtable Buscar review_id') counts.lookup++;
          if (name === 'LLM DEV') counts.llm++;
          if (name === 'Airtable DEV') counts.create++;
          if (fail[name]) throw Error('Falha sintetica: pessoa@example.invalid SECRET_SYNTHETIC');
          if (name in malformed) value = plain(malformed[name]);
          else if (name === 'Airtable Precheck DEV' || name === 'Airtable Buscar review_id') {
            const query = Object.fromEntries(node.parameters.queryParameters.parameters.map(p => [p.name, expression(p.value)]));
            const match = query.filterByFormula.match(/^\{review_id\}='([A-Za-z0-9_-]+)'$/);
            if (!match || query['fields[]'] !== 'review_id' || query.maxRecords !== '1') throw Error('Consulta invalida.');
            const record = records.get(match[1]);
            value = { statusCode: 200, body: { records: record ? [{ id: record.id, fields: { review_id: match[1] } }] : [] } };
          } else if (name === 'LLM DEV') {
            const request = body(node.parameters); prompts.push(request.messages[1].content);
            const sample = semantics.find(s => s.sanitized === request.messages[1].content);
            if (!sample) throw Error('Fixture sanitizada ausente.');
            value = { choices: [{ message: { content: JSON.stringify(sample.expected) } }], usage: { prompt_tokens: 100, completion_tokens: 20 } };
          } else if (name === 'Airtable DEV') {
            const request = body(node.parameters);
            const record = { id: 'rec' + String(records.size + 1).padStart(14, '0'), fields: request.fields };
            records.set(request.fields.review_id, plain(record)); value = record;
          } else if (name === 'Slack DEV falha') {
            counts.alerts++; notifications.push(body(node.parameters));
            value = slackResponse === undefined ? { statusCode: 200, body: { ok: true } } : plain(slackResponse);
          } else if (name === 'Slack DEV') { counts.business_slack++; value = { ok: true }; }
          else throw Error('Transporte nao suportado.');
        }
      } catch (error) {
        if (node.onError === 'continueErrorOutput') {
          branch = 1; value = { error: { message: error.message } };
        } else if (node.onError === 'continueRegularOutput') value = { error: { message: error.message } };
        else return { ok: false, terminal: name, error: error.message, outputs: local };
      }
      local[name] = plain(value);
      const links = workflow.connections[name]?.main?.[branch];
      if (!links?.length) { Object.assign(outputs, local); return { ok: true, terminal: name, value, outputs: local }; }
      if (links.length !== 1) throw Error('Grafo sintetico nao sequencial.');
      name = links[0].node;
    }
    throw Error('Limite do harness excedido.');
  }
  return { run: (payload = input(), id = 600001) => execute(router, 'Webhook Review', { body: payload }, id),
    error: (payload, id = 700001) => execute(errorWorkflow, 'Erro Router DEV', payload, id),
    observe: (report, id = 800001) => execute(observer, 'Receber evento Router DEV', { report }, id),
    logs, counts, outputs, notifications, records, prompts };
}
module.exports = { simulator, input, OBS_ENV, router, observer, errorWorkflow };
