#!/usr/bin/env node
'use strict';

// Somente leitura local. Nao importa clientes HTTP, nao le .env e nao acessa $env.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.join(__dirname, '..');

function loadContract() {
  const workflow = JSON.parse(fs.readFileSync(path.join(ROOT,
    'n8n-mirror/workflows/vozdocliente-retencao-v1.json'), 'utf8'));
  const code = workflow.nodes.find(node => node.name === 'Motor de retencao')?.parameters.jsCode;
  const marker = 'const input = $input.first().json;';
  if (typeof code !== 'string' || code.split(marker).length !== 2) throw Error('CONTRACT_UNSUPPORTED');
  // Carrega somente as declaracoes comuns: nao executa o motor nem o guard.
  const helpers = vm.runInNewContext('(function () {' + code.split(marker)[0]
    + '\nreturn { checkSchema, AUDIT_TYPES, expectedTableName }; })()', {}, { timeout: 1000 });
  const source = helpers.checkSchema.toString();
  const audit = source.match(/audit\?\.name !== '([^']+)'/);
  const field = source.match(/reviews\.fields\.filter\(field => field\.name === '([^']+)' && field\.type === '([^']+)'\)\.length !== 1/);
  if (!source.includes('reviews?.name !== config.tableName') || !audit || !field ||
      !source.includes('audit.fields.some(')) throw Error('CONTRACT_UNSUPPORTED');
  return { reviewsName: helpers.expectedTableName(undefined), auditName: audit[1], reviewField: field[1], reviewType: field[2],
    auditTypes: JSON.parse(JSON.stringify(helpers.AUDIT_TYPES)), checkSchema: helpers.checkSchema,
    expectedTableName: helpers.expectedTableName };
}

const stringOrNull = value => typeof value === 'string' ? value : null;
const fieldsOnly = fields => Array.isArray(fields) ? fields.map(field => field && typeof field === 'object'
  ? { name: stringOrNull(field.name), type: stringOrNull(field.type) } : null) : null;

function projectMetadata(payload, contract, names = {}) {
  // Aceita copia de um unico item n8n ou o objeto JSON desse item.
  if (Array.isArray(payload)) {
    if (payload.length !== 1) throw Error('INPUT_REQUIRES_ONE_ITEM');
    payload = payload[0];
  }
  if (payload?.json && !payload.tables && !payload.response && !payload.body && !payload.kind) payload = payload.json;
  if (!payload || typeof payload !== 'object') throw Error('INPUT_INVALID');
  const capturedName = payload.kind === 'retention_schema_metadata_v1'
    ? payload.expected_reviews_name : payload.state?.config?.tableName;
  if (capturedName !== undefined && names.expectedReviews !== undefined &&
      capturedName !== names.expectedReviews) throw Error('EXPECTED_NAME_CONFLICT');
  const expectedName = contract.expectedTableName(capturedName !== undefined ? capturedName : names.expectedReviews);
  const expectedNameSource = capturedName !== undefined ? 'captured_config'
    : names.expectedReviews !== undefined ? 'diagnostic_argument' : 'default_Reviews';
  if (payload.kind === 'retention_schema_metadata_v1') {
    return { kind: payload.kind, selection_verified: payload.selection_verified === true,
      expected_reviews_name: expectedName, expected_name_source: expectedNameSource,
      tables_is_array: payload.tables_is_array === true && Array.isArray(payload.tables),
      tables: Array.isArray(payload.tables) ? payload.tables.map(table => table && typeof table === 'object' ? {
        name: stringOrNull(table.name), selected_reviews: table.selected_reviews === true,
        selected_audit: table.selected_audit === true, fields: fieldsOnly(table.fields),
      } : null) : [] };
  }
  const config = payload.state?.config;
  if (payload.response && payload.state?.action !== 'schema') throw Error('INPUT_REQUIRES_SCHEMA_ACTION');
  const verified = typeof config?.table === 'string' && typeof config?.auditTable === 'string';
  if (verified && config.table === config.auditTable) throw Error('INPUT_INVALID_TABLE_SELECTION');
  const body = payload.response ? payload.response.body : payload.body ?? payload;
  const tables = Array.isArray(body?.tables) ? body.tables : [];
  return { kind: 'retention_schema_metadata_v1', selection_verified: verified,
    expected_reviews_name: expectedName, expected_name_source: expectedNameSource,
    tables_is_array: Array.isArray(body?.tables),
    tables: tables.map(table => table && typeof table === 'object' ? {
      name: stringOrNull(table.name),
      selected_reviews: verified ? table.id === config.table : table.name === (names.reviews ?? expectedName),
      selected_audit: verified ? table.id === config.auditTable : table.name === (names.audit ?? contract.auditName),
      fields: fieldsOnly(table.fields),
    } : null) };
}

