"""Candidata instrumentada + observador + Error Workflow; geracao local sem APIs."""
import argparse
import copy
import json
from pathlib import Path
import uuid

from build_router_optimized_workflow import build as optimized
from build_retention_workflow import build as retention

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "n8n-mirror/observability"
OUTPUT = ROOT / "n8n-mirror/workflows"
SETTINGS = {"executionOrder": "v1", "saveDataErrorExecution": "none", "saveDataSuccessExecution": "none",
            "saveManualExecutions": False, "saveExecutionProgress": False}


def common():
    contract = json.loads((SOURCE / "router-contract.json").read_text(encoding="utf-8"))
    return "const OBS_CONTRACT = " + json.dumps(contract) + ";\n" + (SOURCE / "router-common.js").read_text(encoding="utf-8") + "\n"


def node(name, kind, version, parameters, **extra):
    return dict(name=name, type="n8n-nodes-base." + kind, typeVersion=version, parameters=parameters,
                position=[0, 0], id=str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router-observability/v1/" + name)), **extra)


def code(name, source):
    return node(name, "code", 2, {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": common() + source})


def gate(name, expression):
    return node(name, "if", 2, {"conditions": {"options": {"caseSensitive": True, "leftValue": "",
        "typeValidation": "strict", "version": 1}, "conditions": [{"id": "decision", "leftValue": expression,
        "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}})


def link(workflow, source, *targets):
    workflow["connections"][source] = {"main": [[{"node": target, "type": "main", "index": 0}] if target else [] for target in targets]}


def layout(workflow):
    for index, item in enumerate(workflow["nodes"]):
        item["position"] = [(index % 8) * 260, (index // 8) * 260]
    return workflow


def base(name):
    return {"name": name, "nodes": [], "connections": {}, "active": False, "pinData": {}, "settings": copy.deepcopy(SETTINGS), "tags": []}


def delivery(workflow, incoming, failure_stop=False):
    workflow["nodes"] += [code("Entregar observabilidade DEV", "return obsDelivery();"),
        gate("Observador configurado?", "={{ $json.send_observation }}"),
        node("Enviar observabilidade DEV", "executeWorkflow", 1,
             {"source": "database", "workflowId": "={{ $json.observer_workflow_id }}", "mode": "once",
              "options": {"waitForSubWorkflow": True}}, onError="continueRegularOutput", retryOnFail=False),
        code("Resultado Router DEV", (SOURCE / "router-result.js").read_text(encoding="utf-8"))]
    for source in incoming:
        link(workflow, source, "Entregar observabilidade DEV")
    link(workflow, "Entregar observabilidade DEV", "Observador configurado?")
    link(workflow, "Observador configurado?", "Enviar observabilidade DEV", "Resultado Router DEV")
    link(workflow, "Enviar observabilidade DEV", "Resultado Router DEV")
    if failure_stop:
        workflow["nodes"] += [gate("Falhou Router DEV?", "={{ $json.report.status === 'failure' }}"),
            node("Interromper com seguranca", "stopAndError", 1,
                 {"errorType": "errorMessage", "errorMessage": "Falha operacional no Router DEV. Consultar evento sem PII pelo run_id."})]
        link(workflow, "Resultado Router DEV", "Falhou Router DEV?")
        link(workflow, "Falhou Router DEV?", "Interromper com seguranca", None)


def build_router():
    workflow = optimized()
    workflow.update(name="VozDoCliente - Router v4 otimizado observavel DEV", connections={})
    nodes = {item["name"]: item for item in workflow["nodes"]}
    nodes["Webhook Review"]["parameters"]["path"] = "review-v4-observavel-dev"
    nodes["Webhook Review"]["webhookId"] = "vozdocliente-v4-observavel-dev"
    # ID do Error Workflow sera escolhido na UI; nao exportar IDs locais/creds.
    workflow["settings"].update(copy.deepcopy(SETTINGS))
    workflow["nodes"].append(code("Recebimento observado DEV", "return obsStart();"))
    steps = [
        ("Sanitizacao observada DEV", "sanitization", "success", "Recebimento observado DEV"),
        ("Precheck iniciado DEV", "precheck", "started", "Sanitizacao observada DEV"),
        ("Precheck observado DEV", "precheck", "success", "Precheck iniciado DEV"),
        ("LLM iniciado DEV", "llm", "started", "Precheck observado DEV"),
        ("LLM observado DEV", "llm", "success", "LLM iniciado DEV"),
        ("Deduplicacao final iniciada DEV", "final_dedup", "started", "LLM observado DEV"),
        ("Deduplicacao final observada DEV", "final_dedup", "success", "Deduplicacao final iniciada DEV"),
        ("Persistencia iniciada DEV", "persistence", "started", "Deduplicacao final observada DEV"),
        ("Persistencia observada DEV", "persistence", "success", "Persistencia iniciada DEV"),
        ("Slack CX iniciado DEV", "business_slack", "started", "Persistencia observada DEV"),
        ("Slack CX observado DEV", "business_slack", "success", "Slack CX iniciado DEV"),
    ]
    for name, stage, status, previous in steps:
        workflow["nodes"].append(code(name, f"return obsStep({stage!r}, {status!r}, {previous!r});"))
    for name, status, previous in [("Duplicata precheck DEV", "duplicate", "Precheck observado DEV"),
                                   ("Duplicata final DEV", "duplicate", "Deduplicacao final observada DEV"),
                                   ("Sucesso Router DEV", "success", None)]:
        workflow["nodes"].append(code(name, f"return obsFinish({status!r}, {previous!r});".replace("None", "null")))
    paths = [
        ["Webhook Review", "Recebimento observado DEV", "Sanitizar PII", "Sanitizacao observada DEV",
         "Preparar deduplicacao DEV", "Precheck iniciado DEV", "Airtable Precheck DEV", "Validar busca e restaurar texto",
         "Precheck observado DEV", "Ja existe? DEV"],
        ["LLM iniciado DEV", "LLM DEV", "Parse + Merge", "LLM observado DEV", "Deduplicacao final iniciada DEV",
         "Airtable Buscar review_id", "Validar busca final DEV", "Deduplicacao final observada DEV", "Confirmar novo? DEV"],
        ["Persistencia iniciada DEV", "Airtable DEV", "Persistencia observada DEV", "É negativo?"],
        ["Slack CX iniciado DEV", "Slack DEV", "Slack CX observado DEV", "Sucesso Router DEV"],
    ]
    for path in paths:
        for source, target in zip(path, path[1:]):
            link(workflow, source, target)
    link(workflow, "Ja existe? DEV", "Duplicata precheck DEV", "LLM iniciado DEV")
    link(workflow, "Confirmar novo? DEV", "Duplicata final DEV", "Persistencia iniciada DEV")
    link(workflow, "É negativo?", "Slack CX iniciado DEV", "Sucesso Router DEV")
    failures = [
        ("Sanitizar PII", "sanitization", "SANITIZATION_FAILED", "Recebimento observado DEV"),
        ("Preparar deduplicacao DEV", "precheck", "DEV_CONFIG_INVALID", "Sanitizacao observada DEV"),
        ("Airtable Precheck DEV", "precheck", "PRECHECK_HTTP_FAILED", "Precheck iniciado DEV"),
        ("Validar busca e restaurar texto", "precheck", "PRECHECK_INVALID", "Precheck iniciado DEV"),
        ("LLM DEV", "llm", "LLM_HTTP_FAILED", "LLM iniciado DEV"),
        ("Parse + Merge", "llm", "CLASSIFICATION_INVALID", "LLM iniciado DEV"),
        ("Airtable Buscar review_id", "final_dedup", "FINAL_DEDUP_HTTP_FAILED", "Deduplicacao final iniciada DEV"),
        ("Validar busca final DEV", "final_dedup", "FINAL_DEDUP_INVALID", "Deduplicacao final iniciada DEV"),
        ("Airtable DEV", "persistence", "PERSISTENCE_HTTP_FAILED", "Persistencia iniciada DEV"),
        ("Slack DEV", "business_slack", "BUSINESS_SLACK_FAILED", "Slack CX iniciado DEV"),
    ]
    terminals = ["Duplicata precheck DEV", "Duplicata final DEV", "Sucesso Router DEV"]
    for source, stage, error, previous in failures:
        name = "Falha segura: " + source
        response = ", true" if source == "Parse + Merge" else ""
        workflow["nodes"].append(code(name, f"return obsFinish('failure', {previous!r}, {stage!r}, {error!r}{response});"))
        nodes[source]["onError"] = "continueErrorOutput"
        workflow["connections"][source]["main"].append([{"node": name, "type": "main", "index": 0}])
        terminals.append(name)
    delivery(workflow, terminals, failure_stop=True)
    # IDs proprios: a candidata nao substitui os exports anteriores na importacao.
    for item in workflow["nodes"]:
        item["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router-observable-dev/" + item["name"]))
    return layout(workflow)


def build_observer():
    workflow = base("VozDoCliente - Observabilidade Router DEV")
    # Reutiliza transporte, IF e confirmacao de entrega ja testados na retencao.
    retained = {item["name"]: item for item in retention()["nodes"]}
    workflow["nodes"] = [node("Receber evento Router DEV", "executeWorkflowTrigger", 1, {}),
        code("Observabilidade DEV", (SOURCE / "router-alert.js").read_text(encoding="utf-8"))]
    for name in ("Alertar falha DEV?", "Slack DEV falha", "Resultado observabilidade"):
        item = copy.deepcopy(retained[name])
        item["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "vozdocliente/router-observer/" + name))
        workflow["nodes"].append(item)
    link(workflow, "Receber evento Router DEV", "Observabilidade DEV")
    link(workflow, "Observabilidade DEV", "Alertar falha DEV?")
    link(workflow, "Alertar falha DEV?", "Slack DEV falha", "Resultado observabilidade")
    link(workflow, "Slack DEV falha", "Resultado observabilidade")
    return layout(workflow)


def build_error():
    workflow = base("VozDoCliente - Erros Router DEV")
    workflow["nodes"] = [node("Erro Router DEV", "errorTrigger", 1, {}),
        code("Normalizar erro Router DEV", (SOURCE / "router-error.js").read_text(encoding="utf-8"))]
    link(workflow, "Erro Router DEV", "Normalizar erro Router DEV")
    delivery(workflow, ["Normalizar erro Router DEV"])
    return layout(workflow)


def exports():
    return [("vozdocliente-router-v4-observavel-dev.json", build_router()),
            ("vozdocliente-observabilidade-router-dev.json", build_observer()),
            ("vozdocliente-erros-router-dev.json", build_error())]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for filename, workflow in exports():
        output = OUTPUT / filename
        expected = json.dumps(workflow, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if output.read_text(encoding="utf-8") != expected:
                raise SystemExit("Export de observabilidade desatualizado: " + filename)
        else:
            output.write_text(expected, encoding="utf-8", newline="\n")
        print("[OK] " + filename + (" sincronizado" if args.check else " gerado inativo e sem credenciais"))
