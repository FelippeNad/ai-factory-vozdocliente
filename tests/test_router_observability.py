import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_router_observability import build_router, build_observer, build_error, exports, OUTPUT
from router_observability_validation import structure_errors
from router_observability_report import aggregate, canonical, read_events, render


def event(run=1, latency=10, source='n8n', status='success'):
    metrics = dict(runs_total=1, runs_success=int(status == 'success'), runs_duplicate=int(status == 'duplicate'),
                   runs_failure=int(status == 'failure'), received=1, persisted=int(status == 'success'),
                   llm_calls_attempted=0 if status == 'duplicate' else 1, llm_responses=int(status == 'success'),
                   classification_valid=int(status == 'success'), prompt_tokens=None, completion_tokens=None, estimated_cost_usd=None)
    return dict(schema='vozdocliente.router.observability.v1', event_id=f'router-{run}:run:run:{status}',
                run_id=f'router-{run}', correlation='execution', at='2026-11-03T12:00:00.000Z', source=source, kind='run', stage='run',
                status=status, duration_ms=latency, error_code='NONE' if status != 'failure' else 'PRECHECK_HTTP_FAILED', metrics=metrics)


class RouterObservabilityTests(unittest.TestCase):
    def test_evidence_binds_to_exports_and_collected_simulation_events(self):
        evidence = ROOT / 'docs/evidencias'
        metadata = json.loads((evidence / 'router-observabilidade-simulacao.json').read_text(encoding='utf-8'))
        path = evidence / 'router-observabilidade-simulacao.ndjson'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), metadata['events_sha256'])
        self.assertIs(metadata['real_n8n_engine'], False)
        self.assertEqual(metadata['real_external_calls'], 0)
        for name, digest in metadata['workflow_sha256'].items():
            self.assertEqual(hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest(), digest)
        events, rejected = read_events(path)
        self.assertEqual(rejected, 0)
        self.assertTrue(all(e['source'] == 'offline_simulation' for e in events))
        self.assertEqual(sorted(e['status'] for e in events if e['kind'] == 'run'), ['duplicate', 'failure', 'success'])
        self.assertEqual((evidence / 'router-observabilidade-simulacao.html').read_text(encoding='utf-8'), render(aggregate(events), rejected))

    def test_generated_exports_and_structure(self):
        for (filename, workflow), role in zip(exports(), ('router', 'observer', 'error')):
            self.assertEqual(json.loads((OUTPUT / filename).read_text(encoding='utf-8')), workflow)
            self.assertEqual(structure_errors(workflow, role), [])

    def test_error_branch_cannot_release_llm_or_write(self):
        for target in ('LLM DEV', 'Airtable DEV'):
            workflow = build_router()
            workflow['connections']['Falha segura: Airtable Precheck DEV']['main'][0].append({'node': target, 'type': 'main', 'index': 0})
            self.assertTrue(structure_errors(workflow, 'router'))

    def test_mutations_of_security_barriers_rejected(self):
        for barrier in ('Sanitizar PII', 'Preparar deduplicacao DEV', 'Airtable Precheck DEV', 'Validar busca e restaurar texto', 'Ja existe? DEV'):
            workflow = build_router()
            workflow['connections'][barrier]['main'][0].append({'node': 'LLM DEV', 'type': 'main', 'index': 0})
            self.assertTrue(structure_errors(workflow, 'router'), barrier)

    def test_raw_fallback_and_silent_error_continuation_rejected(self):
        for name, key, value in [('LLM DEV', 'parameters', {'jsonBody': '={{ $json.body.review_text }}'}),
                                 ('Airtable Precheck DEV', 'onError', 'continueRegularOutput'),
                                 ('Sanitizar PII', 'onError', 'stopWorkflow')]:
            workflow = build_router()
            next(node for node in workflow['nodes'] if node['name'] == name)[key] = value
            self.assertTrue(structure_errors(workflow, 'router'))

    def test_alert_transport_is_reused(self):
        from build_retention_workflow import build
        retained = {n['name']: n for n in build()['nodes']}
        observed = {n['name']: n for n in build_observer()['nodes']}
        for name in ('Slack DEV falha', 'Alertar falha DEV?', 'Resultado observabilidade'):
            self.assertEqual(retained[name]['parameters'], observed[name]['parameters'])

    def test_percentiles_rates_unknown_cost_and_proxy_quality(self):
        events = [event(1, 10), event(2, 20), event(3, 100, status='failure'), event(4, 5, status='duplicate')]
        summary = aggregate(events)['n8n']
        self.assertEqual((summary['p50_ms'], summary['p95_ms'], summary['p99_ms']), (10, 100, 100))
        self.assertEqual(summary['error_rate'], .25)
        self.assertIsNone(summary['estimated_cost_usd_known_subtotal'])
        self.assertEqual(summary['schema_valid_rate'], 1)
        self.assertIsNone(summary['classification_accuracy'])

    def test_sources_and_recollected_events_not_mixed_or_double_counted(self):
        events = [event(1), event(1), event(1, 99, 'offline_simulation')]
        summary = aggregate(events)
        self.assertEqual(summary['n8n']['terminal_runs'], 1)
        self.assertEqual(summary['n8n']['p50_ms'], 10)
        self.assertEqual(summary['offline_simulation']['p50_ms'], 99)

    def test_partial_error_trigger_does_not_invent_calls_or_latency(self):
        value = event(status='failure', latency=None)
        for key in ('llm_calls_attempted', 'llm_responses', 'classification_valid', 'persisted'):
            value['metrics'][key] = None
        value['error_code'] = 'WORKFLOW_INTERRUPTED'
        summary = aggregate([value])['n8n']
        self.assertIsNone(summary['p95_ms'])
        self.assertIsNone(summary['llm_attempts_known'])
        self.assertEqual(summary['llm_attempts_unknown_runs'], 1)

    def test_dashboard_drops_personal_fields_and_external_text(self):
        with tempfile.NamedTemporaryFile(dir=ROOT / 'tests', suffix='.ndjson', delete=False) as temporary:
            path = Path(temporary.name)
        try:
            invalid = event(); invalid['review_text'] = 'pessoa@example.invalid SECRET_SYNTHETIC'
            path.write_text('provider error pessoa@example.invalid\n' + json.dumps(invalid) + '\n[prefix] ' + json.dumps(event()) + '\n', encoding='utf-8')
            events, rejected = read_events(path)
            self.assertEqual(len(events), 1); self.assertEqual(rejected, 2)
            output = render(aggregate(events), rejected)
            self.assertNotIn('example.invalid', output); self.assertNotIn('SECRET_SYNTHETIC', output)
            self.assertNotIn('<script', output); self.assertNotIn('https://', output)
        finally:
            path.unlink()

    def test_reject_arbitrary_codes_ids_numbers_and_mismatching_status(self):
        for key, value in [('run_id', 'pessoa@example.invalid'), ('error_code', 'SECRET_SYNTHETIC'),
                           ('duration_ms', -1), ('duration_ms', True), ('status', 'failure')]:
            invalid = event(); invalid[key] = value
            with self.assertRaises(ValueError): canonical(invalid)
        for bad in (float('nan'), float('inf'), -1, True):
            invalid = event(); invalid['metrics']['estimated_cost_usd'] = bad
            with self.assertRaises(ValueError): canonical(invalid)

    def test_incomplete_runs_visible_not_counted_as_success(self):
        value = event(); value.update(kind='stage', stage='received', event_id='router-1:stage:received:success')
        for key in ('runs_total', 'runs_success', 'runs_duplicate', 'runs_failure'): value['metrics'][key] = 0
        summary = aggregate([value])['n8n']
        self.assertEqual(summary['incomplete_runs'], 1); self.assertEqual(summary['terminal_runs'], 0)
        self.assertIsNone(summary['error_rate'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
