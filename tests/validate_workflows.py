#!/usr/bin/env python3
"""
Validador estrutural dos dois workflows do VozDoCliente Review Router.

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
N8N_PATH = os.path.join(ROOT, "n8n-mirror", "workflows", "vozdocliente-router-v3.json")

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


def validate_n8n():
    print("\n=== n8n mirror ===")
    with open(N8N_PATH, encoding="utf-8") as f:
        wf = json.load(f)
    check("n8n: JSON parseia", True)
    nodes = wf.get("nodes")
    conns = wf.get("connections")
    check("n8n: 'nodes' e uma lista", isinstance(nodes, list))
    check("n8n: 'connections' e um dict", isinstance(conns, dict))
    check(f"n8n: tem >= 5 nodes (encontrados: {len(nodes or [])})", len(nodes or []) >= 5)

    node_names = {nd.get("name") for nd in (nodes or [])}
    # toda origem e todo destino referenciado em connections deve existir em nodes
    ref_ok = True
    bad_refs = []
    for src, payload in conns.items():
        if src not in node_names:
            ref_ok = False
            bad_refs.append(f"origem '{src}'")
        for branch in payload.get("main", []):
            for link in branch:
                tgt = link.get("node")
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


if __name__ == "__main__":
    try:
        validate_make()
        validate_n8n()
    except Exception as exc:  # pragma: no cover
        print(f"\n[ERRO FATAL] {type(exc).__name__}: {exc}")
        sys.exit(2)

    print("\n" + "-" * 48)
    if failures:
        print(f"RESULTADO: {len(failures)} verificacao(oes) FALHARAM")
        sys.exit(1)
    print("RESULTADO: todas as verificacoes passaram")
    sys.exit(0)
