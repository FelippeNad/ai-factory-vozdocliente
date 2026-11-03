#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { compareMetadata, loadContract, syntheticDemo, formatText } = require('../scripts/diagnosticar_schema_retencao.cjs');
const { simulate } = require('./test_retention.cjs');
const clone = value => JSON.parse(JSON.stringify(value));
const contract = loadContract();

function valid() {
  const payload = syntheticDemo(contract);
  payload.response.body.tables[0].name = contract.reviewsName;
  return payload;
}

function runTests(report = console.log) {
  const tests = [];
  const test = (name, fn) => tests.push({ name, fn });
  const invalid = (name, edit, category, code) => test(name, () => {
    const input = valid(); edit(input);
    const result = compareMetadata(input);
    assert.equal(result.check_schema_result, false);
    assert.ok(result.issues.some(issue => issue.category === category && issue.code === code));
  });
  test('schema valido usa funcao real exportada', () => {
    const result = compareMetadata(valid());
    assert.equal(result.check_schema_result, true); assert.deepEqual(result.issues, []);
    assert.equal(result.fields.length, 19);
  });
  test('reproduz ReviewsRetentionTest com TODOS os tipos corretos', () => {
    const result = compareMetadata(syntheticDemo());
    assert.equal(result.check_schema_result, false);
    assert.equal(result.fields.every(field => field.ok), true);
    assert.deepEqual(result.issues.map(issue => issue.code), ['NOME_DE_TABELA_INCOMPATIVEL']);
  });
  test('nome esperado configurado e aceito pelo comparador e funcao real', () => {
    const input = syntheticDemo(); input.state.config.tableName = 'ReviewsRetentionTest';
    const result = compareMetadata(input);
    assert.equal(result.check_schema_result, true); assert.deepEqual(result.issues, []);
    assert.equal(result.expected_name_source, 'captured_config');
    assert.equal(result.tables[0].expected_name, 'ReviewsRetentionTest');
  });
  test('config capturada nao pode ser sobreposta por argumento de diagnostico', () => {
    assert.throws(() => compareMetadata(syntheticDemo(), { expectedReviews: 'ReviewsRetentionTest' }), /EXPECTED_NAME_CONFLICT/);
  });
  test('resposta sem estado com nome esperado explicito permanece inconclusiva quanto aos IDs', () => {
    const result = compareMetadata(syntheticDemo().response, { expectedReviews: 'ReviewsRetentionTest' });
    assert.equal(result.check_schema_result, null);
    assert.equal(result.provisional_result_using_name_selection, true);
    assert.equal(result.expected_name_source, 'diagnostic_argument');
  });
  test('execucao legada sem tableName explicita uso do padrao', () => {
    const input = valid(); delete input.state.config.tableName;
    const result = compareMetadata(input);
    assert.equal(result.check_schema_result, true); assert.equal(result.expected_name_source, 'default_Reviews');
  });
  for (const tableName of ['', null, 123, ' Reviews', 'Reviews\u200b']) test(`config de nome invalida nao e normalizada: ${JSON.stringify(tableName)}`, () => {
    const input = valid(); input.state.config.tableName = tableName;
    assert.throws(() => compareMetadata(input), /CONFIG/);
  });
  for (const name of ['reviews', 'Reviews ', 'Reviews\u200b']) invalid(`nome exato: ${JSON.stringify(name)}`,
    input => { input.response.body.tables[0].name = name; }, 'nome', 'NOME_DE_TABELA_INCOMPATIVEL');
  invalid('nome de auditoria incorreto', input => { input.response.body.tables[1].name = 'Audit'; }, 'nome', 'NOME_DE_TABELA_INCOMPATIVEL');
  invalid('ID reviews nao encontrado', input => { input.state.config.table = 'unknown'; }, 'configuracao', 'TABELA_CONFIGURADA_NAO_LOCALIZADA');
  invalid('ID audit nao encontrado', input => { input.state.config.auditTable = 'unknown'; }, 'configuracao', 'TABELA_CONFIGURADA_NAO_LOCALIZADA');
  invalid('IDs invertidos', input => {
    input.state.config.table = 'audit-id'; input.state.config.auditTable = 'reviews-id';
  }, 'nome', 'NOME_DE_TABELA_INCOMPATIVEL');
  invalid('body ausente', input => { delete input.response.body; }, 'estrutura', 'BODY_TABLES_NAO_E_ARRAY');
  invalid('body string', input => { input.response.body = '{}'; }, 'estrutura', 'BODY_TABLES_NAO_E_ARRAY');
  invalid('tables objeto em vez de array', input => { input.response.body.tables = {}; }, 'estrutura', 'BODY_TABLES_NAO_E_ARRAY');
  for (const position of [0, 1]) invalid(`fields nao e array ${position}`,
    input => { input.response.body.tables[position].fields = {}; }, 'estrutura', 'FIELDS_NAO_E_ARRAY');
  invalid('processed_at ausente', input => { input.response.body.tables[0].fields = []; }, 'nome', 'CAMPO_OBRIGATORIO_AUSENTE');
  invalid('processed_at com capitalizacao incorreta', input => { input.response.body.tables[0].fields[0].name = 'Processed_at'; }, 'nome', 'CAMPO_OBRIGATORIO_AUSENTE');
  for (const type of ['date', 'formula', 'singleLineText']) invalid(`processed_at tipo ${type}`,
    input => { input.response.body.tables[0].fields[0].type = type; }, 'tipo', 'TIPO_DE_CAMPO_INCOMPATIVEL');
  invalid('processed_at duas correspondencias validas', input => {
    input.response.body.tables[0].fields.push({ name: 'processed_at', type: 'dateTime' });
  }, 'quantidade', 'QUANTIDADE_DE_CORRESPONDENCIAS_INVALIDA');
  invalid('campo de auditoria ausente', input => { input.response.body.tables[1].fields.pop(); }, 'nome', 'CAMPO_OBRIGATORIO_AUSENTE');
  for (const [name, wrongType] of [['status', 'singleSelect'], ['run_id', 'autoNumber'],
    ['eligible', 'count'], ['retention_days', 'currency'], ['cutoff', 'date']]) invalid(`auditoria ${name} tipo ${wrongType}`,
    input => { input.response.body.tables[1].fields.find(field => field.name === name).type = wrongType; }, 'tipo', 'TIPO_DE_CAMPO_INCOMPATIVEL');
  test('coleta divergencias adicionais apos erro de nome', () => {
    const input = syntheticDemo(); input.response.body.tables[1].fields.pop();
    const result = compareMetadata(input);
    assert.ok(result.issues.some(issue => issue.code === 'NOME_DE_TABELA_INCOMPATIVEL'));
    assert.ok(result.issues.some(issue => issue.code === 'CAMPO_OBRIGATORIO_AUSENTE'));
  });
  test('campos extras nao sao rejeitados', () => {
    const input = valid();
    for (const table of input.response.body.tables) table.fields.push({ name: 'Extra', type: 'checkbox' });
    assert.equal(compareMetadata(input).check_schema_result, true);
  });
  test('options timezone precision e primaryFieldId nao sao verificados', () => {
    const input = valid();
    for (const table of input.response.body.tables) {
      table.primaryFieldId = 'qualquer';
      for (const field of table.fields) field.options = { timeZone: 'qualquer', precision: 3, includeTime: false };
    }
    assert.equal(compareMetadata(input).check_schema_result, true);
  });
  test('auditoria duplicada tem regra some, nao quantidade exata', () => {
    const input = valid(); input.response.body.tables[1].fields.push(clone(input.response.body.tables[1].fields[0]));
    assert.equal(compareMetadata(input).check_schema_result, true);
  });
  test('nome processed_at duplicado com somente um dateTime passa no codigo atual', () => {
    const input = valid(); input.response.body.tables[0].fields.push({ name: 'processed_at', type: 'date' });
    assert.equal(compareMetadata(input).check_schema_result, true);
  });
  test('JSON de HTTP sem config nao comprova IDs', () => {
    const result = compareMetadata(valid().response);
    assert.equal(result.check_schema_result, null);
    assert.equal(result.provisional_result_using_name_selection, true);
    assert.ok(result.issues.some(issue => issue.code === 'IDS_CONFIGURADOS_NAO_VERIFICADOS'));
  });
  test('selecao manual por nome e apenas diagnostica', () => {
    const result = compareMetadata(syntheticDemo().response, { reviews: 'ReviewsRetentionTest' });
    assert.equal(result.check_schema_result, null);
    assert.equal(result.provisional_result_using_name_selection, false);
    assert.ok(result.issues.some(issue => issue.category === 'nome'));
  });
  test('aceita copia de um unico item n8n', () => assert.equal(compareMetadata([{ json: valid() }]).check_schema_result, true));
  test('item de listagem nao e aceito como schema', () => {
    const input = valid(); input.state.action = 'list';
    assert.throws(() => compareMetadata(input), /INPUT_REQUIRES_SCHEMA_ACTION/);
  });
  test('tabela malformada pode causar excecao, nao SCHEMA_INVALID', () => {
    const input = valid(); input.response.body.tables.unshift(null);
    const result = compareMetadata(input);
    assert.equal(result.validator_threw, true); assert.equal(result.check_schema_result, null);
  });
  test('projecao n8n preserva selecao e remove informacoes desnecessarias', () => {
    const input = syntheticDemo();
    input.state.config.base = 'BASE-NAO-PUBLICAR';
    input.response.headers = { authorization: 'SEGREDO-SINTETICO' };
    input.response.body.records = [{ fields: { review_text: 'DADO-SINTETICO-NAO-PUBLICAR' } }];
    input.response.body.tables[0].fields[0].description = 'DESCRICAO-NAO-PUBLICAR';
    input.response.body.tables[0].fields[0].options = { choices: [{ name: 'VALOR-NAO-PUBLICAR' }] };
    const code = fs.readFileSync(path.join(__dirname, '../scripts/extrair_schema_retencao_n8n.js'), 'utf8');
    const output = vm.runInNewContext('(function(){' + code + '\n})()', { $input: { first: () => ({ json: input }) } }, { timeout: 1000 })[0].json;
    const projected = JSON.parse(JSON.stringify(output));
    assert.equal(projected.expected_reviews_name, input.state.config.tableName);
    const result = compareMetadata(projected);
    assert.equal(result.check_schema_result, false);
    const rendered = JSON.stringify(result) + formatText(result) + JSON.stringify(projected);
    for (const forbidden of ['reviews-id', 'audit-id', 'BASE-NAO-PUBLICAR', 'SEGREDO-SINTETICO',
      'DADO-SINTETICO-NAO-PUBLICAR', 'DESCRICAO-NAO-PUBLICAR', 'VALOR-NAO-PUBLICAR']) assert.ok(!rendered.includes(forbidden));
  });
  test('projecao preserva nome configurado de teste sem alterar expectativa', () => {
    const input = syntheticDemo(); input.state.config.tableName = 'ReviewsRetentionTest';
    const code = fs.readFileSync(path.join(__dirname, '../scripts/extrair_schema_retencao_n8n.js'), 'utf8');
    const output = vm.runInNewContext('(function(){' + code + '\n})()', { $input: { first: () => ({ json: input }) } }, { timeout: 1000 })[0].json;
    assert.equal(output.expected_reviews_name, 'ReviewsRetentionTest');
    assert.equal(compareMetadata(JSON.parse(JSON.stringify(output))).check_schema_result, true);
    output.tables[0].name = 'Reviews';
    assert.equal(compareMetadata(JSON.parse(JSON.stringify(output))).check_schema_result, false);
  });
  test('formato de texto explicita espacos e caracteres invisiveis em nomes', () => {
    const input = valid(); input.response.body.tables[0].name = 'Reviews\u200b';
    assert.ok(formatText(compareMetadata(input)).includes('Reviews\\u200b'));
  });
  test('motor bloqueia nome ReviewsRetentionTest antes de ler ou escrever registros', () => {
    const input = syntheticDemo();
    const result = simulate({ handler: (request, kind) => kind === 'schema' ? input.response : undefined });
    assert.deepEqual(result.summary.error_codes, ['SCHEMA_INVALID']);
    assert.equal(result.summary.analyzed, 0); assert.equal(result.summary.deleted, 0);
    assert.equal(result.summary.audit_persisted, false); assert.equal(result.requests.length, 1);
    assert.equal(result.requests[0].method, 'GET');
  });
  let failed = 0;
  for (const { name, fn } of tests) {
    try { fn(); report(`[OK] ${name}`); }
    catch (error) { failed++; report(`[FALHA] ${name}: ${error.message}`); }
  }
  report(`RESULTADO: ${tests.length - failed} passaram, ${failed} falharam`);
  return { passed: tests.length - failed, failed, total: tests.length };
}

module.exports = { runTests };
if (require.main === module) process.exitCode = runTests().failed ? 1 : 0;
