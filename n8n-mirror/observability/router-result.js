const previous = $('Entregar observabilidade DEV').first().json;
const report = obsCanonical(previous.report);
const response = $input.first().json;
const allowedStatus = ['not_needed', 'disabled', 'blocked', 'sent', 'failed'];
const result = response.observability;
const ok = previous.send_observation && result && allowedStatus.includes(result.alert_status);
const alertStatus = !previous.send_observation ? 'not_configured' : ok ? result.alert_status : 'delivery_failed';
const allowedErrors = ['ALERT_CONFIG_INVALID', 'SLACK_DELIVERY_FAILED'];
const alertError = ok ? allowedErrors.includes(result.alert_error_code) ? result.alert_error_code : null : 'OBS_DELIVERY_FAILED';
if (!ok || ['failed', 'blocked'].includes(alertStatus)) {
  const event = { ...report, kind: 'stage', stage: 'telemetry', status: 'failure', duration_ms: null,
    at: new Date().toISOString(), error_code: 'OBS_DELIVERY_FAILED',
    event_id: [report.run_id, 'stage', 'telemetry', 'failure'].join(':'),
    metrics: { ...report.metrics, runs_total: 0, runs_success: 0, runs_duplicate: 0, runs_failure: 0, received: 0 } };
  console.log(JSON.stringify(obsCanonical(event)));
}
return [{ json: { report, alert_status: alertStatus, alert_error_code: alertError }, pairedItem: { item: 0 } }];