function compareMetadata(payload, names = {}, contract = loadContract()) {
  const metadata = projectMetadata(payload, contract, names);
  const issues = [], fields = [], tables = [];
  const issue = (category, code, role = null, field = null) => issues.push({ category, code, role, field });
  if (!metadata.selection_verified) issue('configuracao', 'IDS_CONFIGURADOS_NAO_VERIFICADOS');
  if (!metadata.tables_is_array) issue('estrutura', 'BODY_TABLES_NAO_E_ARRAY');
  if (metadata.tables.some(table => table === null)) issue('estrutura', 'ENTRADA_DE_TABELA_MALFORMADA');
  if (metadata.tables.some(table => table?.selected_reviews && table?.selected_audit)) issue('configuracao', 'SELECAO_SOBREPOSTA');

  for (const [role, expectedName, selection, expectedFields] of [
    ['reviews', metadata.expected_reviews_name, 'selected_reviews', { [contract.reviewField]: contract.reviewType }],
    ['audit', contract.auditName, 'selected_audit', contract.auditTypes],
  ]) {
    const matches = metadata.tables.filter(table => table?.[selection]);
    const selected = matches[0]; // O codigo operacional tambem usa find: primeira correspondencia.
    tables.push({ role, expected_name: expectedName, observed_name: selected?.name ?? null,
      fields_count: selected?.fields?.length ?? null,
      expected_fields_count: Object.keys(expectedFields).length,
      // Informativo, nao limite total: extras sao permitidos no codigo operacional.
      selection_matches: matches.length });
    if (!selected) { issue('configuracao', 'TABELA_CONFIGURADA_NAO_LOCALIZADA', role); continue; }
    if (selected.name !== expectedName) issue('nome', 'NOME_DE_TABELA_INCOMPATIVEL', role);
    if (!Array.isArray(selected.fields)) { issue('estrutura', 'FIELDS_NAO_E_ARRAY', role); continue; }
    if (selected.fields.some(field => field === null)) issue('estrutura', 'ENTRADA_DE_CAMPO_MALFORMADA', role);
    for (const [name, type] of Object.entries(expectedFields)) {
      const sameName = selected.fields.filter(field => field?.name === name);
      const exact = sameName.filter(field => field.type === type);
      const ok = role === 'reviews' ? exact.length === 1 : exact.length >= 1;
      fields.push({ role, name, expected_type: type,
        observed_types: sameName.map(field => field.type),
        matching_names: sameName.length, matching_name_and_type: exact.length,
        required_matches: role === 'reviews' ? 'exactly_one' : 'at_least_one', ok });
      if (sameName.length === 0) issue('nome', 'CAMPO_OBRIGATORIO_AUSENTE', role, name);
      else if (exact.length === 0) issue('tipo', 'TIPO_DE_CAMPO_INCOMPATIVEL', role, name);
      else if (!ok) issue('quantidade', 'QUANTIDADE_DE_CORRESPONDENCIAS_INVALIDA', role, name);
    }
  }
  // Reconstitui apenas identidades simbolicas para executar a funcao REAL.
  // Nao imprime nem retorna IDs reais, config, headers, options ou valores de registros.
  const shape = metadata.tables_is_array ? { tables: metadata.tables.map((table, index) => table ? {
    id: table.selected_reviews ? 'reviews' : table.selected_audit ? 'audit' : 'other-' + index,
    name: table.name, fields: table.fields,
  } : null) } : {};
  let accepted = null, threw = false;
  try { accepted = contract.checkSchema(shape, { table: 'reviews', tableName: metadata.expected_reviews_name, auditTable: 'audit' }); }
  catch { threw = true; issue('estrutura', 'VALIDADOR_LANCARIA_EXCECAO'); }
  const selectionInvalid = issues.some(item => item.code === 'SELECAO_SOBREPOSTA');
  return {
    scope: 'DIAGNOSTICO_LOCAL_SEM_REDE',
    selection_verified: metadata.selection_verified,
    expected_name_source: metadata.expected_name_source,
    check_schema_result: metadata.selection_verified && !selectionInvalid ? accepted : null,
    provisional_result_using_name_selection: !metadata.selection_verified ? accepted : null,
    validator_threw: threw,
    tables, fields, issues,
    observed_tables: metadata.tables.filter(Boolean).map(table => ({ name: table.name,
      fields: table.fields })),
    properties_checked: ['configured_table_identity', 'table.name', 'fields_array', 'field.name', 'field.type', 'matching_count'],
    options_checked: false,
  };
}

