// Stub incorporado SOMENTE na demonstracao: nenhuma rede, escrita ou exclusao.
const input = $input.first().json;
const s = input.state;
const date = days => new Date(s.now - days * 86400000).toISOString();
const rec = (number, processed_at) => ({ id: 'rec' + String(number).padStart(14, '0'),
  fields: processed_at === null ? {} : { processed_at } });
let body;
let statusCode = 200;
if (s.action === 'schema') {
  body = { tables: [
    { id: s.config.table, name: s.config.tableName, fields: [{ name: 'processed_at', type: 'dateTime' }] },
    { id: s.config.auditTable, name: 'RetentionAudit',
      fields: Object.entries(AUDIT_TYPES).map(([name, type]) => ({ name, type })) },
  ] };
} else if (s.action === 'list') {
  const pages = [
    { records: [rec(1, date(60)), rec(2, date(45))], offset: 'demo-page-2' },
    { records: [rec(3, date(1)), rec(4, s.cutoff)], offset: 'demo-page-3' },
    { records: [rec(5, '2026-02-30T00:00:00Z'), rec(6, null)] },
  ];
  body = pages[s.metrics.pages];
} else if (s.action === 'audit_create' || s.action === 'audit_update') {
  body = { id: 'rec00000000000999', fields: input.request.body.fields };
} else {
  // Mesmo uma mudanca acidental de modo nao habilita DELETE neste stub.
  statusCode = 405; body = { error: 'DEMO_READ_ONLY' };
}
return [{ json: { statusCode, body }, pairedItem: { item: 0 } }];
