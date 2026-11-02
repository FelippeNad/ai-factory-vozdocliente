// Fonte compartilhada incorporada ao JSON por scripts/build_retention_workflow.py.
// Sem rede, dependencias, secrets, console ou texto de reviews.
const RECORD_ID = /^rec[A-Za-z0-9]{14}$/;
const METRICS = ['analyzed', 'eligible', 'deleted', 'failures', 'invalid_dates',
  'recent', 'pages', 'attempted', 'skipped_changed', 'unknown_outcome'];
const AUDIT_TYPES = {
  run_id: 'singleLineText', mode: 'singleLineText', status: 'singleLineText',
  error_codes: 'singleLineText', retention_days: 'number', cutoff: 'dateTime',
  started_at: 'dateTime', updated_at: 'dateTime',
  ...Object.fromEntries(METRICS.map(key => [key, 'number'])),
};

function settings(env) {
  const integer = (key, fallback, max) => {
    const value = env[key] === undefined || env[key] === '' ? String(fallback) : env[key];
    if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value) || Number(value) > max) throw Error('CONFIG');
    return Number(value);
  };
  const dry = env.RETENTION_DRY_RUN === undefined || env.RETENTION_DRY_RUN === ''
    ? 'true' : env.RETENTION_DRY_RUN;
  if (!['true', 'false'].includes(dry) || env.RETENTION_ENV !== 'DEV') throw Error('CONFIG');
  const base = env.RETENTION_DEV_BASE_ID;
  const table = env.RETENTION_TABLE_ID;
  const auditTable = env.RETENTION_AUDIT_TABLE_ID;
  if (!/^app[A-Za-z0-9]{14}$/.test(base || '') || !/^tbl[A-Za-z0-9]{14}$/.test(table || '') ||
      !/^tbl[A-Za-z0-9]{14}$/.test(auditTable || '') || table === auditTable) throw Error('CONFIG');
  const protectedBases = (env.RETENTION_PROTECTED_BASE_IDS || '').split(',').filter(Boolean);
  if (protectedBases.some(id => !/^app[A-Za-z0-9]{14}$/.test(id)) || protectedBases.includes(base)) throw Error('CONFIG');
  if (dry === 'false' && (!protectedBases.length || env.RETENTION_CONFIRM_DEV_BASE_ID !== base ||
      env.RETENTION_DELETE_CONFIRMATION !== 'DELETE_DEV_EXPIRED_REVIEWS')) throw Error('CONFIG');
  return { environment: 'DEV', dry_run: dry === 'true', base, table, auditTable,
    days: integer('RETENTION_DAYS', 30, 3650),
    pageSize: integer('RETENTION_PAGE_SIZE', 100, 100),
    maxPages: integer('RETENTION_MAX_PAGES', 10, 50),
    maxAnalyzed: integer('RETENTION_MAX_ANALYZED', 1000, 5000),
    maxDelete: integer('RETENTION_MAX_DELETE', 10, 100),
    // Detecta mudancas da denylist/confirmacoes durante uma execucao.
    protectedBases: [...protectedBases].sort(),
    confirmation: env.RETENTION_CONFIRM_DEV_BASE_ID || '',
    deleteConfirmation: env.RETENTION_DELETE_CONFIRMATION || '',
  };
}

function timestamp(value) {
  // Nao usa Date.parse sozinho: ele normaliza datas impossiveis como 30/02.
  if (typeof value !== 'string') return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?(Z|[+-]\d{2}:\d{2})$/);
  if (!match) return null;
  const [, year, month, day, hour, minute, second, , zone] = match;
  const y = Number(year), m = Number(month), d = Number(day);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (y < 1 || m < 1 || m > 12 || d < 1 || d > days[m - 1] ||
      Number(hour) > 23 || Number(minute) > 59 || Number(second) > 59) return null;
  if (zone !== 'Z' && (Number(zone.slice(1, 3)) > 14 || Number(zone.slice(4)) > 59 ||
      (zone.slice(1, 3) === '14' && zone.slice(4) !== '00'))) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function failure(s, code) {
  s.metrics.failures++;
  if (!s.codes.includes(code)) s.codes.push(code);
}

function status(s) {
  if (s.blocked) return 'blocked';
  if (s.metrics.failures) return 'partial';
  return s.config.dry_run ? 'dry_run' : 'completed';
}

function auditFields(s, state) {
  return { run_id: s.run_id, mode: s.config.dry_run ? 'DRY_RUN' : 'DELETE_DEV',
    status: state, error_codes: s.codes.join(','), retention_days: s.config.days,
    cutoff: s.cutoff, started_at: s.started_at, updated_at: new Date().toISOString(), ...s.metrics };
}

function auditConfirmed(body, s) {
  if (!RECORD_ID.test(body?.id || '') || !body.fields || !s.audit_expected) return false;
  return Object.entries(s.audit_expected).every(([name, value]) => {
    // Airtable omite campos vazios na resposta.
    if (name === 'error_codes' && value === '') return !body.fields[name];
    if (AUDIT_TYPES[name] === 'dateTime') return timestamp(body.fields[name]) === timestamp(value);
    return body.fields[name] === value;
  });
}

function finish(s) { s.done = true; s.action = null; return s; }

function auditOrFinish(s) {
  if (!s.schema_verified || s.audit_failed) return finish(s);
  s.action = s.audit_id ? 'audit_update' : 'audit_create';
  s.final_audit = true;
  return s;
}

function block(s, code) {
  failure(s, code); s.blocked = true;
  return auditOrFinish(s);
}

function nextCandidate(s) {
  s.recheck = null;
  if (s.blocked || s.index >= s.candidates.length) return auditOrFinish(s);
  s.action = 'recheck';
  return s;
}

function checkSchema(body, config) {
  if (!body || !Array.isArray(body.tables)) return false;
  const reviews = body.tables.find(table => table.id === config.table);
  const audit = body.tables.find(table => table.id === config.auditTable);
  if (reviews?.name !== 'Reviews' || audit?.name !== 'RetentionAudit') return false;
  if (!Array.isArray(reviews.fields) || !Array.isArray(audit.fields)) return false;
  if (reviews.fields.filter(field => field.name === 'processed_at' && field.type === 'dateTime').length !== 1) return false;
  return Object.entries(AUDIT_TYPES).every(([name, type]) =>
    audit.fields.some(field => field.name === name && field.type === type));
}