function syntheticDemo(contract = loadContract()) {
  return { state: { action: 'schema', config: { table: 'reviews-id', tableName: contract.reviewsName, auditTable: 'audit-id' } },
    response: { statusCode: 200, body: { tables: [
      { id: 'reviews-id', name: 'ReviewsRetentionTest', fields: [{ name: contract.reviewField, type: contract.reviewType }] },
      { id: 'audit-id', name: contract.auditName,
        fields: Object.entries(contract.auditTypes).map(([name, type]) => ({ name, type })) },
    ] } } };
}

function formatText(report) {
  const q = value => value === null ? '(ausente)' : JSON.stringify(value)
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g, char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
  const lines = ['DIAGNOSTICO LOCAL: nomes/tipos; sem IDs, tokens, headers ou valores de registros.',
    'Selecao pelos IDs configurados confirmada: ' + report.selection_verified,
    'Origem do nome esperado: ' + report.expected_name_source,
    'checkSchema: ' + (report.check_schema_result === null ? 'inconclusivo' : report.check_schema_result),
    'Options/Include time/timeZone/precision/primaryFieldId: nao examinados pelo validador.'];
  for (const table of report.tables) lines.push('Tabela ' + table.role + ': esperado=' + q(table.expected_name)
    + '; recebido=' + q(table.observed_name) + '; total de campos=' + table.fields_count
    + '; campos obrigatorios=' + table.expected_fields_count + ' (nao e limite total)');
  for (const field of report.fields) lines.push((field.ok ? '[OK] ' : '[DIVERGENCIA] ') + field.role + '.' + q(field.name)
    + ': esperado=' + q(field.expected_type) + '; tipos recebidos=' + q(field.observed_types)
    + '; correspondencias=' + field.matching_name_and_type + '; regra=' + field.required_matches);
  for (const item of report.issues) lines.push('[' + item.category + '] ' + item.code
    + (item.role ? ' (' + item.role + (item.field ? '.' + q(item.field) : '') + ')' : ''));
  lines.push('Nomes/tipos presentes nos metadados (sem options):');
  for (const table of report.observed_tables) {
    lines.push('  ' + q(table.name));
    if (table.fields) for (const field of table.fields) lines.push('    ' + q(field?.name ?? null) + ': ' + q(field?.type ?? null));
  }
  return lines.join('\n');
}

function main(args) {
  try {
    const options = {};
    for (let index = 0; index < args.length; index++) {
      const arg = args[index];
      if (['--demo', '--json'].includes(arg)) options[arg] = true;
      else if (['--input', '--reviews-name', '--audit-name', '--expected-table-name'].includes(arg) && args[index + 1] && !args[index + 1].startsWith('--')) options[arg] = args[++index];
      else throw Error('ARGS_INVALID');
    }
    if (!!options['--demo'] === !!options['--input']) {
      console.log('Uso: node scripts/diagnosticar_schema_retencao.cjs --demo [--json]');
      console.log('Ou:  node scripts/diagnosticar_schema_retencao.cjs --input <metadados.json|-> [--expected-table-name ReviewsRetentionTest] [--reviews-name ReviewsRetentionTest] [--audit-name RetentionAudit] [--json]');
      return 2;
    }
    if (options['--input'] && path.basename(options['--input']).startsWith('.env')) throw Error('ENV_NOT_ALLOWED');
    const contract = loadContract();
    const payload = options['--demo'] ? syntheticDemo(contract) : JSON.parse(fs.readFileSync(options['--input'] === '-' ? 0 : options['--input'], 'utf8').replace(/^\uFEFF/, ''));
    const report = compareMetadata(payload, { reviews: options['--reviews-name'], audit: options['--audit-name'],
      expectedReviews: options['--expected-table-name'] }, contract);
    report.synthetic_demo = options['--demo'] === true;
    if (options['--demo'] && !options['--json']) console.log('DEMONSTRACAO SINTETICA; nao sao metadados da sua base.');
    console.log(options['--json'] ? JSON.stringify(report, null, 2) : formatText(report));
    return report.check_schema_result === true ? 0 : 1;
  } catch {
    console.error('Diagnostico indisponivel: verifique argumentos, JSON de metadados e contrato local. Conteudo de entrada omitido.');
    return 2;
  }
}

module.exports = { loadContract, projectMetadata, compareMetadata, syntheticDemo, formatText, main };
if (require.main === module) process.exitCode = main(process.argv.slice(2));
