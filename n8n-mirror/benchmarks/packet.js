// Nunca copiar payload, texto LLM, nomes, IDs Airtable ou erros externos para a coleta.
const report = obsCanonical($input.first().json.report);
const body = $('Webhook Review').first().json.body;
const output = name => { try { return $(name).first().json; } catch { return null; } };
const attempted = name => output(name) === null ? 0 : 1;
let classification = null;
if (report.metrics.persisted === 1) {
  const fields = output('Airtable DEV')?.fields;
  const parsed = output('Parse + Merge');
  if (fields?.review_id === body.review_id && fields.sentiment === parsed?.sentiment && fields.theme === parsed?.theme
      && ['positivo', 'neutro', 'negativo'].includes(fields.sentiment)
      && ['entrega', 'produto', 'atendimento', 'preco', 'app_bug'].includes(fields.theme)) {
    classification = { sentiment: fields.sentiment, theme: fields.theme };
  }
}
return [{ json: {
  schema: 'vozdocliente.router.real-benchmark.packet.v1',
  benchmark_id: body.benchmark_id, variant: BENCH_VARIANT, sequence: body.benchmark_sequence,
  case_id: (body.benchmark_sequence - 1) % 5 + 1, report,
  delivery_status: $input.first().json.alert_status,
  airtable_queries_attempted: { precheck: attempted('Precheck iniciado DEV'), final: attempted('Deduplicacao final iniciada DEV') },
  persisted_classification: classification,
  configuration: {
    environment: $env.CLASSIFIER_ENV, dev_base_id: $env.CLASSIFIER_DEV_BASE_ID,
    dev_table_id: $env.CLASSIFIER_DEV_TABLE_ID, slack_channel_id: $env.CLASSIFIER_SLACK_DEV_CHANNEL_ID,
    observer_id: $env.ROUTER_OBSERVER_WORKFLOW_ID || null,
    input_price: obsPrice($env.OBS_LLM_INPUT_USD_PER_MILLION),
    output_price: obsPrice($env.OBS_LLM_OUTPUT_USD_PER_MILLION)
  }
}, pairedItem: { item: 0 } }];
