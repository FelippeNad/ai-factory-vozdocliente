const input = $input.first().json;
let s = input.state;
if (!s) {
  const now = Date.now();
  s = { config: null, started_at: new Date(now).toISOString(), now, deadline: now + 600000,
    run_id: 'retention-' + (/^\d{1,30}$/.test(String($execution.id)) ? String($execution.id) : String(now)),
    metrics: Object.fromEntries(METRICS.map(key => [key, 0])), codes: [],
    candidates: [], seen: [], offsets: [], offset: null, index: 0,
    schema_verified: false, scan_complete: false, audit_id: null, audit_failed: false,
    audit_finalized: false, blocked: false, done: false, action: 'schema' };
  try {
    s.config = settings($env);
    s.cutoff = new Date(now - s.config.days * 86400000).toISOString();
  } catch {
    failure(s, 'CONFIG_INVALID'); s.blocked = true; finish(s);
  }
} else if (!s.done) {
  const response = input.response;
  const code = response?.statusCode;
  const body = response?.body;
  const action = s.action;
  const ok = Number.isInteger(code) && code >= 200 && code < 300;
  if (!ok) {
    const reason = code === 429 ? 'HTTP_429' : code >= 500 ? 'HTTP_5XX'
      : Number.isInteger(code) ? 'HTTP_REJECTED' : 'NETWORK_ERROR';
    if (action === 'audit_create' || action === 'audit_update') {
      failure(s, 'AUDIT_FAILED'); failure(s, reason);
      s.audit_failed = true; s.blocked = true; finish(s);
    } else {
      // Nao repete DELETE: timeout/5xx pode ter ocorrido depois da exclusao.
      if (action === 'delete' && (!Number.isInteger(code) || code >= 500)) s.metrics.unknown_outcome++;
      block(s, reason);
    }
  } else if (action === 'schema') {
    if (!checkSchema(body, s.config)) block(s, 'SCHEMA_INVALID');
    else { s.schema_verified = true; s.action = 'list'; }
  } else if (action === 'list') {
    const records = body?.records;
    const remaining = Math.min(s.config.pageSize, s.config.maxAnalyzed - s.metrics.analyzed);
    if (!Array.isArray(records) || records.length > remaining) {
      block(s, 'PAGE_INVALID');
    } else {
      s.metrics.pages++;
      for (const record of records) {
        if (!RECORD_ID.test(record?.id || '') || s.seen.includes(record.id) ||
            !record.fields || typeof record.fields !== 'object' || Array.isArray(record.fields)) {
          block(s, 'RECORD_INVALID'); break;
        }
        s.seen.push(record.id); s.metrics.analyzed++;
        const time = timestamp(record.fields.processed_at);
        if (time === null || time > s.now) {
          s.metrics.invalid_dates++; failure(s, 'DATE_INVALID');
        } else if (time < Date.parse(s.cutoff)) {
          s.metrics.eligible++;
          // Mantem memoria limitada mesmo quando o total elegivel ultrapassa o teto.
          if (s.candidates.length < s.config.maxDelete + 1) {
            s.candidates.push({ id: record.id, time, processed_at: new Date(time).toISOString() });
          }
        } else s.metrics.recent++;
      }
      if (!s.blocked) {
        const offset = body.offset;
        if (offset !== undefined && (typeof offset !== 'string' || !/^[\x21-\x7e]{1,1024}$/.test(offset) ||
            !records.length || s.offsets.includes(offset))) block(s, 'PAGINATION_INVALID');
        else if (offset !== undefined) {
          if (s.metrics.pages >= s.config.maxPages || s.metrics.analyzed >= s.config.maxAnalyzed) block(s, 'SCAN_LIMIT');
          else { s.offsets.push(offset); s.offset = offset; s.action = 'list'; }
        } else {
          s.scan_complete = true;
          if (s.metrics.eligible > s.config.maxDelete) block(s, 'DELETE_LIMIT');
          else {
            s.action = 'audit_create';
            s.final_audit = s.config.dry_run || !s.candidates.length;
          }
        }
      }
    }
  } else if (action === 'audit_create') {
    if (!auditConfirmed(body, s)) {
      failure(s, 'AUDIT_FAILED'); s.audit_failed = true; s.blocked = true; finish(s);
    } else {
      s.audit_id = body.id;
      if (s.final_audit) { s.audit_finalized = true; finish(s); }
      else nextCandidate(s);
    }
  } else if (action === 'recheck') {
    const candidate = s.candidates[s.index];
    if (!Array.isArray(body?.records) || body.records.length > 1) block(s, 'RECHECK_INVALID');
    else {
      const record = body.records[0];
      const time = timestamp(record?.fields?.processed_at);
      if (record && record.id !== candidate.id) block(s, 'RECHECK_INVALID');
      else if (!record || time === null || time !== candidate.time || time >= Date.parse(s.cutoff)) {
        s.metrics.skipped_changed++; s.index++;
        if (record && time === null) { s.metrics.invalid_dates++; failure(s, 'DATE_INVALID'); }
        s.action = 'audit_update'; s.final_audit = s.index >= s.candidates.length;
      } else { s.recheck = { id: record.id, time }; s.action = 'delete'; }
    }
  } else if (action === 'delete') {
    if (body?.id !== s.candidates[s.index]?.id || body?.deleted !== true) {
      s.metrics.unknown_outcome++; block(s, 'DELETE_NOT_CONFIRMED');
    } else {
      s.metrics.deleted++; s.index++; s.recheck = null;
      s.action = 'audit_update'; s.final_audit = s.index >= s.candidates.length;
    }
  } else if (action === 'audit_update') {
    if (body?.id !== s.audit_id || !auditConfirmed(body, s)) {
      failure(s, 'AUDIT_FAILED'); s.audit_failed = true; s.blocked = true; finish(s);
    } else if (s.final_audit) { s.audit_finalized = true; finish(s); }
    else nextCandidate(s);
  } else block(s, 'STATE_INVALID');
}
// Nao propaga body, headers nem mensagens de erro recebidas do provedor.
return [{ json: { state: s }, pairedItem: { item: 0 } }];
