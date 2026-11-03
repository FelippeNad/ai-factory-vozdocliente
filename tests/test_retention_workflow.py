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
        for name in ("Airtable DEV operacao", "Airtable DEV sem body"):
            for mutation in ["retry", "redirect"]:
                with self.subTest(node=name, mutation=mutation):
                    workflow = build()
                    http = next(node for node in workflow["nodes"] if node["name"] == name)
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

    def test_missing_or_invalid_http_body_configuration_rejected(self):
        for key, invalid_values in {
            "sendBody": [None, False, "true", "={{ $json.request.body !== undefined }}"],
            "contentType": [None, "raw", "form-urlencoded"],
            "specifyBody": [None, "keypair"],
            "jsonBody": [None, "", "={}", "={{ JSON.stringify($json.request.body.fields) }}"],
        }.items():
            for value in invalid_values:
                with self.subTest(parameter=key, value=value):
                    workflow = build()
                    http = next(node for node in workflow["nodes"] if node["type"].endswith(".httpRequest"))
                    if value is None:
                        http["parameters"].pop(key)
                    else:
                        http["parameters"][key] = value
                    self.assertTrue(retention_structure_errors(workflow))

    def test_bodyless_transport_and_router_regressions_rejected(self):
        for mutation in ("send_true", "send_expression", "send_missing", "payload", "bypass_guard", "invert_branches", "missing_router"):
            with self.subTest(mutation=mutation):
                workflow = build()
                reader = next(node for node in workflow["nodes"] if node["name"] == "Airtable DEV sem body")
                if mutation == "send_true":
                    reader["parameters"]["sendBody"] = True
                elif mutation == "send_expression":
                    reader["parameters"]["sendBody"] = "={{ false }}"
                elif mutation == "send_missing":
                    reader["parameters"].pop("sendBody")
                elif mutation == "payload":
                    reader["parameters"]["jsonBody"] = "={}"
                elif mutation == "bypass_guard":
                    workflow["connections"]["Agenda de retencao"]["main"][0].append(
                        {"node": reader["name"], "type": "main", "index": 0})
                elif mutation == "invert_branches":
                    workflow["connections"]["Operacao com body?"]["main"].reverse()
                else:
                    workflow["nodes"] = [node for node in workflow["nodes"] if node["name"] != "Operacao com body?"]
                self.assertTrue(retention_structure_errors(workflow))

    def test_v3_and_v4_blobs_unchanged(self):
        for version, expected in [(3, "8c21523b18d2dc0fca3aba6456b042036d7b379e"),
                                  (4, "a454e445ab7600a27ba6e5b23383be00a42387f6")]:
            with self.subTest(version=version):
                data = (ROOT / f"n8n-mirror/workflows/vozdocliente-router-v{version}.json").read_bytes().replace(b"\r\n", b"\n")
                blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
                self.assertEqual(hashlib.sha1(blob).hexdigest(), expected)

    def test_slack_endpoint_body_and_gate_regressions_rejected(self):
        for mutation in ("url", "body", "expression", "retry", "bypass", "gate"):
            with self.subTest(mutation=mutation):
                workflow = build()
                slack = next(node for node in workflow["nodes"] if node["name"] == "Slack DEV falha")
                if mutation == "url":
                    slack["parameters"]["url"] = "={{ $json.url }}"
                elif mutation == "body":
                    slack["parameters"]["jsonBody"] = "={{ JSON.stringify($json) }}"
                elif mutation == "expression":
                    slack["parameters"]["sendBody"] = "={{ true }}"
                elif mutation == "retry":
                    slack["retryOnFail"] = True
                elif mutation == "bypass":
                    workflow["connections"]["Agenda de retencao"]["main"][0].append(
                        {"node": slack["name"], "type": "main", "index": 0})
                else:
                    workflow["connections"]["Alertar falha DEV?"]["main"].reverse()
                self.assertTrue(retention_structure_errors(workflow))


if __name__ == "__main__":
    unittest.main(verbosity=2)
