#!/usr/bin/env node
'use strict';

// Executa o JavaScript REAL exportado pelo n8n, sem HTTP nem dependencias npm.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function runTests(report = console.log) {
  const workflow = JSON.parse(fs.readFileSync(path.join(__dirname,
    '../n8n-mirror/workflows/vozdocliente-router-v4.json'), 'utf8'));
  const nodes = Object.fromEntries(workflow.nodes.map(node => [node.name, node]));
  const tests = [];
  const test = (label, fn) => tests.push({ label, fn });
  const plain = value => JSON.parse(JSON.stringify(value));
  const runCode = (name, globals) => plain(vm.runInNewContext(
    `(function () { ${nodes[name].parameters.jsCode}\n})()`, globals, { timeout: 1000 }));
  const sanitizeItems = items => runCode('Sanitizar PII', { $input: { all: () => items } });
  const sanitize = text => sanitizeItems([{ json: { body: { review_text: text } } }])[0].json.review_text_sanitized;
  // Simula somente a interpolacao usada nos JSON bodies; nao substitui teste de importacao n8n.
  const body = (name, globals) => JSON.parse(nodes[name].parameters.jsonBody.slice(1)
    .replace(/\{\{([\s\S]*?)\}\}/g, (_, expr) => String(
      vm.runInNewContext(expr, globals, { timeout: 1000 }))));
  const parse = (raw, webhook = {}) => runCode('Parse + Merge', {
    $json: { choices: [{ message: { content: raw } }] },
    $: name => { assert.equal(name, 'Webhook Review'); return { first: () => ({ json: { body: webhook } }) }; },
  });

  // Numeros deliberadamente ficticios, sem validacao de digitos verificadores.
  const cases = [
    ['CPF pontuado', '000.000.000-00', '[CPF]'],
    ['CPF compacto', '00000000000', '[CPF]'],
    ['CPF com espacos', '000 000 000 00', '[CPF]'],
    ['CPF espacos em volta da pontuacao', '000 . 000 . 000 - 00', '[CPF]'],
    ['CNPJ pontuado', '00.000.000/0000-00', '[CNPJ]'],
    ['CNPJ compacto', '00000000000000', '[CNPJ]'],
    ['CNPJ com espacos', '00 000 000 0000 00', '[CNPJ]'],
    ['CNPJ espacos em volta da pontuacao', '00 . 000 . 000 / 0000 - 00', '[CNPJ]'],
    ['CNPJ alfanumerico pontuado', 'AA.AAA.AAA/AAAA-00', '[CNPJ]'],
    ['CNPJ alfanumerico compacto', 'AAAAAAAAAAAA00', '[CNPJ]'],
    ['email', 'pessoa@example.invalid', '[EMAIL]'],
    ['email alias e subdominio', 'cliente.teste+cx@sub.example.invalid', '[EMAIL]'],
    ['email maiusculo', 'TESTE@EXAMPLE.INVALID', '[EMAIL]'],
    ['email unicode', 'usuário@example.invalid', '[EMAIL]'],
    ['telefone com DDD', '(00) 90000-0000', '[TELEFONE]'],
    ['telefone fixo', '(00) 0000-0000', '[TELEFONE]'],
    ['telefone internacional', '+55 (00) 90000-0000', '[TELEFONE]'],
    ['telefone com espacos', '+55 00 90000 0000', '[TELEFONE]'],
    ['telefone nono digito separado', '+55 (00) 9 0000-0000', '[TELEFONE]'],
    ['telefone pontos', '00.90000.0000', '[TELEFONE]'],
    ['telefone compacto internacional', '+5500900000000', '[TELEFONE]'],
    ['telefone sem DDD', '90000-0000', '[TELEFONE]'],
    ['telefone fixo sem DDD', '0000-0000', '[TELEFONE]'],
    ['telefone local rotulado', 'telefone: 900000000', 'telefone: [TELEFONE]'],
    ['telefone 0800', '0800 000 0000', '[TELEFONE]'],
    ['CEP hifen', '00000-000', '[CEP]'],
    ['CEP compacto', '00000000', '[CEP]'],
    ['CEP espaco', '00000 000', '[CEP]'],
    ['CEP ponto', '00000.000', '[CEP]'],
    ['URL HTTPS e query', 'https://example.invalid/pessoa?id=00000000000&email=teste@example.invalid', '[URL]'],
    ['URL HTTP', 'http://example.invalid', '[URL]'],
    ['URL FTP', 'ftp://example.invalid/arquivo', '[URL]'],
    ['URL WWW maiuscula', 'WWW.EXAMPLE.INVALID/perfil', '[URL]'],
    ['dominio sem protocolo', 'example.invalid/perfil?id=00000000000', '[URL]'],
    ['dominio BR', 'loja.example.com.br/cliente', '[URL]'],
    ['URL com pontuacao final', 'https://example.invalid/perfil.', '[URL].'],
    ['URL entre parenteses', '(https://example.invalid/perfil)', '([URL])'],
    ['digitos unicode fullwidth', '０００.０００.０００-００', '[CPF]'],
    ['caractere invisivel', 'teste@exam\u200bple.invalid', '[EMAIL]'],
    ['telefone compacto ambiguo', '00900000000', '[CPF]'],
  ];
  for (const [label, input, expected] of cases) {
    test(label, () => assert.equal(sanitize(input), expected));
  }
  test('substitui repeticoes e todos os tipos no mesmo texto', () => {
    const result = sanitize('Pessimo SAC. CPF 000.000.000-00; CNPJ 00.000.000/0000-00; '
      + 'a@example.invalid e a@example.invalid; +55 (00) 90000-0000; CEP 00000-000; https://example.invalid.');
    assert.equal(result, 'Pessimo SAC. CPF [CPF]; CNPJ [CNPJ]; [EMAIL] e [EMAIL]; [TELEFONE]; CEP [CEP]; [URL].');
  });
  test('marcadores sao idempotentes', () => {
    const once = sanitize('O app trava. teste@example.invalid; 000.000.000-00');
    assert.equal(sanitize(once), once);
  });
  test('texto sem PII preservado, incluindo preco, acentos e pontuacao', () => {
    const text = 'Entrega em 2 dias, preço R$ 29,90. Ótimo produto! Nota 5/5.';
    assert.equal(sanitize(text), text);
  });
  test('nao altera o payload nem copia metadados, headers ou outros campos', () => {
    const items = [{ json: { body: { review_text: 'app trava teste@example.invalid',
      customer_name: 'Pessoa Sintética', review_text_sanitized: 'INJETADO' },
      headers: { authorization: 'SINTETICO' } } }];
    const original = JSON.stringify(items);
    assert.deepEqual(sanitizeItems(items), [{ json: { review_text_sanitized: 'app trava [EMAIL]' }, pairedItem: { item: 0 } }]);
    assert.equal(JSON.stringify(items), original);
  });
  test('sanitiza todos os itens com pareamento', () => {
    assert.deepEqual(sanitizeItems(['a@example.invalid', '00000-000'].map(review_text => ({ json: { body: { review_text } } }))), [
      { json: { review_text_sanitized: '[EMAIL]' }, pairedItem: { item: 0 } },
      { json: { review_text_sanitized: '[CEP]' }, pairedItem: { item: 1 } },
    ]);
  });
  const invalid = [undefined, null, '', ' \n\t', '\u200b', 42, false, [], {}, ['texto'], 'x'.repeat(20001)];
  invalid.forEach((value, index) => test(`texto invalido ${index}: bloqueia com erro generico`, () => {
    assert.throws(() => sanitize(value), error => error.message === 'Entrada invalida para sanitizacao.');
  }));
  [[], [{ json: {} }], [{ json: { body: null } }], [{ json: { body: [] } }], [{ json: { body: 'teste@example.invalid' } }]]
    .forEach((items, index) => test(`envelope invalido ${index}`, () => {
      assert.throws(() => sanitizeItems(items), error => error.message === 'Entrada invalida para sanitizacao.');
    }));
  test('limite de tamanho aceito', () => assert.equal(sanitize('x'.repeat(20000)).length, 20000));
  test('item invalido interrompe lote inteiro', () => assert.throws(() => sanitizeItems([
    { json: { body: { review_text: 'entrega boa' } } }, { json: { body: { review_text: null } } },
  ])));

  // Limites conhecidos, deliberadamente NAO detectados: testes documentam risco residual.
  for (const text of ['Pessoa Sintética mora na Rua de Teste, 0.',
    'Meu email é teste arroba example ponto invalid.', 'CPF zero zero zero escrito por extenso.',
    'Telefone estrangeiro +1 (000) 000-0000.', 'Celular local 900000000 sem rotulo antes.']) {
    test(`limite conhecido ${text.slice(0, 22)}`, () => assert.equal(sanitize(text), text));
  }

  test('LLM recebe exclusivamente o texto sanitizado', () => {
    const sanitized = sanitize('O app trava, teste@example.invalid.');
    const result = body('LLM PROD', { $json: { review_text_sanitized: sanitized,
      body: { review_text: 'ORIGINAL_SINTETICO' }, customer_name: 'Pessoa Sintética' } });
    assert.equal(result.messages[1].content, 'O app trava, [EMAIL].');
    assert.equal(result.response_format.json_schema.strict, true);
    assert.ok(!JSON.stringify(result).includes('ORIGINAL_SINTETICO'));
    assert.ok(!JSON.stringify(result).includes('Pessoa Sintética'));
  });
  [undefined, null, '', '   ', 123, {}, []].forEach((value, index) => test(`LLM sem fallback ${index}`, () => {
    assert.throws(() => body('LLM PROD', { $json: { review_text_sanitized: value,
      body: { review_text: 'teste@example.invalid' } } }),
    error => error.message === 'Texto sanitizado ausente ou invalido.');
  }));
  test('LLM escapa aspas, barras e novas linhas', () => {
    const text = 'O app "trava".\nErro \\ login em teste@example.invalid';
    assert.equal(body('LLM PROD', { $json: { review_text_sanitized: sanitize(text) } }).messages[1].content,
      'O app "trava".\nErro \\ login em [EMAIL]');
  });
  test('parse normaliza enums e preserva dados apenas para Airtable', () => {
    const original = { review_id: 'SYNTH-1', customer_name: 'Pessoa Sintética', source: 'app-store',
      rating: 1, review_text: 'app trava teste@example.invalid' };
    const result = parse('{"sentiment":" Negativo ","theme":" APP_BUG "}', original)[0].json;
    assert.deepEqual({ ...result, processed_at: undefined }, { ...original, sentiment: 'negativo', theme: 'app_bug', processed_at: undefined });
    assert.ok(!Number.isNaN(Date.parse(result.processed_at)));
    const airtable = body('Airtable PROD', { $: () => ({ item: { json: result } }) });
    assert.equal(airtable.fields.review_text, original.review_text);
    assert.equal(airtable.fields.customer_name, original.customer_name);
  });
  const badResponses = [undefined, '', 'teste@example.invalid', 'null', '[]', '42', '{}',
    '{"sentiment":[],"theme":"produto"}', '{"sentiment":"negativo","theme":{}}',
    '{"sentiment":"teste@example.invalid","theme":"produto"}',
    '{"sentiment":"negativo","theme":"teste@example.invalid"}'];
  badResponses.forEach((raw, index) => test(`parse invalido ${index}: erro sem conteudo pessoal`, () => {
    assert.throws(() => parse(raw), error => /^(Resposta do LLM|Classificacao do LLM)/.test(error.message)
      && !error.message.includes('example.invalid') && (!raw || !error.message.includes(raw)));
  }));
  for (const rating of [1, 5, 'teste@example.invalid', {}, -1, 99, null]) {
    test(`Slack minimizado com nota ${typeof rating}:${String(rating)}`, () => {
      const result = body('Slack PROD', { $: () => ({ item: { json: { theme: 'app_bug', rating,
        customer_name: 'Pessoa Sintética', source: 'teste@example.invalid', review_id: 'teste@example.invalid',
        review_text: 'teste@example.invalid', review_text_sanitized: 'Pessoa Sintética' } } }) });
      assert.ok(result.text.includes('app_bug'));
      assert.ok(!result.text.includes('example.invalid'));
      assert.ok(!result.text.includes('Pessoa Sintética'));
      assert.ok(result.text.includes(Number.isInteger(rating) && rating >= 1 && rating <= 5 ? `Nota: ${rating}` : 'Nota: indisponivel'));
    });
  }

  // O Python usa os mesmos pares para verificar o mock existente, sem subprocessos.
  const semantics = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/pii_semantic_cases.json'), 'utf8'));
  for (const scenario of semantics) {
    test(`preserva conteudo para classificacao: ${scenario.name}`, () => {
      const sanitized = sanitize(scenario.original);
      assert.equal(sanitized, scenario.sanitized);
      assert.equal(body('LLM PROD', { $json: { review_text_sanitized: sanitized } }).messages[1].content,
        scenario.sanitized);
      const classification = parse(JSON.stringify(scenario.expected))[0].json;
      assert.equal(classification.sentiment, scenario.expected.sentiment);
      assert.equal(classification.theme, scenario.expected.theme);
    });
  }

  let failed = 0;
  for (const { label, fn } of tests) {
    try { fn(); report(`[OK] ${label}`); }
    catch (error) { failed++; report(`[FALHA] ${label}: ${error.message}`); }
  }
  const result = { passed: tests.length - failed, failed, total: tests.length };
  report(`RESULTADO: ${result.passed} passaram, ${failed} falharam`);
  return result;
}

module.exports = { runTests };
if (require.main === module) process.exitCode = runTests().failed ? 1 : 0;
