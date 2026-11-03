'use strict';
// Transporte exclusivamente em memoria. Nao importa HTTP, SDKs, fetch nem .env.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.join(__dirname, '..');
const load = file => JSON.parse(fs.readFileSync(path.join(ROOT, file), 'utf8'));
const baseline = load('n8n-mirror/workflows/vozdocliente-router-v4.json');
const optimized = load('n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json');
const semantics = load('tests/fixtures/pii_semantic_cases.json');
const recipe = load('tests/fixtures/optimization_load.json');
const ENV = { CLASSIFIER_ENV: 'DEV', CLASSIFIER_DEV_BASE_ID: 'app00000000000000',
  CLASSIFIER_DEV_TABLE_ID: 'tbl00000000000001', CLASSIFIER_SLACK_DEV_CHANNEL_ID: 'C00000000' };
const plain = value => JSON.parse(JSON.stringify(value));
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : ['2026-11-02T12:00:00.000Z'])); }
  static now() { return Date.parse('2026-11-02T12:00:00.000Z'); }
}
function makeLoad({ unique = recipe.unique_reviews, passes = recipe.passes } = {}) {
  const inputs = [];
  for (let pass = 0; pass < passes; pass++) for (let i = 0; i < unique; i++) {
    const sample = semantics[i % semantics.length];
    inputs.push({ review_id: 'SYNTH-' + String(i + 1).padStart(4, '0'), customer_name: 'Pessoa Sintetica ' + (i + 1),
      source: 'fixture', rating: sample.expected.sentiment === 'negativo' ? 1 : sample.expected.sentiment === 'positivo' ? 5 : 3,
      review_text: sample.original });
  }
  return inputs;
}
function simulator(workflow, { env = ENV, seed = [], lookupResponse, llmResponse } = {}) {
  const records = new Map(seed.map((review, i) => [review.review_id,
    { id: 'rec' + String(i + 1).padStart(14, '0'), fields: plain(review) }]));
  const counts = { llm: 0, lookup: 0, create: 0, slack: 0 };
  const prompts = [], notifications = [], errors = [];
  const nodes = Object.fromEntries(workflow.nodes.map(n => [n.name, n]));
  const scripts = new Map();
  const script = source => {
    if (!scripts.has(source)) scripts.set(source, new vm.Script(source));
    return scripts.get(source);
  };
  function run(input) {
    let current = 'Webhook Review', value = { body: plain(input) };
    const outputs = {};
    const context = () => vm.createContext({ $json: value, $env: env, Date: FixedDate,
      $input: { all: () => [{ json: value }], first: () => ({ json: value }) },
      $: name => { if (!(name in outputs)) throw Error('Node pareado ausente.');
        return { first: () => ({ json: outputs[name] }), item: { json: outputs[name] } }; },
    });
    const evaluate = source => script(source).runInContext(context(), { timeout: 1000 });
    const expression = text => typeof text !== 'string' || !text.startsWith('=') ? text
      : text.startsWith('={{') && text.endsWith('}}') ? evaluate('(' + text.slice(3, -2) + ')')
        : text.slice(1).replace(/\{\{([\s\S]*?)\}\}/g, (_, expr) => String(evaluate('(' + expr + ')')));
    const body = parameters => JSON.parse(expression(parameters.jsonBody));
    try {
      for (let step = 0; step < 30; step++) {
        const node = nodes[current]; let branch = 0;
        if (node.type.endsWith('.code')) {
          const result = evaluate('(function(){' + node.parameters.jsCode + '\n})()');
          if (!Array.isArray(result) || result.length !== 1) throw Error('Quantidade de itens invalida.');
          value = plain(result[0].json);
        } else if (node.type.endsWith('.if')) {
          const condition = node.parameters.conditions.conditions[0];
          const left = expression(condition.leftValue);
          const operation = condition.operator.operation;
          const yes = operation === 'gt' ? left > condition.rightValue
            : operation === 'true' ? left === true : left === condition.rightValue;
          branch = yes ? 0 : 1;
        } else if (node.type.endsWith('.httpRequest')) {
          // Avalia parametros exportados, mas nunca efetua transporte externo.
          const url = expression(node.parameters.url);
          if (current.startsWith('LLM ')) {
            counts.llm++;
            const request = body(node.parameters), text = request.messages[1].content;
            prompts.push(text);
            const scenario = semantics.find(sample => sample.sanitized === text);
            if (!scenario) throw Error('Prompt fora da fixture sintetica.');
            value = { choices: [{ message: { content: llmResponse === undefined
              ? JSON.stringify(scenario.expected) : llmResponse } }] };
          } else if (current === 'Airtable Buscar review_id' || current === 'Airtable Precheck DEV') {
            counts.lookup++;
            const query = Object.fromEntries(node.parameters.queryParameters.parameters.map(p => [p.name, expression(p.value)]));
            const match = query.filterByFormula.match(/^\{review_id\}='([A-Za-z0-9_-]+)'$/);
            if (!match || query.maxRecords !== '1') throw Error('Consulta fora do contrato sintetico.');
            const found = records.get(match[1]);
            const result = { records: found ? [{ id: found.id, fields: query['fields[]'] === 'review_id'
              ? { review_id: found.fields.review_id } : found.fields }] : [] };
            const override = typeof lookupResponse === 'function' ? lookupResponse(current, query, result) : lookupResponse;
            value = override === undefined ? node.parameters.options.response
              ? { statusCode: 200, body: result } : result : plain(override);
          } else if (current.startsWith('Airtable ')) {
            const request = body(node.parameters); counts.create++;
            const rec = { id: 'rec' + String(records.size + 1).padStart(14, '0'), fields: request.fields };
            records.set(request.fields.review_id, rec); value = plain(rec);
          } else if (current.startsWith('Slack ')) {
            counts.slack++; notifications.push(body(node.parameters)); value = { ok: true };
          } else throw Error('Transporte inesperado.');
          if (typeof url !== 'string') throw Error('URL fora do contrato.');
        }
        outputs[current] = plain(value);
        const links = workflow.connections[current]?.main?.[branch];
        if (!links?.length) return { ok: true, terminal: current };
        if (links.length !== 1) throw Error('Roteamento nao sequencial.');
        current = links[0].node;
      }
      throw Error('Loop inesperado.');
    } catch (error) { errors.push(error.message); return { ok: false, error: error.message, terminal: current }; }
  }
  return { run, counts, records, prompts, notifications, errors };
}
function runLoad(workflow, inputs, options) {
  const run = simulator(workflow, options);
  for (const input of inputs) run.run(input);
  return run;
}
function saved(run) {
  return [...run.records.values()].map(record => record.fields).sort((a, b) => a.review_id.localeCompare(b.review_id));
}
module.exports = { baseline, optimized, semantics, recipe, ENV, makeLoad, simulator, runLoad, saved };
