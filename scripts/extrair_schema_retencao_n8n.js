// Para node Code ISOLADO, sem HTTP/credentials, alimentado pelo item JA OBTIDO
// de "Receber resposta" cujo state.action === 'schema'. Nao conectar ao motor.
const input = $input.first().json;
if (input.state?.action !== 'schema' || !input.state.config || !input.response) {
  throw new Error('Selecione somente o item de metadados da etapa schema.');
}
const config = input.state.config;
if (typeof config.table !== 'string' || typeof config.auditTable !== 'string' || config.table === config.auditTable ||
    (config.tableName !== undefined && typeof config.tableName !== 'string')) {
  throw new Error('Selecao de tabelas indisponivel para diagnostico.');
}
const tables = input.response.body?.tables;
return [{ json: {
  kind: 'retention_schema_metadata_v1',
  selection_verified: true,
  // Ausente em execucoes da versao anterior: o comparador explicita default_Reviews.
  ...(config.tableName === undefined ? {} : { expected_reviews_name: config.tableName }),
  tables_is_array: Array.isArray(tables),
  tables: Array.isArray(tables) ? tables.map(table => table && typeof table === 'object' ? {
    name: typeof table.name === 'string' ? table.name : null,
    selected_reviews: table.id === config.table,
    selected_audit: table.id === config.auditTable,
    fields: Array.isArray(table.fields) ? table.fields.map(field => field && typeof field === 'object' ? {
      name: typeof field.name === 'string' ? field.name : null,
      type: typeof field.type === 'string' ? field.type : null,
    } : null) : null,
  } : null) : [],
} }];
