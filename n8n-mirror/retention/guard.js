const s = $input.first().json.state;
let request = null;
if (!s.done) {
  try {
    const current = settings($env);
    if (JSON.stringify(current) !== JSON.stringify(s.config)) throw Error('CONFIG_CHANGED');
    if (Date.now() > s.deadline && !['audit_create', 'audit_update'].includes(s.action)) {
      block(s, 'TIME_LIMIT');
    }
    if (s.action === 'delete') {
      const candidate = s.candidates[s.index];
      if (current.dry_run || !s.schema_verified || !s.scan_complete || !s.audit_id || s.audit_failed || s.blocked ||
          !candidate || !RECORD_ID.test(candidate.id) || s.recheck?.id !== candidate.id ||
          s.recheck?.time !== candidate.time || candidate.time >= Date.parse(s.cutoff) ||
          timestamp(s.cutoff) !== s.now - current.days * 86400000 ||
          s.metrics.eligible > current.maxDelete || s.metrics.attempted >= current.maxDelete) throw Error('DELETE_BLOCKED');
    }
    const baseUrl = 'https://api.airtable.com/v0/' + current.base;
    const reviewsUrl = baseUrl + '/' + current.table;
    const auditUrl = baseUrl + '/' + current.auditTable;
    const query = [['fields[]', 'processed_at']];
    const urlWithQuery = (url, pairs) => url + '?' + pairs.map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
    if (s.action === 'schema') {
      request = { method: 'GET', url: 'https://api.airtable.com/v0/meta/bases/' + current.base + '/tables' };
    } else if (s.action === 'list' && s.schema_verified && !s.blocked) {
      query.push(['pageSize', Math.min(current.pageSize, current.maxAnalyzed - s.metrics.analyzed)]);
      if (s.offset) query.push(['offset', s.offset]);
      request = { method: 'GET', url: urlWithQuery(reviewsUrl, query) };
    } else if (s.action === 'recheck' && !current.dry_run && s.audit_id && !s.blocked) {
      const candidate = s.candidates[s.index];
      if (!candidate || !RECORD_ID.test(candidate.id)) throw Error('STATE');
      query.push(['filterByFormula', "RECORD_ID()='" + candidate.id + "'"], ['maxRecords', 1], ['pageSize', 1]);
      request = { method: 'GET', url: urlWithQuery(reviewsUrl, query) };
    } else if (s.action === 'delete') {
      request = { method: 'DELETE', url: reviewsUrl + '/' + s.candidates[s.index].id };
      s.metrics.attempted++;
    } else if (['audit_create', 'audit_update'].includes(s.action) && s.schema_verified && !s.audit_failed) {
      if (s.action === 'audit_update' && !RECORD_ID.test(s.audit_id || '')) throw Error('STATE');
      s.audit_expected = auditFields(s, s.final_audit ? status(s) : s.action === 'audit_create' ? 'planned' : 'running');
      request = { method: s.action === 'audit_create' ? 'POST' : 'PATCH',
        url: auditUrl + (s.action === 'audit_update' ? '/' + s.audit_id : ''),
        body: { fields: s.audit_expected } };
    } else if (!s.done) throw Error('STATE');
  } catch {
    failure(s, 'GUARD_BLOCKED'); s.blocked = true; finish(s);
  }
}
return [{ json: { state: s, request, has_request: request !== null }, pairedItem: { item: 0 } }];
