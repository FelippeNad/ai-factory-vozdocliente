"""Regressoes do validador: um bypass introduzido precisa fazer o CI falhar."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from validate_workflows import pii_structure_errors

ROOT = Path(__file__).resolve().parents[1]


class WorkflowSecurityTests(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads((ROOT / "n8n-mirror/workflows/vozdocliente-router-v4.json").read_text(encoding="utf-8"))

    def add_edge(self, source, target, connection="main"):
        self.workflow["connections"].setdefault(source, {}).setdefault(connection, [[]])[0].append(
            {"node": target, "type": connection, "index": 0})

    def test_v4_passes(self):
        self.assertEqual(pii_structure_errors(self.workflow), [])

    def test_direct_bypass(self):
        self.add_edge("Webhook Review", "LLM PROD")
        self.assertIn("caminho do webhook ao LLM sem sanitizacao", pii_structure_errors(self.workflow))

    def test_indirect_bypass(self):
        self.add_edge("Webhook Review", "Parse + Merge")
        self.add_edge("Slack PROD", "LLM PROD")
        self.assertIn("caminho do webhook ao LLM sem sanitizacao", pii_structure_errors(self.workflow))

    def test_non_main_connection_bypass(self):
        self.add_edge("Webhook Review", "LLM PROD", "error")
        self.assertIn("caminho do webhook ao LLM sem sanitizacao", pii_structure_errors(self.workflow))

    def test_cycle_does_not_hide_bypass(self):
        self.add_edge("Webhook Review", "Webhook Review")
        self.add_edge("Webhook Review", "LLM PROD")
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_disconnected_llm(self):
        del self.workflow["connections"]["Sanitizar PII"]
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_absent_sanitizer(self):
        self.workflow["nodes"] = [node for node in self.workflow["nodes"] if node["name"] != "Sanitizar PII"]
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_disabled_or_fail_open_nodes(self):
        for name in ["Sanitizar PII", "LLM PROD"]:
            for flag in [{"disabled": True}, {"continueOnFail": True}, {"onError": "continueRegularOutput"}]:
                with self.subTest(name=name, flag=flag):
                    mutated = copy.deepcopy(self.workflow)
                    next(node for node in mutated["nodes"] if node["name"] == name).update(flag)
                    self.assertTrue(pii_structure_errors(mutated))

    def test_original_text_fallback_rejected(self):
        llm = next(node for node in self.workflow["nodes"] if node["name"] == "LLM PROD")
        llm["parameters"]["jsonBody"] = llm["parameters"]["jsonBody"].replace(
            "$json.review_text_sanitized", "$json.review_text_sanitized || $json.body.review_text")
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_extra_dynamic_message_rejected(self):
        llm = next(node for node in self.workflow["nodes"] if node["name"] == "LLM PROD")
        llm["parameters"]["jsonBody"] = llm["parameters"]["jsonBody"].replace(
            '"model": "gpt-5.6-luna"', '"model": "{{ $json.body.review_text }}"')
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_execution_retention_rejected(self):
        self.workflow["settings"]["saveDataErrorExecution"] = "all"
        self.assertTrue(pii_structure_errors(self.workflow))

    def test_credentials_and_existing_node_versions_preserved(self):
        old = json.loads((ROOT / "n8n-mirror/workflows/vozdocliente-router-v3.json").read_text(encoding="utf-8"))
        current = {node["name"]: node for node in self.workflow["nodes"]}
        for node in old["nodes"]:
            self.assertEqual(current[node["name"]].get("credentials"), node.get("credentials"))
            self.assertEqual(current[node["name"]]["typeVersion"], node["typeVersion"])

    def test_v3_reference_unchanged(self):
        # Hash Git do arquivo original, registrado antes de qualquer alteracao.
        data = (ROOT / "n8n-mirror/workflows/vozdocliente-router-v3.json").read_bytes()
        # Normaliza CRLF de checkouts Windows para o blob versionado.
        data = data.replace(b"\r\n", b"\n")
        blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        self.assertEqual(hashlib.sha1(blob).hexdigest(), "8c21523b18d2dc0fca3aba6456b042036d7b379e")


if __name__ == "__main__":
    unittest.main(verbosity=2)
