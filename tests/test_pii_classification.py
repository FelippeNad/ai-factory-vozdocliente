"""Pares compartilhados: JS valida a sanitizacao real; Python valida o mock legado."""
import json
from pathlib import Path
import unittest

from test_routing_logic import classify, should_alert, SENTIMENTS, THEMES


class PiiClassificationTests(unittest.TestCase):
    def test_classification_and_alert_are_preserved(self):
        cases = json.loads((Path(__file__).parent / "fixtures/pii_semantic_cases.json").read_text(encoding="utf-8"))
        self.assertEqual({case["expected"]["theme"] for case in cases}, THEMES)
        self.assertEqual({case["expected"]["sentiment"] for case in cases}, SENTIMENTS)
        for case in cases:
            with self.subTest(scenario=case["name"]):
                original = classify(case["original"])
                sanitized = classify(case["sanitized"])
                self.assertEqual(original, case["expected"])
                self.assertEqual(sanitized, original)
                self.assertEqual(should_alert(sanitized), sanitized["sentiment"] == "negativo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
