"""Gera somente copias DEV de benchmark; nenhum workflow atual ou servico e alterado."""
import argparse
import copy
import json
from pathlib import Path
import uuid

from build_router_observability import common, link, node

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'n8n-mirror/benchmarks'
CURRENT = ROOT / 'n8n-mirror/workflows/vozdocliente-router-v4-observavel-dev.json'
CASES = json.loads((SOURCE / 'cases.json').read_text(encoding='utf-8'))


def build(variant):
    if variant not in ('before', 'after'):
        raise ValueError('Variante invalida')
    workflow = json.loads(CURRENT.read_text(encoding='utf-8'))
    workflow['name'] = 'VozDoCliente - Benchmark ' + variant + ' DEV'
    nodes = {n['name']: n for n in workflow['nodes']}
    webhook = nodes['Webhook Review']
    webhook['parameters'].update(path='benchmark-router-' + variant + '-dev', responseMode='responseNode')
    webhook['webhookId'] = 'vozdocliente-benchmark-' + variant + '-dev'
    if variant == 'before':
        # Reconstroi a ordem da v4 anterior, preservando os controles DEV atuais.
        removed = {'Precheck iniciado DEV', 'Airtable Precheck DEV', 'Validar busca e restaurar texto',
                   'Precheck observado DEV', 'Ja existe? DEV', 'Duplicata precheck DEV',
                   'Falha segura: Airtable Precheck DEV', 'Falha segura: Validar busca e restaurar texto'}
        workflow['nodes'] = [n for n in workflow['nodes'] if n['name'] not in removed]
        workflow['connections'] = {name: value for name, value in workflow['connections'].items() if name not in removed}
        # Preserva a saida de erro de preparacao/configuracao antes do LLM.
        workflow['connections']['Preparar deduplicacao DEV']['main'][0] = [
            {'node': 'LLM iniciado DEV', 'type': 'main', 'index': 0}]
        nodes['LLM iniciado DEV']['parameters']['jsCode'] = common() + "return obsStep('llm', 'started', 'Sanitizacao observada DEV');"
    prefix = 'const BENCH_VARIANT = ' + json.dumps(variant) + ';\n'
    guard = node('Validar benchmark DEV', 'code', 2, {'mode': 'runOnceForAllItems', 'language': 'javaScript',
        'jsCode': prefix + 'const BENCH_CASES = ' + json.dumps(CASES, ensure_ascii=False) + ';\n'
                  + (SOURCE / 'guard.js').read_text(encoding='utf-8')}, onError='stopWorkflow')
    packet = node('Coletar benchmark DEV', 'code', 2, {'mode': 'runOnceForAllItems', 'language': 'javaScript',
        'jsCode': common() + prefix + (SOURCE / 'packet.js').read_text(encoding='utf-8')}, onError='stopWorkflow')
    workflow['nodes'] += [guard, packet]
    for name in ('Responder benchmark DEV', 'Responder falha benchmark DEV'):
        workflow['nodes'].append(node(name, 'respondToWebhook', 1.4,
            {'respondWith': 'json', 'responseBody': '={{ $json }}', 'options': {'responseCode': 200}}, onError='stopWorkflow'))
    link(workflow, 'Webhook Review', 'Validar benchmark DEV')
    link(workflow, 'Validar benchmark DEV', 'Recebimento observado DEV')
    link(workflow, 'Resultado Router DEV', 'Coletar benchmark DEV')
    link(workflow, 'Coletar benchmark DEV', 'Falhou Router DEV?')
    link(workflow, 'Falhou Router DEV?', 'Responder falha benchmark DEV', 'Responder benchmark DEV')
    link(workflow, 'Responder falha benchmark DEV', 'Interromper com seguranca')
    for index, item in enumerate(workflow['nodes']):
        item['id'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'vozdocliente/benchmark/' + variant + '/' + item['name']))
        item['position'] = [(index % 8) * 260, (index // 8) * 260]
    return copy.deepcopy(workflow)


def exports():
    return [(SOURCE / ('router-' + v + '-benchmark-dev.json'), build(v)) for v in ('before', 'after')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for path, workflow in exports():
        expected = json.dumps(workflow, ensure_ascii=False, indent=2) + '\n'
        if args.check:
            if path.read_text(encoding='utf-8') != expected:
                raise SystemExit('Copia de benchmark desatualizada: ' + path.name)
        else:
            path.write_text(expected, encoding='utf-8', newline='\n')
        print('[OK] ' + path.name + (' sincronizado' if args.check else ' preparado inativo, sem credenciais'))


if __name__ == '__main__':
    main()
