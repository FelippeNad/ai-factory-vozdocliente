"""Fixtures sinteticas e transporte fake: nenhum resultado real ou acesso a fornecedores."""
import copy
from contextlib import contextmanager
import json
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_router_benchmark import build, exports, CASES, CURRENT
from router_observability_validation import reachable
from router_real_benchmark import (LocalN8n, digest, healthy, payload, prepare, read_records, render, run,
                                   summarize, validate_packet, validate_plan, verify_live, normalized_benchmark_node, PACKET_SCHEMA)
from test_router_observability import event

TARGETS = {'dev_base_id': 'app00000000000000', 'dev_table_id': 'tbl00000000000001', 'dev_slack_channel_id': 'C00000000'}


@contextmanager
def directory():
    # mkdir padrao evita ACL 0700 de TemporaryDirectory no Python/Windows.
    with tempfile.NamedTemporaryFile(dir=ROOT / 'tests', delete=False) as temp:
        path = Path(temp.name)
    path.unlink()
    path.mkdir()
    try:
        yield path
    finally:
        for item in path.iterdir():
            if item.is_dir():
                for child in item.iterdir():
                    child.unlink()
                item.rmdir()
            else:
                item.unlink()
        path.rmdir()


def packet(plan, variant, sequence, run_id):
    case = CASES[(sequence - 1) % 5]
    call = int(variant == 'before' or sequence <= 5)
    report = event(run_id, latency=sequence * 100, status='success' if sequence <= 5 else 'duplicate')
    report['metrics'].update(llm_calls_attempted=call, llm_responses=call, classification_valid=call,
                             prompt_tokens=100 * call, completion_tokens=20 * call, estimated_cost_usd=.00036 * call)
    return {'schema': PACKET_SCHEMA, 'benchmark_id': plan['benchmark_id'], 'variant': variant,
            'sequence': sequence, 'case_id': case['case_id'], 'report': report, 'delivery_status': 'not_needed',
            'airtable_queries_attempted': {'precheck': int(variant == 'after'), 'final': call},
            'persisted_classification': {key: case[key] for key in ('sentiment', 'theme')} if sequence <= 5 else None,
            'configuration': {'environment': 'DEV', 'dev_base_id': TARGETS['dev_base_id'], 'dev_table_id': TARGETS['dev_table_id'],
                              'slack_channel_id': TARGETS['dev_slack_channel_id'], 'observer_id': 'observer_synthetic',
                              'input_price': 2, 'output_price': 8}}


def records(plan):
    result = []
    for variant in plan['order']:
        for sequence in range(1, 16):
            value = packet(plan, variant, sequence, len(result) + 1)
            value['configuration_sha256'] = digest(value.pop('configuration'))
            value['completion_status'] = 'terminal_confirmed'
            result.append(value)
    return result


def live(variant):
    value = build(variant)
    value['active'] = True
    for node in value['nodes']:
        if node['type'] == 'n8n-nodes-base.httpRequest':
            kind = 'openAiApi' if node['name'] == 'LLM DEV' else 'httpHeaderAuth'
            node['credentials'] = {kind: {'id': 'synthetic-' + kind, 'name': 'synthetic'}}
    return value


def imported_live(variant):
    """Omissoes observadas no round-trip n8n 2.28.7, sem alterar o comportamento."""
    workflow = live(variant)
    defaults = {
        ('n8n-nodes-base.code', 2): {'mode': 'runOnceForAllItems', 'language': 'javaScript'},
        ('n8n-nodes-base.httpRequest', 4.4): {'method': 'GET'},
        ('n8n-nodes-base.executeWorkflow', 1): {'source': 'database', 'mode': 'once'},
        ('n8n-nodes-base.stopAndError', 1): {'errorType': 'errorMessage'},
    }
    for node in workflow['nodes']:
        for key, value in defaults.get((node['type'], node['typeVersion']), {}).items():
            if node['parameters'].get(key) == value:
                node['parameters'].pop(key, None)
        if node['name'] in ('Validar benchmark DEV', 'Coletar benchmark DEV',
                            'Responder benchmark DEV', 'Responder falha benchmark DEV'):
            node.pop('onError')
    return workflow


