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
N8N_PATHS.append(os.path.join(ROOT, "n8n-mirror", "workflows", "vozdocliente-router-v4-otimizado-dev.json"))
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


def optimized_structure_errors(wf):
    errors = []
    nodes = {node["name"]: node for node in wf["nodes"]}
    barriers = ("Sanitizar PII", "Preparar deduplicacao DEV", "Airtable Precheck DEV",
                "Validar busca e restaurar texto", "Ja existe? DEV")
    if not set(barriers + ("Webhook Review", "LLM DEV", "Parse + Merge", "Airtable DEV", "Slack DEV",
                           "Airtable Buscar review_id", "Validar busca final DEV", "Confirmar novo? DEV")) <= nodes.keys():
        return ["nodes da variante DEV ausentes"]
    with open(N8N_PATHS[1], encoding="utf-8") as stream:
        original = {node["name"]: node for node in json.load(stream)["nodes"]}
    if (nodes["Sanitizar PII"]["parameters"] != original["Sanitizar PII"]["parameters"]
            or nodes["Parse + Merge"]["parameters"] != original["Parse + Merge"]["parameters"]
            or nodes["LLM DEV"]["parameters"]["jsonBody"] != original["LLM PROD"]["parameters"]["jsonBody"]):
        errors.append("sanitizador, prompt/schema e parser devem permanecer identicos a v4")
    if not reachable(wf, "Webhook Review", "LLM DEV"):
        errors.append("LLM DEV desconectado")
    for barrier in barriers:
        if reachable(wf, "Webhook Review", "LLM DEV", blocked=barrier):
            errors.append("bypass da barreira: " + barrier)
    if {src for src, dst in edges(wf) if dst == "LLM DEV"} != {"Ja existe? DEV"}:
        errors.append("origem inesperada no LLM DEV")
    expected_gate = {"main": [[], [{"node": "LLM DEV", "type": "main", "index": 0}]]}
    if wf.get("connections", {}).get("Ja existe? DEV") != expected_gate:
        errors.append("duplicata nao pode chegar ao LLM")
    for barrier in ("Airtable Buscar review_id", "Validar busca final DEV", "Confirmar novo? DEV"):
        if reachable(wf, "Webhook Review", "Airtable DEV", blocked=barrier):
            errors.append("checagem final de duplicatas ausente: " + barrier)
    if wf.get("connections", {}).get("Confirmar novo? DEV") != {
        "main": [[], [{"node": "Airtable DEV", "type": "main", "index": 0}]]}:
        errors.append("duplicata da checagem final nao pode ser gravada")
    if nodes["Ja existe? DEV"]["parameters"]["conditions"]["conditions"] != [{
        "id": "already-exists", "leftValue": "={{ $json.duplicate }}", "rightValue": True,
        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
    }]:
        errors.append("condicao de deduplicacao invalida")
    for name, source in [("Preparar deduplicacao DEV", "prepare-dedup.js"),
                         ("Validar busca e restaurar texto", "validate-lookup.js"),
                         ("Validar busca final DEV", "validate-lookup.js")]:
        with open(os.path.join(ROOT, "n8n-mirror", "router-dev", source), encoding="utf-8") as stream:
            if nodes[name]["parameters"].get("jsCode") != stream.read():
                errors.append("codigo DEV nao corresponde a fonte: " + name)
    expected_settings = {"saveDataErrorExecution": "none", "saveDataSuccessExecution": "none",
                         "saveManualExecutions": False, "saveExecutionProgress": False}
    if (wf.get("active") is not False or wf.get("pinData")
            or any(wf.get("settings", {}).get(key) != value for key, value in expected_settings.items())):
        errors.append("DEV deve estar inativo, sem pinData e sem salvar payloads")
    if nodes["Webhook Review"]["parameters"].get("path") != "review-v4-otimizado-dev":
        errors.append("webhook DEV precisa de caminho proprio")
    for node in wf["nodes"]:
        if (node.get("credentials") or node.get("disabled") or node.get("continueOnFail")
                or node.get("onError", "stopWorkflow") != "stopWorkflow"):
            errors.append("DEV deve estar sem credenciais e falhar fechado")
        if "$env.AIRTABLE_BASE_ID" in json.dumps(node.get("parameters", {})):
            errors.append("fallback para base publicada proibido")
        if node["type"] == "n8n-nodes-base.httpRequest":
            opts = node["parameters"].get("options", {})
            if (node.get("retryOnFail") is not False or opts.get("timeout") != 15000
                    or opts.get("redirect", {}).get("redirect", {}).get("followRedirects") is not False):
                errors.append("HTTP DEV exige timeout, sem retry/redirect")
    for name, url in (("Airtable Precheck DEV", "={{ $json.lookup_url }}"),
                      ("Airtable Buscar review_id", "={{ $('Preparar deduplicacao DEV').item.json.lookup_url }}")):
        lookup = nodes[name]["parameters"]
        fields = lookup.get("queryParameters", {}).get("parameters", [])
        if (lookup.get("url") != url or lookup.get("method") != "GET"
                or {"name": "fields[]", "value": "review_id"} not in fields
                or {"name": "maxRecords", "value": "1"} not in fields
                or lookup.get("options", {}).get("response", {}).get("response", {}).get("fullResponse") is not True):
            errors.append("consulta DEV deve ser minima e validavel")
    if nodes["Airtable DEV"]["parameters"].get("url") != "={{ $('Preparar deduplicacao DEV').item.json.lookup_url }}":
        errors.append("escrita deve usar a mesma tabela DEV validada")
    if "$env.CLASSIFIER_SLACK_DEV_CHANNEL_ID" not in nodes["Slack DEV"]["parameters"].get("jsonBody", ""):
        errors.append("Slack deve usar canal DEV explicito")
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
    elif workflow_path.endswith("otimizado-dev.json"):
        errors = optimized_structure_errors(wf)
        check("v4 DEV otimizado: dedup antes do LLM, PII preservada e isolamento DEV"
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
    expected_http = 0 if demo else 3
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
        for name, send_body in (("Airtable DEV operacao", True), ("Airtable DEV sem body", False)):
            for barrier in ("Motor de retencao", "Validar operacao DEV", "Ha operacao segura?", "Operacao com body?"):
                if reachable(wf, "Agenda de retencao", name, blocked=barrier):
                    errors.append("bypass de barreira de retencao: " + barrier + " -> " + name)
            http = nodes.get(name, {})
            parameters = http.get("parameters", {})
            options = parameters.get("options", {})
            if http.get("type") != "n8n-nodes-base.httpRequest" or http.get("typeVersion") != 4.1:
                errors.append("transporte deve usar HTTP Request 4.1: " + name)
            if parameters.get("sendBody") is not send_body:
                errors.append("HTTP exige sendBody booleano literal no transporte: " + name)
            if send_body:
                if parameters.get("contentType") != "json" or parameters.get("specifyBody") != "json":
                    errors.append("HTTP deve configurar envio de body JSON explicitamente")
                if parameters.get("jsonBody") != "={{ JSON.stringify($json.request.body) }}":
                    errors.append("HTTP deve serializar request.body completo, incluindo fields")
            elif any(key in parameters for key in ("jsonBody", "body", "bodyParameters")):
                errors.append("transporte GET/DELETE nao deve configurar payload")
            if http.get("retryOnFail") is not False or http.get("onError") != "continueRegularOutput":
                errors.append("HTTP deve encaminhar falha para metricas sem repeticao automatica")
            if options.get("redirect", {}).get("redirect", {}).get("followRedirects") is not False:
                errors.append("redirecionamentos HTTP devem estar desabilitados")
        slack = nodes.get("Slack DEV falha", {})
        params = slack.get("parameters", {})
        if (slack.get("type") != "n8n-nodes-base.httpRequest" or slack.get("typeVersion") != 4.1
                or params.get("method") != "POST" or params.get("url") != "https://slack.com/api/chat.postMessage"
                or params.get("sendBody") is not True or params.get("contentType") != "json"
                or params.get("specifyBody") != "json" or params.get("jsonBody") != "={{ JSON.stringify($json.slack_body) }}"):
            errors.append("Slack DEV exige endpoint fixo e somente payload permitido")
        options = params.get("options", {})
        if (slack.get("retryOnFail") is not False or slack.get("onError") != "continueRegularOutput"
                or options.get("redirect", {}).get("redirect", {}).get("followRedirects") is not False
                or options.get("timeout") != 5000):
            errors.append("Slack DEV exige falha tratada, timeout e nenhum retry/redirect")
        for barrier in ("Resumo sem PII", "Observabilidade DEV", "Alertar falha DEV?"):
            if reachable(wf, "Agenda de retencao", "Slack DEV falha", blocked=barrier):
                errors.append("bypass do alerta DEV: " + barrier)
    alert_conditions = nodes.get("Alertar falha DEV?", {}).get("parameters", {}).get("conditions", {})
    if nodes.get("Alertar falha DEV?", {}).get("type") != "n8n-nodes-base.if" or alert_conditions.get("conditions") != [{
        "id": "alert", "leftValue": "={{ $json.send_alert }}", "rightValue": True,
        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
    }] or alert_conditions.get("options", {}).get("typeValidation") != "strict":
        errors.append("alerta deve respeitar decisao DEV da observabilidade")
    router = nodes.get("Operacao com body?", {})
    conditions = router.get("parameters", {}).get("conditions", {})
    if router.get("type") != "n8n-nodes-base.if" or conditions.get("conditions") != [{
        "id": "has-body", "leftValue": "={{ $json.request.body !== undefined }}", "rightValue": True,
        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
    }] or conditions.get("options", {}).get("typeValidation") != "strict":
        errors.append("selecao de transporte deve testar presenca de request.body em IF")
    for source, targets in {
        "Ha operacao segura?": ["Operacao com body?", "Resumo sem PII"],
        "Operacao com body?": ["Airtable DEV operacao", "Airtable DEV sem body"],
        "Airtable DEV operacao": ["Receber resposta"],
        "Airtable DEV sem body": ["Receber resposta"],
        "Resumo sem PII": ["Observabilidade DEV"],
        "Observabilidade DEV": ["Alertar falha DEV?"],
        "Alertar falha DEV?": ["Slack DEV falha", "Resultado observabilidade"],
        "Slack DEV falha": ["Resultado observabilidade"],
    }.items():
        expected = [[{"node": target, "type": "main", "index": 0}] for target in targets]
        if wf.get("connections", {}).get(source, {}).get("main") != expected:
            errors.append("roteamento incorreto do transporte: " + source)
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
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from router_observability_validation import structure_errors
        for filename, role in [('vozdocliente-router-v4-observavel-dev.json', 'router'),
                               ('vozdocliente-observabilidade-router-dev.json', 'observer'),
                               ('vozdocliente-erros-router-dev.json', 'error')]:
            with open(os.path.join(ROOT, 'n8n-mirror', 'workflows', filename), encoding='utf-8') as stream:
                errors = structure_errors(json.load(stream), role)
            check('observabilidade Router: ' + role + (f' ({errors})' if errors else ''), not errors)
    except Exception as exc:  # pragma: no cover
        print(f"\n[ERRO FATAL] {type(exc).__name__}: {exc}")
        sys.exit(2)

    print("\n" + "-" * 48)
    if failures:
        print(f"RESULTADO: {len(failures)} verificacao(oes) FALHARAM")
        sys.exit(1)
    print("RESULTADO: todas as verificacoes passaram")
    sys.exit(0)
