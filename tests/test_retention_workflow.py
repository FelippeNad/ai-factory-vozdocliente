"""Valida exportacoes, barreiras de grafo e preservacao da classificacao."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_retention_workflow import build, build_demo, serialized, OUTPUT, DEMO_OUTPUT
from validate_workflows import retention_structure_errors


class RetentionWorkflowTests(unittest.TestCase):
    def test_generated_workflows_match_sources(self):
        for output, workflow in [(OUTPUT, build()), (DEMO_OUTPUT, build_demo())]:
            with self.subTest(path=output.name):
                self.assertEqual(output.read_text(encoding="utf-8"), serialized(workflow))

    def test_operational_structure(self):
        self.assertEqual(retention_structure_errors(build()), [])

    def test_demo_structure(self):
        self.assertEqual(retention_structure_errors(build_demo(), demo=True), [])

    def test_direct_bypass_rejected(self):
        workflow = build()
        workflow["connections"]["Agenda de retencao"]["main"][0].append(
            {"node": "Airtable DEV operacao", "type": "main", "index": 0})
        self.assertTrue(retention_structure_errors(workflow))

    def test_gate_bypass_rejected(self):
        workflow = build()
        workflow["connections"]["Validar operacao DEV"]["main"][0].append(
            {"node": "Airtable DEV operacao", "type": "main", "index": 0})
        self.assertTrue(retention_structure_errors(workflow))

    def test_http_retry_and_redirect_rejected(self):
        for mutation in ["retry", "redirect"]:
            workflow = build()
            http = next(node for node in workflow["nodes"] if node["type"].endswith(".httpRequest"))
            if mutation == "retry":
                http["retryOnFail"] = True
            else:
                http["parameters"]["options"]["redirect"]["redirect"]["followRedirects"] = True
            self.assertTrue(retention_structure_errors(workflow))

    def test_activation_and_pinning_rejected(self):
        for mutation in [{"active": True}, {"pinData": {"example": [{}]}}]:
            workflow = build()
            workflow.update(copy.deepcopy(mutation))
            self.assertTrue(retention_structure_errors(workflow))

    def test_v3_and_v4_blobs_unchanged(self):
        for version, expected in [(3, "8c21523b18d2dc0fca3aba6456b042036d7b379e"),
                                  (4, "a454e445ab7600a27ba6e5b23383be00a42387f6")]:
            with self.subTest(version=version):
                data = (ROOT / f"n8n-mirror/workflows/vozdocliente-router-v{version}.json").read_bytes().replace(b"\r\n", b"\n")
                blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
                self.assertEqual(hashlib.sha1(blob).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
