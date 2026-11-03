// Variante DEV: sem fallback para a base da classificacao publicada e sem logs.
const base = $env.CLASSIFIER_DEV_BASE_ID, table = $env.CLASSIFIER_DEV_TABLE_ID;
if ($env.CLASSIFIER_ENV !== 'DEV' || typeof base !== 'string' || base.trim() !== base
    || !/^app[A-Za-z0-9]{14}$/.test(base) || typeof table !== 'string' || table.trim() !== table
    || !/^tbl[A-Za-z0-9]{14}$/.test(table)) {
  throw new Error('Configuracao DEV de classificacao invalida.');
}
const items = $input.all();
const reviewId = $('Webhook Review').first().json.body?.review_id;
// Identificadores opacos limitados: nao interpolar aspas, formulas ou texto pessoal.
if (items.length !== 1 || typeof reviewId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(reviewId)
    || reviewId.trim() !== reviewId) throw new Error('review_id invalido para deduplicacao.');
const text = items[0].json.review_text_sanitized;
if (typeof text !== 'string' || !text.trim()) throw new Error('Texto sanitizado ausente ou invalido.');
return [{ json: { review_id: reviewId, review_text_sanitized: text,
  lookup_url: 'https://api.airtable.com/v0/' + base + '/' + table },
  pairedItem: { item: 0 } }];
