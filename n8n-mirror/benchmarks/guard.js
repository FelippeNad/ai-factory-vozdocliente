// Somente as cinco fixtures sem PII; configuracao confirmada antes de qualquer HTTP.
const body = $input.first().json.body;
const invalid = () => { throw new Error('Entrada/configuracao de benchmark DEV invalida.'); };
const keys = ['review_id', 'customer_name', 'source', 'rating', 'review_text', 'benchmark_id',
  'benchmark_sequence', 'dev_base_id', 'dev_table_id', 'dev_slack_channel_id'];
if (!body || Object.keys(body).sort().join('|') !== keys.sort().join('|')
    || $env.CLASSIFIER_ENV !== 'DEV'
    || !/^app[A-Za-z0-9]{14}$/.test(body.dev_base_id || '')
    || !/^tbl[A-Za-z0-9]{14}$/.test(body.dev_table_id || '')
    || !/^[CG][A-Z0-9]{8,31}$/.test(body.dev_slack_channel_id || '')
    || body.dev_base_id !== $env.CLASSIFIER_DEV_BASE_ID
    || body.dev_table_id !== $env.CLASSIFIER_DEV_TABLE_ID
    || body.dev_slack_channel_id !== $env.CLASSIFIER_SLACK_DEV_CHANNEL_ID
    || typeof $env.ROUTER_OBSERVER_WORKFLOW_ID !== 'string'
    || !/^[A-Za-z0-9_-]{1,64}$/.test($env.ROUTER_OBSERVER_WORKFLOW_ID)
    || !/^[0-9a-f]{32}$/.test(body.benchmark_id || '')
    || !Number.isInteger(body.benchmark_sequence) || body.benchmark_sequence < 1 || body.benchmark_sequence > 15) invalid();
const sample = BENCH_CASES[(body.benchmark_sequence - 1) % 5];
if (body.review_id !== 'BMR-' + body.benchmark_id + '-' + BENCH_VARIANT + '-0' + sample.case_id
    || body.review_text !== sample.text || body.rating !== sample.rating
    || body.customer_name !== 'BENCHMARK_SINTETICO' || body.source !== 'formulario') invalid();
return [{ json: $input.first().json, pairedItem: { item: 0 } }];
