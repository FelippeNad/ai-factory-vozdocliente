// Somente campos permitidos: nunca logar summary, preview, estado, headers ou erros externos.
const summary = $input.first().json;
const alertEnv = $env;
const count = value => Number.isSafeInteger(value) && value >= 0 ? value : 0;
const allowedCodes = new Set(['CONFIG_INVALID', 'HTTP_429', 'HTTP_5XX', 'HTTP_REJECTED',
  'NETWORK_ERROR', 'AUDIT_FAILED', 'SCHEMA_INVALID', 'PAGE_INVALID', 'RECORD_INVALID',
  'DATE_INVALID', 'PAGINATION_INVALID', 'SCAN_LIMIT', 'DELETE_LIMIT', 'RECHECK_INVALID',
  'DELETE_NOT_CONFIRMED', 'STATE_INVALID', 'TIME_LIMIT', 'GUARD_BLOCKED']);
const started = timestamp(summary.started_at), finished = timestamp(summary.finished_at);
const duration = started !== null && finished !== null && finished >= started ? finished - started : null;
const validRun = typeof summary.run_id === 'string' && summary.run_id.trim() === summary.run_id
  && /^retention-\d{1,30}$/.test(summary.run_id);
const runId = validRun ? summary.run_id : 'retention-unknown';
const failed = !validRun || duration === null || !['dry_run', 'completed'].includes(summary.status)
  || count(summary.failures) > 0 || summary.audit_persisted !== true || summary.audit_finalized !== true;
const code = !failed ? 'NONE' : !validRun || duration === null ? 'OBS_INPUT_INVALID'
  : Array.isArray(summary.error_codes) && allowedCodes.has(summary.error_codes[0]) ? summary.error_codes[0] : 'UNKNOWN_ERROR';
const event = { run_id: runId, stage: 'retention', status: failed ? 'failure' : 'success',
  duration_ms: duration, error_code: code };
const metrics = { runs_total: 1, runs_success: failed ? 0 : 1, runs_failure: failed ? 1 : 0,
  processed: count(summary.analyzed), failures: count(summary.failures), latency_ms: duration };
console.log({ ...event, metrics });
let alertStatus = 'not_needed', alertError = null, slackBody = null;
const channel = alertEnv.RETENTION_SLACK_DEV_CHANNEL_ID;
if (failed) {
  if (alertEnv.RETENTION_ALERTS_ENABLED !== 'true') alertStatus = 'disabled';
  else if (alertEnv.RETENTION_ENV !== 'DEV' || typeof channel !== 'string'
      || channel.trim() !== channel || !/^[CG][A-Z0-9]{8,31}$/.test(channel)) {
    alertStatus = 'blocked'; alertError = 'ALERT_CONFIG_INVALID';
  } else {
    alertStatus = 'pending';
    slackBody = { channel, mrkdwn: false,
      unfurl_links: false, unfurl_media: false,
      text: '[DEV] VozDoCliente: falha na retencao. run_id=' + runId
        + '; status=' + event.status + '; error_code=' + code
        + '; processed=' + metrics.processed + '; duration_ms=' + (duration ?? 'unknown') };
  }
}
return [{ json: { summary, event, metrics, send_alert: slackBody !== null, slack_body: slackBody,
  alert_status: alertStatus, alert_error_code: alertError, alert_started_ms: Date.now() }, pairedItem: { item: 0 } }];
