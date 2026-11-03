"""Integridade do candidato DEV e rejeicao de bypass/credenciais."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_router_optimized_workflow import build, serialized, OUTPUT
from validate_workflows import optimized_structure_errors


class RouterOptimizationTests(unittest.TestCase):
    def test_export_matches_generator(self):
        self.assertEqual(OUTPUT.read_text(encoding="utf-8"), serialized(build()))

    def test_candidate_passes(self):
        self.assertEqual(optimized_structure_errors(build()), [])

    def test_bypasses_rejected(self):
        for source in ("Webhook Review", "Sanitizar PII", "Preparar deduplicacao DEV", "Airtable Precheck DEV"):
            with self.subTest(source=source):
                workflow = build()
                workflow["connections"][source]["main"][0].append({"node": "LLM DEV", "type": "main", "index": 0})
                self.assertTrue(optimized_structure_errors(workflow))

    def test_duplicate_branch_rejected(self):
        workflow = build()
        workflow["connections"]["Ja existe? DEV"]["main"].reverse()
        self.assertTrue(optimized_structure_errors(workflow))

    def test_final_check_bypass_rejected(self):
        workflow = build()
        workflow["connections"]["Parse + Merge"]["main"][0] = [{"node": "Airtable DEV", "type": "main", "index": 0}]
        self.assertTrue(optimized_structure_errors(workflow))

    def test_pii_or_error_policy_mutations_rejected(self):
        for mutation in ("prompt", "sanitizer", "parser", "credentials", "on_error", "base", "activate"):
            with self.subTest(mutation=mutation):
                workflow = build()
                nodes = {node["name"]: node for node in workflow["nodes"]}
                if mutation == "prompt":
                    nodes["LLM DEV"]["parameters"]["jsonBody"] = "={{ $json.body.review_text }}"
                elif mutation in {"sanitizer", "parser"}:
                    nodes["Sanitizar PII" if mutation == "sanitizer" else "Parse + Merge"]["parameters"]["jsCode"] = "return [];"
                elif mutation == "credentials":
                    nodes["LLM DEV"]["credentials"] = {"httpHeaderAuth": {"id": "synthetic"}}
                elif mutation == "on_error":
                    nodes["Validar busca e restaurar texto"]["onError"] = "continueRegularOutput"
                elif mutation == "base":
                    nodes["Airtable Buscar review_id"]["parameters"]["url"] = "={{ $env.AIRTABLE_BASE_ID }}"
                else:
                    workflow["active"] = True
                self.assertTrue(optimized_structure_errors(workflow))

    def test_baseline_core_is_preserved(self):
        baseline = json.loads((ROOT / "n8n-mirror/workflows/vozdocliente-router-v4.json").read_text(encoding="utf-8"))
        candidate = {node["name"]: node for node in build()["nodes"]}
        for node in baseline["nodes"]:
            if node["name"] in {"Sanitizar PII", "Parse + Merge"}:
                self.assertEqual(candidate[node["name"]]["parameters"], node["parameters"])
        original_llm = next(node for node in baseline["nodes"] if node["name"] == "LLM PROD")
        self.assertEqual(candidate["LLM DEV"]["parameters"]["jsonBody"], original_llm["parameters"]["jsonBody"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
