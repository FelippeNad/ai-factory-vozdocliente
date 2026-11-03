const previous = $('Observabilidade DEV').item.json;
const response = $input.first().json;
const simulated = false; // Substituido SOMENTE no export DEMO pelo gerador.
let alertStatus = previous.alert_status, alertError = previous.alert_error_code;
if (previous.send_alert) {
  const ok = Number.isInteger(response.statusCode) && response.statusCode >= 200
    && response.statusCode < 300 && response.body?.ok === true;
  alertStatus = ok ? (simulated ? 'simulated' : 'sent') : 'failed';
  alertError = ok ? null : 'SLACK_DELIVERY_FAILED';
}
if (previous.send_alert || alertError) {
  console.log({ run_id: previous.event.run_id, stage: 'slack_alert',
    status: alertError ? 'failure' : 'success',
    duration_ms: Math.max(0, Date.now() - previous.alert_started_ms), error_code: alertError || 'NONE' });
}
// Nao propaga resposta Slack, mensagem do provedor, destino ou payload do alerta.
return [{ json: { ...previous.summary, observability: { event: previous.event, metrics: previous.metrics,
  alert_status: alertStatus, alert_error_code: alertError } }, pairedItem: { item: 0 } }];
