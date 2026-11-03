"""Deriva candidato v4 DEV inativo; preserva baseline, sanitizador, prompt e parser."""
import argparse
import copy
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "n8n-mirror/workflows/vozdocliente-router-v4.json"
OUTPUT = ROOT / "n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json"
SOURCE = ROOT / "n8n-mirror/router-dev"


def build():
    workflow = json.loads(BASELINE.read_text(encoding="utf-8"))
    workflow.update(name="VozDoCliente - v4 DEV (deduplicacao antes do LLM)", active=False, pinData={})
    for node in workflow["nodes"]:
        node["name"] = node["name"].replace(" PROD", " DEV")
        if node["name"].startswith("dedup"):
            node["name"] = "Confirmar novo? DEV"
        node["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router/v4-optimized-dev/" + node["name"]))
        node.pop("credentials", None)
        if node["type"] == "n8n-nodes-base.httpRequest":
            node.update(retryOnFail=False, onError="stopWorkflow")
            node["parameters"]["options"] = {"timeout": 15000,
                "redirect": {"redirect": {"followRedirects": False}}}
    nodes = {node["name"]: node for node in workflow["nodes"]}
    webhook = nodes["Webhook Review"]
    webhook["parameters"]["path"] = "review-v4-otimizado-dev"
    webhook["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router/v4-optimized-dev/webhook"))
    lookup = nodes["Airtable Buscar review_id"]
    lookup["parameters"].update(method="GET", url="={{ $('Preparar deduplicacao DEV').item.json.lookup_url }}", sendQuery=True,
        queryParameters={"parameters": [
            {"name": "maxRecords", "value": "1"}, {"name": "fields[]", "value": "review_id"},
            {"name": "filterByFormula", "value": "={{ \"{review_id}='\" + $json.review_id + \"'\" }}"}]})
    lookup["parameters"]["options"]["response"] = {"response": {"fullResponse": True, "responseFormat": "json"}}
    precheck = copy.deepcopy(lookup)
    precheck.update(name="Airtable Precheck DEV",
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router/v4-optimized-dev/Airtable Precheck DEV")))
    precheck["parameters"]["url"] = "={{ $json.lookup_url }}"
    workflow["nodes"].append(precheck)
    nodes["Airtable DEV"]["parameters"]["url"] = "={{ $('Preparar deduplicacao DEV').item.json.lookup_url }}"
    slack = nodes["Slack DEV"]["parameters"]
    channel = "{{ JSON.stringify((() => { const channel = $env.CLASSIFIER_SLACK_DEV_CHANNEL_ID; if (typeof channel !== 'string' || channel.trim() !== channel || !/^[CG][A-Z0-9]{8,31}$/.test(channel)) { throw new Error('Canal Slack DEV invalido.'); } return channel; })()) }}"
    slack["jsonBody"] = slack["jsonBody"].replace('"channel": "#cx-alertas"', '"channel": ' + channel)
    gate = nodes["Confirmar novo? DEV"]["parameters"]["conditions"]
    gate["conditions"] = [{"id": "already-exists", "leftValue": "={{ $json.duplicate }}", "rightValue": True,
                           "operator": {"type": "boolean", "operation": "true", "singleValue": True}}]
    pre_gate = copy.deepcopy(nodes["Confirmar novo? DEV"])
    pre_gate.update(name="Ja existe? DEV",
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router/v4-optimized-dev/Ja existe? DEV")))
    workflow["nodes"].append(pre_gate)
    for name, filename, position in [
        ("Preparar deduplicacao DEV", "prepare-dedup.js", [200, 0]),
        ("Validar busca e restaurar texto", "validate-lookup.js", [600, 0]),
        ("Validar busca final DEV", "validate-lookup.js", [1600, 0]),
    ]:
        workflow["nodes"].append({"name": name, "type": "n8n-nodes-base.code", "typeVersion": 2,
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router/v4-optimized-dev/" + name)),
            "position": position, "parameters": {"mode": "runOnceForAllItems", "language": "javaScript",
                "jsCode": (SOURCE / filename).read_text(encoding="utf-8")}})
    negative = next(node["name"] for node in workflow["nodes"] if node["name"].endswith("negativo?"))
    def links(*targets):
        return {"main": [[{"node": name, "type": "main", "index": 0}] if name else [] for name in targets]}
    workflow["connections"] = {
        "Webhook Review": links("Sanitizar PII"), "Sanitizar PII": links("Preparar deduplicacao DEV"),
        "Preparar deduplicacao DEV": links("Airtable Precheck DEV"),
        "Airtable Precheck DEV": links("Validar busca e restaurar texto"),
        "Validar busca e restaurar texto": links("Ja existe? DEV"),
        "Ja existe? DEV": links(None, "LLM DEV"), "LLM DEV": links("Parse + Merge"),
        "Parse + Merge": links("Airtable Buscar review_id"),
        "Airtable Buscar review_id": links("Validar busca final DEV"),
        "Validar busca final DEV": links("Confirmar novo? DEV"),
        "Confirmar novo? DEV": links(None, "Airtable DEV"),
        "Airtable DEV": links(negative), negative: links("Slack DEV"),
    }
    positions = {"Webhook Review": [-200, 0], "Sanitizar PII": [0, 0], "Airtable Precheck DEV": [400, 0],
        "Ja existe? DEV": [800, 0], "LLM DEV": [1000, 0], "Parse + Merge": [1200, 0],
        "Airtable Buscar review_id": [1400, 0], "Confirmar novo? DEV": [1800, 0],
        "Airtable DEV": [2000, 0], negative: [2200, 0], "Slack DEV": [2400, 0]}
    for node in workflow["nodes"]:
        node["position"] = positions.get(node["name"], node["position"])
    return workflow


def serialized(workflow):
    return json.dumps(workflow, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = serialized(build())
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != expected:
            raise SystemExit("Export DEV otimizado desatualizado; execute o gerador.")
        print("[OK] Export DEV otimizado corresponde as fontes; baseline preservada.")
    else:
        OUTPUT.write_text(expected, encoding="utf-8", newline="\n")
        print("[OK] Export DEV otimizado gerado inativo e sem credenciais; nenhuma API executada.")
