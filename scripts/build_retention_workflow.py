"""Gera workflow independente; nao importa n8n, nao acessa rede nem ativa nada."""
import argparse
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "n8n-mirror/workflows/vozdocliente-retencao-v1.json"
DEMO_OUTPUT = ROOT / "n8n-mirror/workflows/vozdocliente-retencao-demo.json"
SOURCE = ROOT / "n8n-mirror/retention"


def build():
    common = (SOURCE / "common.js").read_text(encoding="utf-8")
    nodes = []

    def node(name, kind, version, parameters, position, **extra):
        nodes.append(dict(name=name, type=f"n8n-nodes-base.{kind}", typeVersion=version,
                          parameters=parameters, position=position,
                          id=str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/retention/v1/" + name)), **extra))

    def code(name, source, position):
        node(name, "code", 2, {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": source}, position)

    node("Agenda de retencao", "scheduleTrigger", 1.2,
         {"rule": {"interval": [{"field": "cronExpression", "expression": "0 3 * * *"}]}}, [-1000, 0])
    code("Motor de retencao", common + "\n" + (SOURCE / "engine.js").read_text(encoding="utf-8"), [-760, 0])
    node("Limitar taxa", "wait", 1.1, {"resume": "timeInterval", "amount": 1, "unit": "seconds"}, [-520, 0],
         webhookId="vozdocliente-retention-rate-limit")
    code("Validar operacao DEV", common + "\n" + (SOURCE / "guard.js").read_text(encoding="utf-8"), [-280, 0])
    node("Ha operacao segura?", "if", 2, {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
        "conditions": [{"id": "pending", "leftValue": "={{ $json.has_request }}", "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}, [-40, 0])
    # HTTP Request 4.1 declara sendBody com noDataExpression=true.
    # A condicao fica em IF; cada transporte usa um booleano literal.
    node("Operacao com body?", "if", 2, {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
        "conditions": [{"id": "has-body", "leftValue": "={{ $json.request.body !== undefined }}", "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}, [200, -160])
    transport = {
        "method": "={{ $json.request.method }}", "url": "={{ $json.request.url }}",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 15000, "redirect": {"redirect": {"followRedirects": False}},
                    "response": {"response": {"fullResponse": True, "neverError": True, "responseFormat": "json"}}},
    }
    node("Airtable DEV operacao", "httpRequest", 4.1, {
        **transport, "sendBody": True, "contentType": "json", "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json.request.body) }}",
    }, [440, -280], onError="continueRegularOutput", retryOnFail=False)
    node("Airtable DEV sem body", "httpRequest", 4.1, {
        **transport, "sendBody": False,
    }, [440, -40], onError="continueRegularOutput", retryOnFail=False)
    code("Receber resposta", """const previous = $('Validar operacao DEV').item.json;
return [{ json: { state: previous.state, response: $input.first().json }, pairedItem: { item: 0 } }];
""", [680, -160])
    code("Resumo sem PII", common + """
const s = $input.first().json.state;
return [{ json: {
  run_id: s.run_id, mode: s.config?.dry_run === false ? 'DELETE_DEV' : 'DRY_RUN',
  status: s.config ? status(s) : 'blocked', started_at: s.started_at, finished_at: new Date().toISOString(),
  retention_days: s.config?.days ?? null, cutoff: s.cutoff ?? null,
  ...s.metrics, error_codes: s.codes, scan_complete: s.scan_complete,
  audit_persisted: !!s.audit_id, audit_finalized: s.audit_finalized,
  preview: s.config?.dry_run ? s.candidates.slice(0, s.config.maxDelete).map(c => ({ record_id: c.id, processed_at: c.processed_at })) : [],
  preview_truncated: s.metrics.eligible > (s.config?.maxDelete ?? 0)
} }];
""", [200, 120])
    code("Observabilidade DEV", common + "\n" + (SOURCE / "observe.js").read_text(encoding="utf-8"), [440, 160])
    node("Alertar falha DEV?", "if", 2, {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
        "conditions": [{"id": "alert", "leftValue": "={{ $json.send_alert }}", "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}, [680, 160])
    node("Slack DEV falha", "httpRequest", 4.1, {
        "method": "POST", "url": "https://slack.com/api/chat.postMessage",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "contentType": "json", "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json.slack_body) }}",
        "options": {"timeout": 5000, "redirect": {"redirect": {"followRedirects": False}},
                    "response": {"response": {"fullResponse": True, "neverError": True, "responseFormat": "json"}}},
    }, [920, 80], onError="continueRegularOutput", retryOnFail=False)
    code("Resultado observabilidade", (SOURCE / "observe-result.js").read_text(encoding="utf-8"), [1160, 160])
    connections = {}

    def connect(src, *targets):
        connections[src] = {"main": [[{"node": dst, "type": "main", "index": 0}] for dst in targets]}

    connect("Agenda de retencao", "Motor de retencao")
    connect("Motor de retencao", "Limitar taxa")
    connect("Limitar taxa", "Validar operacao DEV")
    connect("Validar operacao DEV", "Ha operacao segura?")
    connect("Ha operacao segura?", "Operacao com body?", "Resumo sem PII")
    connect("Operacao com body?", "Airtable DEV operacao", "Airtable DEV sem body")
    connect("Airtable DEV operacao", "Receber resposta")
    connect("Airtable DEV sem body", "Receber resposta")
    connect("Receber resposta", "Motor de retencao")
    connect("Resumo sem PII", "Observabilidade DEV")
    connect("Observabilidade DEV", "Alertar falha DEV?")
    connect("Alertar falha DEV?", "Slack DEV falha", "Resultado observabilidade")
    connect("Slack DEV falha", "Resultado observabilidade")
    return {"name": "VozDoCliente - Retencao DEV v1 (DRY_RUN por padrao)", "nodes": nodes,
            "connections": connections, "active": False, "pinData": {},
            "settings": {"executionOrder": "v1", "timezone": "America/Sao_Paulo", "executionTimeout": 900,
                         "saveDataErrorExecution": "none", "saveDataSuccessExecution": "none",
                         "saveManualExecutions": False, "saveExecutionProgress": False}, "tags": []}


def build_demo():
    workflow = build()
    workflow["name"] = "VozDoCliente - Retencao DEMO OFFLINE (sem HTTP)"
    demo_env = {"RETENTION_ENV": "DEV", "RETENTION_DRY_RUN": "true", "RETENTION_DAYS": "30",
                "RETENTION_DEV_BASE_ID": "app00000000000000", "RETENTION_TABLE_ID": "tbl00000000000001",
                "RETENTION_TABLE_NAME": "Reviews",
                "RETENTION_AUDIT_TABLE_ID": "tbl00000000000002", "RETENTION_PAGE_SIZE": "2"}
    for node in workflow["nodes"]:
        node["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/retention/demo/" + node["name"]))
        if node["name"] in {"Motor de retencao", "Validar operacao DEV"}:
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace("settings($env)", "settings(" + json.dumps(demo_env) + ")")
        if node["type"] == "n8n-nodes-base.wait":
            node["webhookId"] = "vozdocliente-retention-demo-rate-limit"
        if node["type"] == "n8n-nodes-base.httpRequest":
            source = (SOURCE / "common.js").read_text(encoding="utf-8") + "\n" + (SOURCE / "demo-transport.js").read_text(encoding="utf-8")
            if node["name"] == "Slack DEV falha":
                source = "return [{ json: { statusCode: 200, body: { ok: true } }, pairedItem: { item: 0 } }];\n"
            node.update(type="n8n-nodes-base.code", typeVersion=2,
                        parameters={"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": source})
            node.pop("onError", None)
            node.pop("retryOnFail", None)
        if node["name"] == "Observabilidade DEV":
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace("const alertEnv = $env;",
                "const alertEnv = { RETENTION_ENV: 'DEV', RETENTION_ALERTS_ENABLED: 'true', RETENTION_SLACK_DEV_CHANNEL_ID: 'C00000000' };")
        if node["name"] == "Resultado observabilidade":
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace("const simulated = false;", "const simulated = true;")
    return workflow


def serialized(workflow):
    return json.dumps(workflow, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Falha se o JSON nao corresponde as fontes")
    args = parser.parse_args()
    for output, workflow in [(OUTPUT, build()), (DEMO_OUTPUT, build_demo())]:
        expected = serialized(workflow)
        if args.check:
            if output.read_text(encoding="utf-8") != expected:
                raise SystemExit("Workflow de retencao desatualizado; execute o gerador.")
            print(f"[OK] {output.name} corresponde as fontes JavaScript.")
        else:
            output.write_text(expected, encoding="utf-8", newline="\n")
            print(f"{output.name} gerado inativo; nenhuma chamada externa realizada.")
