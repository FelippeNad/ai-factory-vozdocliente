"""Evidencias documentais publicas: verificacao offline, sem logs privados."""
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_etapa2_evidence import OUTPUT, NAMES, check_public, json_text, sha
from validate_doc_links import links, markdown_anchors, validate
from test_router_real_benchmark import directory


class PublicEvidenceTests(unittest.TestCase):
    def copy_evidence(self, destination):
        for name in (*NAMES, 'etapa-2-evidencias-manifesto.json'):
            shutil.copyfile(OUTPUT / name, destination / name)

    def mutate(self, destination, name, change, rehash=True):
        path = destination / name
        value = json.loads(path.read_text(encoding='utf-8'))
        change(value)
        path.write_text(json_text(value), encoding='utf-8', newline='\n')
        if rehash:
            manifest_path = destination / 'etapa-2-evidencias-manifesto.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['artifacts_sha256'][name] = sha(path.read_bytes())
            manifest_path.write_text(json_text(manifest), encoding='utf-8', newline='\n')

    def test_public_evidence_reproduces_without_private_inputs_or_network(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Rede proibida')):
            result = check_public(OUTPUT)
        self.assertTrue(result['comparison']['comparable_complete_pair'])
        self.assertAlmostEqual(result['comparison']['llm_calls_reduction_percent'], 200 / 3)
        self.assertAlmostEqual(result['comparison']['estimated_cost_reduction_percent'], 200 / 3)
        before, after = (result['variants'][v] for v in ('before', 'after'))
        self.assertAlmostEqual(100 * (1 - after['latency_mean_ms'] / before['latency_mean_ms']), 35.335020721497514)
        self.assertEqual(before['airtable_queries_attempted'], 15)
        self.assertEqual(after['airtable_queries_attempted'], 20)

    def test_cohorts_and_semantic_unknowns_are_separate(self):
        result = check_public(OUTPUT)
        for variant in result['variants'].values():
            self.assertEqual(variant['persisted_classifications_evaluated'], 0)
            self.assertIsNone(variant['persisted_joint_accuracy'])
        dashboard = json.loads((OUTPUT / 'router-observabilidade-dev-real.json').read_text(encoding='utf-8'))
        self.assertEqual(set(dashboard['summary']), {'n8n'})
        cohort = dashboard['summary']['n8n']
        self.assertEqual((cohort['terminal_runs'], cohort['success'], cohort['duplicate'], cohort['failure']), (11, 7, 1, 3))
        self.assertEqual((cohort['human_labels'], cohort['joint_accuracy']), (5, .8))
        self.assertEqual(cohort['theme_accuracy'], 1)
        self.assertEqual(cohort['sentiment_accuracy'], .8)

    def test_public_samples_contain_only_allowed_numeric_measurements(self):
        data = json.loads((OUTPUT / 'benchmark-dev-amostras.json').read_text(encoding='utf-8'))
        allowed = {'variant', 'sequence', 'status', 'duration_ms', 'metrics', 'airtable_queries_attempted'}
        for row in data['samples']:
            self.assertEqual(set(row), allowed)
            for value in [row['sequence'], row['duration_ms'], *row['metrics'].values(), *row['airtable_queries_attempted'].values()]:
                self.assertIn(type(value), (int, float))
        # Nao transportar campos do plano/pacote ou identificadores correlacionaveis.
        serialized = (OUTPUT / 'benchmark-dev-amostras.json').read_text(encoding='utf-8')
        for field in ('review_text', 'customer_name', 'run_id', 'configuration', 'dev_base_id', 'credentials', 'webhook', 'case_id'):
            self.assertNotIn(field, serialized)

    def test_html_explicitly_limits_interpretation(self):
        benchmark = (OUTPUT / 'benchmark-dev-real.html').read_text(encoding='utf-8')
        self.assertIn('não avaliada neste benchmark', benchmark)
        self.assertIn('não comprova equivalência semântica', benchmark)
        dashboard = (OUTPUT / 'router-observabilidade-dev-real.html').read_text(encoding='utf-8')
        self.assertIn('27,27% descreve o experimento, não operação normal', dashboard)
        self.assertIn('custo desconhecido, nunca zero', dashboard)

    def test_changed_artifact_fails_hash_check(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-real.json', lambda r: r.update(scope='changed'), rehash=False)
            with self.assertRaisesRegex(ValueError, 'Hash'):
                check_public(folder)

    def test_changed_measurement_fails_recalculation_even_with_updated_hash(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-amostras.json', lambda r: r['samples'][0]['metrics'].update(prompt_tokens=999))
            with self.assertRaisesRegex(ValueError, 'Agregados'):
                check_public(folder)

    def test_duplicate_sample_fails_even_with_updated_hash(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-amostras.json', lambda r: r['samples'].__setitem__(1, r['samples'][0]))
            with self.assertRaisesRegex(ValueError, 'Sequencia'):
                check_public(folder)

    def test_free_text_field_fails_allowlist_even_with_updated_hash(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-amostras.json', lambda r: r['samples'][0].update(review_text='SYNTHETIC_FORBIDDEN_FIELD'))
            with self.assertRaisesRegex(ValueError, 'allowlist'):
                check_public(folder)

    def test_claimed_accuracy_fails_even_with_updated_hash(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-real.json', lambda r: r['variants']['after'].update(persisted_joint_accuracy=1))
            with self.assertRaisesRegex(ValueError, 'avaliacao semantica'):
                check_public(folder)

    def test_claimed_reduction_fails_even_with_updated_hash(self):
        with directory() as folder:
            self.copy_evidence(folder)
            self.mutate(folder, 'benchmark-dev-real.json', lambda r: r['comparison'].update(llm_calls_reduction_percent=75))
            with self.assertRaisesRegex(ValueError, 'Reducao'):
                check_public(folder)


class DocumentationLinkTests(unittest.TestCase):
    def test_heading_accents_inline_code_and_duplicate_anchors(self):
        self.assertEqual(markdown_anchors('# Ação `DEV`\n## Ação DEV\n'), {'ação-dev', 'ação-dev-1'})

    def test_ignore_fenced_examples_and_external_links(self):
        self.assertEqual(links('```md\n[x](absent.md)\n```\n`[x](absent.md)`\n[site](https://example.invalid)', '.md'), ['https://example.invalid'])

    def test_relative_links_fragments_spaces_and_html(self):
        with directory() as folder:
            source = folder / 'README.md'
            source.write_text('# Ação\n[local](#a%C3%A7%C3%A3o)\n[space](<My Report.md#resultado>)\n[html](report.html#ok)\n[site](https://example.invalid)', encoding='utf-8')
            (folder / 'My Report.md').write_text('# Resultado\n', encoding='utf-8')
            (folder / 'report.html').write_text('<h1 id="ok">OK</h1>', encoding='utf-8')
            self.assertEqual(validate([source], folder), (3, []))

    def test_missing_target_and_anchor_are_reported(self):
        with directory() as folder:
            source = folder / 'README.md'
            source.write_text('# Existing\n[x](absent.md)\n[y](#missing)', encoding='utf-8')
            count, errors = validate([source], folder)
            self.assertEqual((count, len(errors)), (2, 2))
            self.assertIn('destino ausente', errors[0])
            self.assertIn('ancora ausente', errors[1])


if __name__ == '__main__':
    unittest.main()
