const report = obsCanonical($input.first().json.report);
let alertStatus = 'not_needed', alertError = null, slackBody = null;
if (report.status === 'failure') {
  const channel = $env.CLASSIFIER_SLACK_DEV_CHANNEL_ID;
  if ($env.ROUTER_ALERTS_ENABLED !== 'true') alertStatus = 'disabled';
  else if ($env.CLASSIFIER_ENV !== 'DEV' || typeof channel !== 'string'
      || channel.trim() !== channel || !/^[CG][A-Z0-9]{8,31}$/.test(channel)) {
    alertStatus = 'blocked'; alertError = 'ALERT_CONFIG_INVALID';
  } else {
    alertStatus = 'pending';
    slackBody = { channel, mrkdwn: false, unfurl_links: false, unfurl_media: false,
      text: '[DEV][P1] VozDoCliente Router: falha. run_id=' + report.run_id
        + '; stage=' + report.stage + '; error_code=' + report.error_code
        + '; llm_calls_attempted=' + (report.metrics.llm_calls_attempted ?? 'unknown')
        + '; duration_ms=' + (report.duration_ms ?? 'unknown') };
  }
}
// Formato compativel com observe-result.js da retencao, reutilizado sem alteracoes.
return [{ json: { summary: { report }, event: { run_id: report.run_id, stage: report.stage,
  status: report.status, duration_ms: report.duration_ms, error_code: report.error_code },
  metrics: report.metrics, send_alert: slackBody !== null, slack_body: slackBody,
  alert_status: alertStatus, alert_error_code: alertError, alert_started_ms: Date.now() }, pairedItem: { item: 0 } }];
