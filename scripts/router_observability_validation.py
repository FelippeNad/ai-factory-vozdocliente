"""Invariantes do grafo observado; independe de n8n/API e nao altera exports."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edges(workflow):
    for source, value in workflow.get('connections', {}).items():
        for branches in value.values():
            for branch in branches:
                for target in branch:
                    yield source, target['node']


def reachable(workflow, source, target, blocked=None):
    graph = {}
    for start, end in edges(workflow):
        graph.setdefault(start, []).append(end)
    todo, seen = [source], set()
    while todo:
        current = todo.pop()
        if current == blocked or current in seen:
            continue
        if current == target:
            return True
        seen.add(current)
        todo.extend(graph.get(current, []))
    return False


def structure_errors(workflow, role):
    errors = []
    nodes = {node['name']: node for node in workflow['nodes']}
    if len(nodes) != len(workflow['nodes']) or any(a not in nodes or b not in nodes for a, b in edges(workflow)):
        errors.append('referencia/nomes de nodes invalidos')
    if workflow.get('active') is not False or workflow.get('pinData'):
        errors.append('export precisa estar inativo e sem pinData')
    settings = {'saveDataErrorExecution': 'none', 'saveDataSuccessExecution': 'none',
                'saveManualExecutions': False, 'saveExecutionProgress': False}
    if any(workflow.get('settings', {}).get(k) != v for k, v in settings.items()) or workflow.get('settings', {}).get('errorWorkflow'):
        errors.append('historico/ligacao local de Error Workflow nao deve ser exportado')
    for item in nodes.values():
        if item.get('credentials') or item.get('disabled') or item.get('continueOnFail'):
            errors.append('credenciais/bypass proibidos no export')
        if '$env.AIRTABLE_BASE_ID' in json.dumps(item.get('parameters', {})):
            errors.append('fallback PROD proibido')
    if role == 'router':
        baseline = json.loads((ROOT / 'n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json').read_text(encoding='utf-8'))
        for item in baseline['nodes']:
            if item['name'] not in nodes:
                errors.append('node original ausente: ' + item['name'])
            elif item['name'] != 'Webhook Review' and nodes[item['name']]['parameters'] != item['parameters']:
                errors.append('parametros funcionais modificados: ' + item['name'])
        barriers = ('Recebimento observado DEV', 'Sanitizar PII', 'Preparar deduplicacao DEV',
                    'Airtable Precheck DEV', 'Validar busca e restaurar texto', 'Ja existe? DEV', 'LLM iniciado DEV')
        for barrier in barriers:
            if barrier not in nodes or reachable(workflow, 'Webhook Review', 'LLM DEV', blocked=barrier):
                errors.append('bypass antes do LLM: ' + barrier)
        if not reachable(workflow, 'Webhook Review', 'LLM DEV'):
            errors.append('LLM desconectado')
        for barrier in ('Airtable Buscar review_id', 'Validar busca final DEV', 'Confirmar novo? DEV'):
            if reachable(workflow, 'Webhook Review', 'Airtable DEV', blocked=barrier):
                errors.append('bypass da deduplicacao final: ' + barrier)
        for source, success in (('Ja existe? DEV', 'LLM iniciado DEV'), ('Confirmar novo? DEV', 'Persistencia iniciada DEV')):
            branches = workflow['connections'].get(source, {}).get('main', [])
            if len(branches) != 2 or branches[1] != [{'node': success, 'type': 'main', 'index': 0}]:
                errors.append('ramo false de deduplicacao invalido')
            elif any(reachable(workflow, target['node'], destination) for target in branches[0] for destination in ('LLM DEV', 'Airtable DEV')):
                errors.append('duplicata alcanca negocio')
        operational = ('Sanitizar PII', 'Preparar deduplicacao DEV', 'Airtable Precheck DEV', 'Validar busca e restaurar texto',
                       'LLM DEV', 'Parse + Merge', 'Airtable Buscar review_id', 'Validar busca final DEV', 'Airtable DEV', 'Slack DEV')
        for name in operational:
            item = nodes.get(name, {})
            failure = 'Falha segura: ' + name
            branches = workflow['connections'].get(name, {}).get('main', [])
            if (item.get('onError') != 'continueErrorOutput' or item.get('retryOnFail', False)
                    or len(branches) != 2 or branches[1] != [{'node': failure, 'type': 'main', 'index': 0}]):
                errors.append('captura de erro obrigatoria: ' + name)
            if not reachable(workflow, failure, 'Interromper com seguranca'):
                errors.append('falha nao interrompe: ' + name)
            if any(reachable(workflow, failure, target) for target in ('LLM DEV', 'Airtable DEV', 'Slack DEV')):
                errors.append('ramo de erro libera negocio: ' + name)
        if nodes.get('Interromper com seguranca', {}).get('type') != 'n8n-nodes-base.stopAndError':
            errors.append('parada segura ausente')
        stop_gate = nodes.get('Falhou Router DEV?', {}).get('parameters', {}).get('conditions', {}).get('conditions', [])
        if (stop_gate != [{'id': 'decision', 'leftValue': "={{ $json.report.status === 'failure' }}", 'rightValue': True,
                          'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}]
                or workflow['connections'].get('Falhou Router DEV?', {}).get('main') != [
                    [{'node': 'Interromper com seguranca', 'type': 'main', 'index': 0}], []]):
            errors.append('gate de parada precisa interromper todo resultado de falha')
        if nodes.get('Webhook Review', {}).get('parameters', {}).get('path') != 'review-v4-observavel-dev':
            errors.append('webhook exclusivo obrigatorio')
        for name in operational:
            if nodes.get(name, {}).get('type') == 'n8n-nodes-base.httpRequest':
                opts = nodes[name]['parameters'].get('options', {})
                if (nodes[name].get('retryOnFail') is not False or opts.get('timeout') != 15000
                        or opts.get('redirect', {}).get('redirect', {}).get('followRedirects') is not False):
                    errors.append('politica HTTP alterada')
    elif role == 'observer':
        if nodes.get('Receber evento Router DEV', {}).get('type') != 'n8n-nodes-base.executeWorkflowTrigger':
            errors.append('entrada deve ser subworkflow, sem webhook publico')
        transport = nodes.get('Slack DEV falha', {})
        params = transport.get('parameters', {})
        if (params.get('url') != 'https://slack.com/api/chat.postMessage' or params.get('sendBody') is not True
                or params.get('contentType') != 'json' or params.get('specifyBody') != 'json'
                or transport.get('retryOnFail') is not False or transport.get('typeVersion') != 4.1):
            errors.append('transporte Slack inseguro/incompativel')
        if reachable(workflow, 'Receber evento Router DEV', 'Slack DEV falha', blocked='Observabilidade DEV'):
            errors.append('bypass da allowlist DEV')
        if reachable(workflow, 'Receber evento Router DEV', 'Slack DEV falha', blocked='Alertar falha DEV?'):
            errors.append('bypass da condicao de alerta')
    elif role == 'error':
        if nodes.get('Erro Router DEV', {}).get('type') != 'n8n-nodes-base.errorTrigger':
            errors.append('Error Trigger ausente')
        if any(item['type'] == 'n8n-nodes-base.httpRequest' for item in nodes.values()):
            errors.append('Error Workflow nao deve duplicar transporte')
    else:
        errors.append('papel invalido')
    # Os Code nodes de observabilidade sao gerados de fontes compartilhadas.
    # A verificacao de sincronizacao --check cobre os trechos compilados completos.
    return errors