class FakeN8n:
    def __init__(self, plan):
        self.plan, self.posts, self.trace, self.pending = plan, [], [], False
        self.mutate = lambda value: value

    def request(self, path, body=None):
        if path.startswith('/api/v1/workflows/'):
            return live(path.rsplit('/', 1)[1])
        assert not self.pending, 'Envio ocorreu antes da conclusao anterior'
        self.pending = True
        self.posts.append(copy.deepcopy(body))
        self.trace.append('post')
        value = self.mutate(packet(self.plan, path.split('-')[-2], body['benchmark_sequence'], len(self.posts)))
        self.pending = False
        self.trace.append('terminal')
        return value


class RealBenchmarkTests(unittest.TestCase):
    def setUp(self):
        # Plano real de preparacao, mas todas as medicoes destes testes sao fixtures.
        self.plan = {'schema': 'vozdocliente.router.real-benchmark.plan.v1', 'scope': 'PREPARATION_ONLY_NO_MEASUREMENTS',
                     'benchmark_id': 'a' * 32, 'prepared_at': '2026-11-22T12:00:00Z', 'order': ['before', 'after'],
                     'targets': TARGETS, 'workflows': {v: digest(build(v)) for v in ('before', 'after')},
                     'cases_sha256': digest(CASES), 'current_router_sha256': __import__('hashlib').sha256(CURRENT.read_bytes()).hexdigest()}

    def test_generated_exports_match_and_keep_current_functional_parameters(self):
        original = {n['name']: n for n in json.loads(CURRENT.read_text(encoding='utf-8'))['nodes']}
        for path, workflow in exports():
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), workflow)
            self.assertFalse(workflow['active'])
            self.assertFalse(workflow['pinData'])
            for node in workflow['nodes']:
                self.assertNotIn('credentials', node)
                if node['name'] in original and node['name'] not in ('Webhook Review', 'LLM iniciado DEV'):
                    self.assertEqual(node['parameters'], original[node['name']]['parameters'], node['name'])
                    self.assertEqual(node.get('onError'), original[node['name']].get('onError'))
            for barrier in ('Sanitizar PII', 'Preparar deduplicacao DEV', 'Validar benchmark DEV'):
                self.assertFalse(reachable(workflow, 'Webhook Review', 'LLM DEV', blocked=barrier))
            for barrier in ('Airtable Buscar review_id', 'Validar busca final DEV', 'Confirmar novo? DEV'):
                self.assertFalse(reachable(workflow, 'Webhook Review', 'Airtable DEV', blocked=barrier))

    def test_order_matches_old_v4_and_only_optimized_has_precheck(self):
        old = json.loads((ROOT / 'n8n-mirror/workflows/vozdocliente-router-v4.json').read_text(encoding='utf-8'))
        self.assertEqual(old['connections']['Parse + Merge']['main'][0][0]['node'], 'Airtable Buscar review_id')
        before, after = build('before'), build('after')
        self.assertNotIn('Airtable Precheck DEV', {n['name'] for n in before['nodes']})
        self.assertFalse(reachable(before, 'Webhook Review', 'Airtable Buscar review_id', blocked='LLM DEV'))
        self.assertFalse(reachable(after, 'Webhook Review', 'LLM DEV', blocked='Airtable Precheck DEV'))
        self.assertTrue(reachable(after, 'Falha segura: Airtable Precheck DEV', 'Interromper com seguranca'))

    def test_load_same_content_and_order_separate_ids(self):
        ids = {}
        for variant in ('before', 'after'):
            values = [payload(self.plan, variant, i) for i in range(1, 16)]
            ids[variant] = {v['review_id'] for v in values}
            self.assertEqual(len(ids[variant]), 5)
            self.assertEqual([v['review_text'] for v in values], [c['text'] for c in CASES] * 3)
            self.assertTrue(all(sum(v['review_id'] == key for v in values) == 3 for key in ids[variant]))
        self.assertFalse(ids['before'] & ids['after'])

    def test_prepare_is_offline_unique_and_does_not_overwrite(self):
        with directory() as folder, patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network')):
            p1 = prepare(folder / 'one', TARGETS)
            p2 = prepare(folder / 'two', TARGETS, first='after')
            self.assertNotEqual(p1['benchmark_id'], p2['benchmark_id'])
            self.assertEqual(p2['order'], ['after', 'before'])
            self.assertEqual(validate_plan(p1), p1)
            self.assertFalse((folder / 'one/records.ndjson').exists())
            with self.assertRaises(FileExistsError):
                prepare(folder / 'one', TARGETS)

    def test_runner_sequential_and_single_use(self):
        with directory() as folder:
            plan = prepare(folder / 'batch', TARGETS)
            fake = FakeN8n(plan)
            with patch('sys.stdout', new=io.StringIO()):
                path = run(folder / 'batch/plan.json', {'before': 'before', 'after': 'after'}, fake)
            self.assertEqual(len(fake.posts), 30)
            self.assertEqual(fake.trace, ['post', 'terminal'] * 30)
            rows = read_records(path)
            self.assertEqual(len(rows), 30)
            self.assertTrue(all(healthy(r) for r in rows))
            self.assertTrue(all('configuration' not in r for r in rows))
            journal = read_records(folder / 'batch/dispatch.ndjson')
            result = summarize(plan, rows, journal)
            self.assertEqual([result['variants'][v]['terminal_reconciliation_rate'] for v in ('before','after')], [1, 1])
            with self.assertRaises(FileExistsError):
                run(folder / 'batch/plan.json', {'before': 'before', 'after': 'after'}, fake)
            self.assertEqual(len(fake.posts), 30)

    def test_comparison_and_percentiles_from_fixture_only(self):
        data = summarize(self.plan, records(self.plan))
        before, after = (data['variants'][v] for v in ('before', 'after'))
        self.assertEqual((before['llm_calls_attempted'], after['llm_calls_attempted']), (15, 5))
        self.assertEqual((before['airtable_queries_attempted'], after['airtable_queries_attempted']), (15, 20))
        self.assertEqual((before['prompt_tokens'], after['prompt_tokens']), (1500, 500))
        self.assertEqual((before['completion_tokens'], after['completion_tokens']), (300, 100))
        self.assertEqual((before['latency_mean_ms'], before['p50_ms'], before['p95_ms'], before['p99_ms']), (800, 800, 1500, 1500))
        self.assertAlmostEqual(data['comparison']['llm_calls_reduction_percent'], 200/3)
        self.assertAlmostEqual(data['comparison']['estimated_cost_reduction_percent'], 200/3)
        self.assertEqual(data['comparison']['additional_airtable_queries'], 5)
        for value in (before, after):
            self.assertEqual(value['records_persisted_confirmed'], 5)
            self.assertEqual(value['duplicates'], 10)
            self.assertEqual(value['schema_valid_rate'], 1)
            self.assertEqual(value['persisted_joint_accuracy'], 1)

    def test_unknown_cost_tokens_and_duration_never_become_zero(self):
        rows = records(self.plan)
        m = rows[0]['report']['metrics']
        m.update(estimated_cost_usd=None, prompt_tokens=None, completion_tokens=None)
        rows[0]['report']['duration_ms'] = None
        data = summarize(self.plan, rows)
        before = data['variants']['before']
        self.assertIsNone(before['estimated_cost_usd_total'])
        self.assertIsNone(data['comparison']['estimated_cost_reduction_percent'])
        self.assertIsNone(before['prompt_tokens'])
        self.assertEqual(before['prompt_tokens_known_subtotal'], 1400)
        self.assertEqual(before['cost_known_classifications'], 14)
        self.assertEqual(before['cost_unknown_llm_runs'], 1)
        self.assertEqual(before['latency_unknown_runs'], 1)
        self.assertAlmostEqual(before['estimated_cost_usd_mean_known_classification'], .00036)

    def test_missing_persisted_snapshot_is_unknown_quality(self):
        rows = records(self.plan)
        rows[0]['persisted_classification'] = None
        value = summarize(self.plan, rows)['variants']['before']
        self.assertEqual(value['persisted_classifications_unknown'], 1)
        self.assertEqual(value['persisted_classifications_evaluated'], 4)
        self.assertEqual(value['records_persisted_confirmed'], 5)

    def test_quality_can_differ_while_structural_validity_stays_perfect(self):
        rows = records(self.plan)
        rows[15]['persisted_classification']['sentiment'] = 'neutro'
        data = summarize(self.plan, rows)
        self.assertEqual(data['variants']['after']['persisted_joint_accuracy'], .8)
        self.assertEqual(data['variants']['after']['schema_valid_rate'], 1)
        self.assertEqual(data['comparison']['persisted_classifications_differing_case_ids'], [1])

    def test_partial_pair_no_reduction_claim(self):
        data = summarize(self.plan, records(self.plan)[:17])
        self.assertFalse(data['comparison']['comparable_complete_pair'])
        self.assertIsNone(data['comparison']['llm_calls_reduction_percent'])
        self.assertIsNone(data['comparison']['estimated_cost_reduction_percent'])

    def test_dispatch_attempt_without_terminal_is_not_complete(self):
        rows = records(self.plan)
        journal = [{'benchmark_id':self.plan['benchmark_id'], 'variant':r['variant'],
                    'sequence':r['sequence'], 'case_id':r['case_id']} for r in rows]
        data = summarize(self.plan, rows[:2], journal[:3])
        self.assertAlmostEqual(data['variants']['before']['terminal_reconciliation_rate'], 2/3)
        self.assertEqual(data['variants']['before']['requests_attempted'], 3)
        with self.assertRaises(ValueError):
            summarize(self.plan, rows[:3], journal[:2])
        journal[1] = journal[0]
        with self.assertRaises(ValueError):
            summarize(self.plan, rows, journal)

    def test_failure_stops_after_one_post_and_retains_partial_evidence(self):
        with directory() as folder:
            plan = prepare(folder / 'batch', TARGETS)
            fake = FakeN8n(plan)
            def fail(value):
                value['report'] = event(1, status='failure')
                value['persisted_classification'] = None
                return value
            fake.mutate = fail
            with self.assertRaises(ValueError):
                run(folder/'batch/plan.json', {'before':'before','after':'after'}, fake)
            self.assertEqual(len(fake.posts), 1)
            self.assertEqual(len(read_records(folder/'batch/dispatch.ndjson')), 1)
            self.assertEqual(len(read_records(folder/'batch/records.ndjson')), 1)

    def test_reject_mixed_sources_ids_sequences_extra_fields_and_duplicates(self):
        base = records(self.plan)
        for mutate in (lambda r: r[0].update(benchmark_id='b'*32), lambda r: r[0].update(sequence=2),
                       lambda r: r[0].update(extra='REJECTED_MARKER'),
                       lambda r: r[0]['report'].update(source='offline_simulation'),
                       lambda r: r[1].update(report=r[0]['report']),
                       lambda r: r[0].update(persisted_classification={'sentiment':'REJECTED_MARKER','theme':'entrega'})):
            rows = copy.deepcopy(base); mutate(rows)
            with self.assertRaises(ValueError):
                summarize(self.plan, rows)

    def test_changed_runtime_configuration_blocks_pair_comparison(self):
        rows = records(self.plan); rows[15]['configuration_sha256'] = 'b'*64
        data = summarize(self.plan, rows)
        self.assertFalse(data['configuration_consistent'])
        self.assertIsNone(data['comparison']['llm_calls_reduction_percent'])

    def test_live_definition_preflight_rejects_mutations(self):
        self.assertTrue(verify_live(live('after'), 'after'))
        for mutate in (lambda w: w.update(active=False), lambda w: w['nodes'][0]['parameters'].update(path='review-v4-observavel-dev'),
                       lambda w: w['settings'].update(saveDataSuccessExecution='all'),
                       lambda w: w.update(activeVersionId='published', versionId='draft'),
                       lambda w: w['connections']['Webhook Review']['main'][0].append({'node':'LLM DEV','type':'main','index':0})):
            value = live('after'); mutate(value)
            with self.assertRaises(ValueError):
                verify_live(value, 'after')

    def test_n8n_round_trip_defaults_accepted_without_mutating_workflows(self):
        for variant in ('before', 'after'):
            value = imported_live(variant)
            untouched = copy.deepcopy(value)
            expected = build(variant)
            untouched_expected = copy.deepcopy(expected)
            with self.subTest(variant=variant):
                with patch('router_real_benchmark.build', return_value=expected):
                    credentials = verify_live(value, variant)
                self.assertEqual(credentials, verify_live(live(variant), variant))
                self.assertEqual(value, untouched)
                self.assertEqual(expected, untouched_expected)

    def test_only_proven_type_versions_receive_parameter_defaults(self):
        examples = [
            ('n8n-nodes-base.code', 2, {'mode':'runOnceForAllItems', 'language':'javaScript'}),
            ('n8n-nodes-base.httpRequest', 4.4, {'method':'GET'}),
            ('n8n-nodes-base.executeWorkflow', 1, {'source':'database', 'mode':'once'}),
            ('n8n-nodes-base.stopAndError', 1, {'errorType':'errorMessage'}),
        ]
        for kind, version, expected in examples:
            value = {'name':'fixture', 'type':kind, 'typeVersion':version, 'parameters':{}}
            with self.subTest(kind=kind, version=version):
                self.assertEqual(normalized_benchmark_node(value)['parameters'], expected)
                self.assertEqual(value['parameters'], {})
                value['typeVersion'] = 99
                self.assertEqual(normalized_benchmark_node(value)['parameters'], {})
        value = {'name':'fixture', 'type':'n8n-nodes-base.httpRequest', 'typeVersion':4.1, 'parameters':{}}
        self.assertEqual(normalized_benchmark_node(value)['parameters'], {})

    def test_stop_policy_omission_accepts_only_missing_or_false_legacy_flag(self):
        names = ('Validar benchmark DEV', 'Coletar benchmark DEV', 'Responder benchmark DEV', 'Responder falha benchmark DEV')
        for variant in ('before', 'after'):
            for name in names:
                for explicit_false in (False, True):
                    value = imported_live(variant)
                    node = next(n for n in value['nodes'] if n['name'] == name)
                    if explicit_false:
                        node['continueOnFail'] = False
                    with self.subTest(variant=variant, node=name, explicit_false=explicit_false):
                        self.assertTrue(verify_live(value, variant))

    def test_stop_policy_never_accepts_continuation_null_or_invalid_legacy(self):
        names = ('Validar benchmark DEV', 'Coletar benchmark DEV', 'Responder benchmark DEV', 'Responder falha benchmark DEV')
        for name in names:
            for policy in ('continueRegularOutput', 'continueErrorOutput', None, 'unknown'):
                value = imported_live('before')
                next(n for n in value['nodes'] if n['name'] == name)['onError'] = policy
                with self.subTest(node=name, policy=policy), self.assertRaises(ValueError):
                    verify_live(value, 'before')
            for legacy in (True, None, 0, 'false'):
                for explicit_stop in (False, True):
                    value = imported_live('before')
                    node = next(n for n in value['nodes'] if n['name'] == name)
                    node['continueOnFail'] = legacy
                    if explicit_stop:
                        node['onError'] = 'stopWorkflow'
                    with self.subTest(node=name, legacy=legacy, explicit_stop=explicit_stop), self.assertRaises(ValueError):
                        verify_live(value, 'before')

    def test_error_policy_equivalence_is_not_extended_to_other_nodes(self):
        value = imported_live('before')
        next(n for n in value['nodes'] if n['name'] == 'Interromper com seguranca')['onError'] = 'stopWorkflow'
        with self.assertRaises(ValueError):
            verify_live(value, 'before')
        for name in ('Sanitizar PII', 'Preparar deduplicacao DEV', 'LLM DEV', 'Parse + Merge',
                     'Airtable Buscar review_id', 'Validar busca final DEV', 'Airtable DEV', 'Slack DEV'):
            value = imported_live('before')
            next(n for n in value['nodes'] if n['name'] == name).pop('onError')
            with self.subTest(node=name), self.assertRaises(ValueError):
                verify_live(value, 'before')

    def test_normalization_preserves_explicit_behavior_and_rejects_null_defaults(self):
        changes = [('Sanitizar PII','mode','runOnceForEachItem'), ('Sanitizar PII','language','pythonNative'),
                   ('Airtable Buscar review_id','method','POST'), ('Enviar observabilidade DEV','source','url'),
                   ('Enviar observabilidade DEV','mode','each'), ('Interromper com seguranca','errorType','errorObject')]
        for name, key, changed in changes:
            for actual in (changed, None):
                value = imported_live('before')
                next(n for n in value['nodes'] if n['name'] == name)['parameters'][key] = actual
                with self.subTest(node=name, key=key, value=actual), self.assertRaises(ValueError):
                    verify_live(value, 'before')

    def test_javascript_expressions_timeouts_retries_and_credentials_stay_strict(self):
        changes = [('Sanitizar PII',lambda n: n['parameters'].__setitem__('jsCode',n['parameters']['jsCode']+'\n')),
                   ('LLM DEV',lambda n: n['parameters'].__setitem__('jsonBody',n['parameters']['jsonBody']+' ')),
                   ('Airtable Buscar review_id',lambda n: n['parameters'].__setitem__('url','=changed')),
                   ('LLM DEV',lambda n: n['parameters']['options'].__setitem__('timeout',15001)),
                   ('LLM DEV',lambda n: n['parameters']['options']['redirect']['redirect'].__setitem__('followRedirects',True)),
                   ('LLM DEV',lambda n: n.__setitem__('retryOnFail',True)),
                   ('LLM DEV',lambda n: n.pop('credentials')),
                   ('LLM DEV',lambda n: n.__setitem__('disabled',True)),
                   ('Sanitizar PII',lambda n: n.__setitem__('typeVersion',1))]
        for index, (name, mutate) in enumerate(changes):
            value = imported_live('before'); mutate(next(n for n in value['nodes'] if n['name'] == name))
            with self.subTest(node=name, mutation=index), self.assertRaises(ValueError):
                verify_live(value, 'before')

    def test_every_retention_override_remains_required_and_exact(self):
        required = {'saveDataErrorExecution':'none', 'saveDataSuccessExecution':'none',
                    'saveManualExecutions':False, 'saveExecutionProgress':False}
        for variant in ('before', 'after'):
            for key in required:
                for changed in ('absent', 'DEFAULT', None, True):
                    value = imported_live(variant)
                    if changed == 'absent':
                        value['settings'].pop(key)
                    else:
                        value['settings'][key] = changed
                    with self.subTest(variant=variant, key=key, value=changed), self.assertRaisesRegex(ValueError,'Persistencia'):
                        verify_live(value, variant)
            value = imported_live(variant); value.pop('settings')
            with self.assertRaisesRegex(ValueError,'Persistencia'):
                verify_live(value, variant)

    def test_local_transport_rejects_remote_urls_redirects_and_proxies(self):
        for url in ('https://example.invalid','http://192.168.0.1:5678','http://localhost:5680',
                    'http://localhost:5678/extra','http://user:pass@localhost:5678','http://localhost:5678?x=y'):
            with self.assertRaises(ValueError):
                LocalN8n(url, 'synthetic-token')
        client = LocalN8n('http://127.0.0.1:5678', 'synthetic-token')
        from router_real_benchmark import NoRedirect
        self.assertTrue(any(isinstance(h, NoRedirect) for h in client.opener.handlers))
        self.assertFalse(client.opener.proxies if hasattr(client.opener, 'proxies') else False)

    def test_abort_on_early_ack_without_terminal_and_without_next_post(self):
        with directory() as folder:
            plan = prepare(folder / 'batch', TARGETS)
            fake = FakeN8n(plan)
            fake.mutate = lambda value: {'message':'Workflow was started'}
            with self.assertRaises(ValueError):
                run(folder / 'batch/plan.json', {'before':'before','after':'after'}, fake)
            self.assertEqual(len(fake.posts), 1)
            data = summarize(plan, read_records(folder / 'batch/records.ndjson'))
            self.assertFalse(data['comparison']['comparable_complete_pair'])

    def test_cli_run_requires_explicit_execution_before_any_network(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts/router_real_benchmark.py'), 'run', '--plan','absent.json',
                                 '--before-workflow-id','a','--after-workflow-id','b'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'--execute-real-dev', result.stderr)

    def test_report_does_not_include_payload_or_credentials(self):
        output = render(summarize(self.plan, records(self.plan)))
        for value in ('review_text','customer_name','synthetic-token','app000','tbl000','<script','https://'):
            self.assertNotIn(value, output)
        self.assertIn('nao representa producao', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
