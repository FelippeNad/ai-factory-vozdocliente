// Erro/resultado ambiguo nunca habilita o LLM. Nao propaga resposta Airtable.
const response = $input.first().json;
const records = response.body?.records;
const prepared = $('Preparar deduplicacao DEV').item.json;
if (response.statusCode !== 200 || !Array.isArray(records) || records.length > 1
    || records.some(record => !/^rec[A-Za-z0-9]{14}$/.test(record?.id || '')
      || record.fields?.review_id !== prepared.review_id)) {
  throw new Error('Resposta de deduplicacao invalida.');
}
const text = $('Sanitizar PII').item.json.review_text_sanitized;
if (typeof text !== 'string' || !text.trim()) throw new Error('Texto sanitizado ausente ou invalido.');
return [{ json: { duplicate: records.length === 1, review_text_sanitized: text }, pairedItem: { item: 0 } }];
