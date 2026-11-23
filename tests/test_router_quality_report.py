"""Qualidade manual: fixtures de telemetria sinteticas, sem APIs ou dados pessoais."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from router_observability_report import aggregate, read_labels, render, validate_labels
from test_router_observability import event

LABELS = ROOT / 'docs/evidencias/router-qualidade-dev-rotulos.json'
SCRIPT = ROOT / 'scripts/router_observability_report.py'


def collection():
    # Apenas fixture do teste; nunca gravada como evidencia de coleta real.
    return ([event(run) for run in (68, 70, 72, 74, 76, 78, 80)]
            + [event(82, status='duplicate')]
            + [event(run, status='failure') for run in (84, 86, 88)])


@contextmanager
def temporary_files(*names):
    # Arquivos diretamente em tests evitam ACLs de diretorios temporarios no Windows.
    paths = {}
    try:
        for name in names:
            with tempfile.NamedTemporaryFile(dir=ROOT / 'tests', suffix='-' + name, delete=False) as temporary:
                paths[name] = Path(temporary.name)
        yield paths
    finally:
        for path in paths.values():
            path.unlink(missing_ok=True)


class RouterQualityTests(unittest.TestCase):
    def setUp(self):
        self.labels = read_labels(LABELS)

    def test_five_supplied_labels_and_eleven_runs(self):
        data = aggregate(collection(), self.labels)['n8n']
        self.assertEqual(data['terminal_runs'], 11)
        self.assertEqual(data['human_labels'], 5)
        self.assertEqual((data['sentiment_correct'], data['theme_correct'], data['joint_correct']), (4, 5, 4))
        self.assertEqual((data['sentiment_accuracy'], data['theme_accuracy'], data['joint_accuracy']), (.8, 1, .8))
        self.assertEqual(data['classification_accuracy'], .8)
        self.assertEqual(data['schema_valid_rate'], 1)

    def test_joint_accuracy_requires_both_labels_on_same_run(self):
        self.labels['evaluations'] = self.labels['evaluations'][:2]
        self.labels['evaluations'][0]['actual_sentiment'] = 'neutro'
        self.labels['evaluations'][1]['actual_theme'] = 'app_bug'
        data = aggregate(collection(), self.labels)['n8n']
        self.assertEqual((data['sentiment_accuracy'], data['theme_accuracy'], data['joint_accuracy']), (.5, .5, 0))

    def test_schema_validity_is_independent(self):
        events = collection()
        for value in events:
            value['metrics']['classification_valid'] = 0
        data = aggregate(events, self.labels)['n8n']
        self.assertEqual(data['schema_valid_rate'], 0)
        self.assertEqual(data['joint_accuracy'], .8)

    def test_empty_labels_are_unmeasured(self):
        self.labels['evaluations'] = []
        data = aggregate(collection(), self.labels)['n8n']
        self.assertEqual(data['human_labels'], 0)
        for key in ('sentiment_accuracy', 'theme_accuracy', 'joint_accuracy', 'classification_accuracy'):
            self.assertIsNone(data[key])
        self.assertIn('não medido', render({'n8n': data}, 0))

    def test_without_file_preserves_previous_behavior(self):
        data = aggregate(collection())['n8n']
        self.assertEqual(data['human_labels'], 0)
        self.assertIsNone(data['classification_accuracy'])
        self.assertNotIn('quality_sample', data)

    def test_recollected_events_do_not_multiply_labels(self):
        events = collection()
        data = aggregate(events + copy.deepcopy(events), self.labels)['n8n']
        self.assertEqual(data['terminal_runs'], 11)
        self.assertEqual(data['human_labels'], 5)
        self.assertEqual(data['joint_correct'], 4)

    def test_duplicate_labels_identical_or_conflicting_rejected(self):
        for sentiment in ('positivo', 'neutro'):
            labels = copy.deepcopy(self.labels)
            duplicate = dict(labels['evaluations'][0], actual_sentiment=sentiment)
            labels['evaluations'].append(duplicate)
            with self.subTest(sentiment=sentiment), self.assertRaisesRegex(ValueError, 'duplicado'):
                aggregate(collection(), labels)

    def test_only_existing_successful_terminal_runs_allowed(self):
        for run in ('router-999', 'router-82', 'router-84', 'router-error-72'):
            labels = copy.deepcopy(self.labels)
            labels['evaluations'][0]['run_id'] = run
            with self.subTest(run=run), self.assertRaises(ValueError):
                aggregate(collection(), labels)
        stage = event(72)
        stage.update(kind='stage', stage='llm', event_id='router-72:stage:llm:success')
        events = [e for e in collection() if e['run_id'] != 'router-72'] + [stage]
        with self.assertRaises(ValueError):
            aggregate(events, self.labels)

    def test_conflicting_terminals_preserve_failure_or_duplicate_precedence(self):
        for status in ('failure', 'duplicate'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                aggregate(collection() + [event(72, status=status)], self.labels)

    def test_offline_runs_cannot_satisfy_real_labels(self):
        simulated = [dict(e, source='offline_simulation') for e in collection()]
        for real in ([], [event(72, status='failure')]):
            with self.subTest(real=bool(real)), self.assertRaises(ValueError):
                aggregate(real + simulated, self.labels)
        mixed = aggregate(collection() + simulated, self.labels)
        self.assertEqual(mixed['n8n']['human_labels'], 5)
        self.assertEqual(mixed['offline_simulation']['human_labels'], 0)
        self.assertIsNone(mixed['offline_simulation']['classification_accuracy'])
        self.assertNotIn('quality_sample', mixed['offline_simulation'])

    def test_strict_envelope_and_enum_allowlists(self):
        for key, value in (('source', 'offline_simulation'), ('sample', 'representative'),
                           ('schema', 'unknown'), ('evaluations', {}), ('review_text', 'REJECTED_MARKER')):
            labels = dict(self.labels, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_labels(labels)
        for field in self.labels:
            labels = copy.deepcopy(self.labels)
            del labels[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_labels(labels)
        for key in ('expected_sentiment', 'actual_sentiment', 'expected_theme', 'actual_theme', 'run_id'):
            for value in ('INVALID_MARKER', '', None, True, [], {}):
                labels = copy.deepcopy(self.labels)
                labels['evaluations'][0][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_labels(labels)
        for row in (None, [], {}, dict(self.labels['evaluations'][0], customer_name='REJECTED_MARKER')):
            labels = dict(self.labels, evaluations=[row])
            with self.subTest(row=row), self.assertRaises(ValueError):
                validate_labels(labels)

    def test_reader_rejects_malformed_json_repeated_keys_and_large_files(self):
        with temporary_files('labels.json') as paths:
            path = paths['labels.json']
            for text in ('REJECTED_MARKER', '{"source":"n8n","source":"n8n"}',
                         LABELS.read_text(encoding='utf-8') + ' trailing', '[]'):
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError) as error:
                    read_labels(path)
                self.assertNotIn('REJECTED_MARKER', str(error.exception))
            with path.open('wb') as output:
                output.truncate(10 * 1024 * 1024 + 1)
            with self.assertRaises(ValueError):
                read_labels(path)
            path.write_bytes(b'\xff')
            with self.assertRaises(ValueError):
                read_labels(path)
            path.unlink()
            with self.assertRaises(ValueError):
                read_labels(path)

    def test_html_has_percentages_counts_limits_and_no_individual_labels(self):
        output = render(aggregate(collection(), self.labels), 0)
        for text in ('Acurácia de sentimento', 'Acurácia de tema', 'Acurácia conjunta',
                     '80% (4/5)', '100% (5/5)', 'Total de avaliações rotuladas</th><td>5',
                     'Amostra sintética e limitada', 'métrica independente', 'transcritos manualmente'):
            self.assertIn(text, output)
        for text in ('router-72', 'expected_sentiment', '<script', 'https://'):
            self.assertNotIn(text, output)

    def test_cli_with_and_without_labels(self):
        with temporary_files('events.ndjson', 'dashboard.html', 'sanitized.ndjson') as paths:
            events, output, exported = (paths[name] for name in ('events.ndjson', 'dashboard.html', 'sanitized.ndjson'))
            events.write_text(''.join(json.dumps(e) + '\n' for e in collection()), encoding='utf-8')
            command = [sys.executable, str(SCRIPT), '--input', str(events), '--output', str(output),
                       '--events-output', str(exported)]
            for options, count in (([], 0), (['--labels', str(LABELS)], 5)):
                result = subprocess.run(command + options, capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)['summary']['n8n']
                self.assertEqual(data['human_labels'], count)
                self.assertIn('<!doctype html>', output.read_text(encoding='utf-8'))
                self.assertEqual(exported.read_text(encoding='utf-8'), events.read_text(encoding='utf-8'))

    def test_invalid_labels_do_not_write_outputs_or_echo_content(self):
        with temporary_files('events.ndjson', 'labels.json', 'dashboard.html', 'sanitized.ndjson') as paths:
            events, labels, output, exported = (paths[name] for name in ('events.ndjson', 'labels.json', 'dashboard.html', 'sanitized.ndjson'))
            events.write_text(json.dumps(event(72)), encoding='utf-8')
            output.write_text('unchanged', encoding='utf-8')
            exported.write_text('unchanged', encoding='utf-8')
            invalid = dict(self.labels, review_text='REJECTED_MARKER')
            for value in (invalid, self.labels):  # Extra field, then missing successful runs.
                labels.write_text(json.dumps(value), encoding='utf-8')
                result = subprocess.run([sys.executable, str(SCRIPT), '--input', str(events),
                                         '--output', str(output), '--events-output', str(exported),
                                         '--labels', str(labels)], capture_output=True, encoding='utf-8')
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('REJECTED_MARKER', result.stdout + result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertEqual(output.read_text(encoding='utf-8'), 'unchanged')
                self.assertEqual(exported.read_text(encoding='utf-8'), 'unchanged')


if __name__ == '__main__':
    unittest.main(verbosity=2)
