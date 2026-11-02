#!/usr/bin/env python3
"""
Validador estrutural do Make e dos workflows n8n v3/v4.

NAO chama API nenhuma e NAO sobe o n8n. So carrega os JSONs e checa estrutura:
  - Make blueprint: tem `name` + `flow[]` com >= 5 modulos (contando rotas aninhadas)
  - n8n mirror:    tem `nodes[]` + `connections{}` com >= 5 nodes e refs de conexao validas

Uso:  python tests/validate_workflows.py
Saida: linhas [OK]/[FALHA] e exit code 0 (tudo passou) ou 1 (alguma falha).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_PATH = os.path.join(ROOT, "workflows", "vozdocliente-make-blueprint.json")
N8N_PATHS = [os.path.join(ROOT, "n8n-mirror", "workflows", f"vozdocliente-router-v{version}.json")
             for version in (3, 4)]
RETENTION_PATHS = [os.path.join(ROOT, "n8n-mirror", "workflows", filename) for filename in
                   ("vozdocliente-retencao-v1.json", "vozdocliente-retencao-demo.json")]

failures = []


def check(label, condition):
    status = "OK" if condition else "FALHA"
    print(f"[{status}] {label}")
    if not condition:
        failures.append(label)
    return condition


def count_make_modules(flow):
    """Conta modulos no flow do Make, descendo em routes[].flow[]."""
    total = 0
    for module in flow:
        total += 1
        for route in module.get("routes", []) or []:
            total += count_make_modules(route.get("flow", []))
    return total


def validate_make():
    print("\n=== Make.com blueprint ===")
    with open(MAKE_PATH, encoding="utf-8") as f:
        bp = json.load(f)
    check("Make: JSON parseia", True)
    check("Make: tem campo 'name'", bool(bp.get("name")))
    flow = bp.get("flow")
    check("Make: 'flow' e uma lista", isinstance(flow, list))
    n = count_make_modules(flow or [])
    check(f"Make: flow tem >= 5 modulos (encontrados: {n})", n >= 5)
    check("Make: tem bloco 'metadata'", isinstance(bp.get("metadata"), dict))
    # checa que existe um modulo webhook e um de slack em algum nivel
    flat = json.dumps(bp)
    check("Make: tem trigger webhook (gateway:CustomWebHook)", "gateway:CustomWebHook" in flat)
    check("Make: tem modulo Slack (slack:CreateMessage)", "slack:CreateMessage" in flat)
    check("Make: tem modulo Airtable", "airtable" in flat.lower())


def edges(wf):
    """Considera todos os tipos e ramos de conexao, inclusive rotas de erro."""
    for src, payload in wf.get("connections", {}).items():
        for branches in payload.values():
            for branch in branches:
                for link in branch:
                    yield src, link["node"]


def reachable(wf, start, target, blocked=None):
    graph = {}
    for src, dst in edges(wf):
        graph.setdefault(src, []).append(dst)
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == blocked or node in seen:
            continue
        if node == target:
            return True
        seen.add(node)
        pending.extend(graph.get(node, []))
    return False


def pii_structure_errors(wf):
    """Invariantes da v4; retorna erros para permitir testes de mutacao do grafo."""
    errors = []
    nodes = {node["name"]: node for node in wf["nodes"]}
    required = {"Webhook Review", "Sanitizar PII", "LLM PROD"}
    if not required <= nodes.keys():
        return ["nodes obrigatorios de PII ausentes"]
    sanitizer = nodes["Sanitizar PII"]
    llm = nodes["LLM PROD"]
    if sanitizer["type"] != "n8n-nodes-base.code" or sanitizer["typeVersion"] != 2:
        errors.append("sanitizador deve usar Code v2")
    if sanitizer["parameters"].get("mode") != "runOnceForAllItems":
        errors.append("modo do sanitizador invalido")
    all_edges = set(edges(wf))
    if ("Webhook Review", "Sanitizar PII") not in all_edges or ("Sanitizar PII", "LLM PROD") not in all_edges:
        errors.append("sequencia Webhook -> Sanitizar PII -> LLM ausente")
    if not reachable(wf, "Webhook Review", "LLM PROD"):
        errors.append("LLM nao e alcancavel pelo webhook")
    if reachable(wf, "Webhook Review", "LLM PROD", blocked="Sanitizar PII"):
        errors.append("caminho do webhook ao LLM sem sanitizacao")
    if {src for src, dst in all_edges if dst == "LLM PROD"} != {"Sanitizar PII"}:
        errors.append("LLM recebe conexoes de outra origem")
    # Expressao permitida exata: nao aceita fallback, metadados ou referencia ao webhook.
    content = "{{ JSON.stringify((() => { const text = $json.review_text_sanitized; if (typeof text !== 'string' || !text.trim()) { throw new Error('Texto sanitizado ausente ou invalido.'); } return text; })()) }}"
    llm_body = llm["parameters"].get("jsonBody", "")
    placeholder = '"__SANITIZED_CONTENT__"'
    if llm_body.count(content) != 1:
        errors.append("LLM deve usar exclusivamente o campo sanitizado com guarda obrigatoria")
    else:
        try:
            request = json.loads(llm_body[1:].replace(content, placeholder))
            if (request["messages"][1] != {"role": "user", "content": "__SANITIZED_CONTENT__"}
                    or len(request["messages"]) != 2 or "{{" in json.dumps(request)):
                errors.append("conteudo dinamico extra no request do LLM")
        except (ValueError, KeyError, IndexError, TypeError):
            errors.append("body do LLM invalido")
    for name in required:
        node = nodes[name]
        if node.get("disabled") or node.get("continueOnFail") or node.get("onError", "stopWorkflow") != "stopWorkflow":
            errors.append(f"{name} deve estar habilitado e interromper em caso de erro")
    expected_settings = {"saveDataErrorExecution": "none", "saveDataSuccessExecution": "none",
                         "saveManualExecutions": False, "saveExecutionProgress": False}
    if any(wf.get("settings", {}).get(key) != value for key, value in expected_settings.items()):
        errors.append("retencao de execucoes deve estar desabilitada na v4")
    if wf.get("pinData") or wf.get("active") is not False:
        errors.append("v4 deve estar inativa e sem dados fixados")
    return errors


def validate_n8n(workflow_path):
    print(f"\n=== n8n mirror: {os.path.basename(workflow_path)} ===")
    with open(workflow_path, encoding="utf-8") as f:
        wf = json.load(f)
    check("n8n: JSON parseia", True)
    nodes = wf.get("nodes")
    conns = wf.get("connections")
    check("n8n: 'nodes' e uma lista", isinstance(nodes, list))
    check("n8n: 'connections' e um dict", isinstance(conns, dict))
    check(f"n8n: tem >= 5 nodes (encontrados: {len(nodes or [])})", len(nodes or []) >= 5)

    node_names = {nd.get("name") for nd in (nodes or [])}
    check("n8n: nomes e ids de nodes unicos", len(node_names) == len(nodes)
          and len({nd["id"] for nd in nodes}) == len(nodes))
    # toda origem e todo destino referenciado em connections deve existir em nodes
    ref_ok = True
    bad_refs = []
    for src, tgt in edges(wf):
        if src not in node_names:
            ref_ok = False
            bad_refs.append(f"origem '{src}'")
        if tgt not in node_names:
            ref_ok = False
            bad_refs.append(f"destino '{tgt}'")
    check(
        "n8n: todas as conexoes referenciam nodes existentes"
        + (f" (invalidos: {bad_refs})" if bad_refs else ""),
        ref_ok,
    )
    # tipos chave presentes
    types = {nd.get("type") for nd in (nodes or [])}
    check("n8n: tem node webhook", "n8n-nodes-base.webhook" in types)
    check("n8n: tem node IF (roteamento do negativo)", "n8n-nodes-base.if" in types)
    # webhook deve ser ponto de entrada (origem de conexao)
    check("n8n: 'Webhook Review' inicia o fluxo", "Webhook Review" in conns)
    if workflow_path.endswith("v4.json"):
        errors = pii_structure_errors(wf)
        check("n8n v4: sanitizacao obrigatoria, LLM sem fallback e retencao minima"
              + (f" ({errors})" if errors else ""), not errors)


def retention_structure_errors(wf, demo=False):
    errors = []
    nodes = {node["name"]: node for node in wf["nodes"]}
    if len(nodes) != len(wf["nodes"]):
        errors.append("nomes de nodes repetidos")
    if wf.get("active") is not False or wf.get("pinData"):
        errors.append("retencao deve permanecer inativa e sem dados fixados")
    types = [node["type"] for node in wf["nodes"]]
    if types.count("n8n-nodes-base.scheduleTrigger") != 1 or "n8n-nodes-base.webhook" in types:
        errors.append("retencao exige agenda independente e nenhum webhook")
    expected_http = 0 if demo else 1
    if types.count("n8n-nodes-base.httpRequest") != expected_http:
        errors.append("quantidade inesperada de transportes HTTP")
    if any(node.get("disabled") or node.get("credentials") for node in wf["nodes"]):
        errors.append("exportacao deve estar sem credenciais e sem nodes desabilitados")
    if wf.get("settings", {}).get("timezone") != "America/Sao_Paulo":
        errors.append("fuso da agenda ausente")
    expected_settings = {"saveDataErrorExecution": "none", "saveDataSuccessExecution": "none",
                         "saveManualExecutions": False, "saveExecutionProgress": False}
    if any(wf.get("settings", {}).get(key) != value for key, value in expected_settings.items()):
        errors.append("historico de payloads deve estar desabilitado")
    if not demo:
        for barrier in ("Motor de retencao", "Validar operacao DEV", "Ha operacao segura?"):
            if reachable(wf, "Agenda de retencao", "Airtable DEV operacao", blocked=barrier):
                errors.append("bypass de barreira de retencao: " + barrier)
        http = nodes.get("Airtable DEV operacao", {})
        options = http.get("parameters", {}).get("options", {})
        if http.get("retryOnFail") is not False or http.get("onError") != "continueRegularOutput":
            errors.append("HTTP deve encaminhar falha para metricas sem repeticao automatica")
        if options.get("redirect", {}).get("redirect", {}).get("followRedirects") is not False:
            errors.append("redirecionamentos HTTP devem estar desabilitados")
    refs = all(src in nodes and dst in nodes for src, dst in edges(wf))
    if not refs:
        errors.append("conexao para node inexistente")
    return errors


def validate_retention(workflow_path):
    print(f"\n=== retencao: {os.path.basename(workflow_path)} ===")
    with open(workflow_path, encoding="utf-8") as stream:
        wf = json.load(stream)
    errors = retention_structure_errors(wf, demo=workflow_path.endswith("demo.json"))
    check("retencao: agenda, barreiras DEV, transporte e nao retencao de payloads"
          + (f" ({errors})" if errors else ""), not errors)


if __name__ == "__main__":
    try:
        validate_make()
        for workflow_path in N8N_PATHS:
            validate_n8n(workflow_path)
        for workflow_path in RETENTION_PATHS:
            validate_retention(workflow_path)
    except Exception as exc:  # pragma: no cover
        print(f"\n[ERRO FATAL] {type(exc).__name__}: {exc}")
        sys.exit(2)

    print("\n" + "-" * 48)
    if failures:
        print(f"RESULTADO: {len(failures)} verificacao(oes) FALHARAM")
        sys.exit(1)
    print("RESULTADO: todas as verificacoes passaram")
    sys.exit(0)
