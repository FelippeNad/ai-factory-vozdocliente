"""prepare/report sao offline; run exige opt-in explicito e acessa somente n8n loopback DEV."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

from build_router_benchmark import CASES, CURRENT, build
from router_observability_report import canonical, percentile

VARIANTS = ('before', 'after')
PLAN_SCHEMA = 'vozdocliente.router.real-benchmark.plan.v1'
PACKET_SCHEMA = 'vozdocliente.router.real-benchmark.packet.v1'
PACKET_KEYS = {'schema', 'benchmark_id', 'variant', 'sequence', 'case_id', 'report', 'delivery_status',
               'airtable_queries_attempted', 'persisted_classification', 'configuration'}
RECORD_KEYS = PACKET_KEYS - {'configuration'} | {'configuration_sha256', 'completion_status'}
CONFIG_KEYS = {'environment', 'dev_base_id', 'dev_table_id', 'slack_channel_id', 'observer_id', 'input_price', 'output_price'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_json(path):
    def exact_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Chave JSON duplicada')
            value[key] = item
        return value
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('Limite excedido')
        return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=exact_keys)
    except (ValueError, OSError):
        raise ValueError('Arquivo JSON inacessivel, invalido ou acima de 10 MiB') from None


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def targets_valid(targets):
    patterns = {'dev_base_id': r'app[A-Za-z0-9]{14}', 'dev_table_id': r'tbl[A-Za-z0-9]{14}',
                'dev_slack_channel_id': r'[CG][A-Z0-9]{8,31}'}
    return (isinstance(targets, dict) and set(targets) == set(patterns)
            and all(isinstance(targets[k], str) and re.fullmatch(pattern, targets[k]) for k, pattern in patterns.items()))


def validate_plan(plan):
    keys = {'schema', 'scope', 'benchmark_id', 'prepared_at', 'order', 'targets', 'workflows', 'cases_sha256', 'current_router_sha256'}
    if (not isinstance(plan, dict) or set(plan) != keys or plan['schema'] != PLAN_SCHEMA
            or plan['scope'] != 'PREPARATION_ONLY_NO_MEASUREMENTS'
            or not isinstance(plan['benchmark_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', plan['benchmark_id'])
            or plan['order'] not in (['before', 'after'], ['after', 'before'])
            or not targets_valid(plan['targets']) or plan['cases_sha256'] != digest(CASES)
            or plan['workflows'] != {v: digest(build(v)) for v in VARIANTS}
            or plan['current_router_sha256'] != hashlib.sha256(CURRENT.read_bytes()).hexdigest()):
        raise ValueError('Plano invalido ou fontes alteradas; preparar novo lote')
    try:
        datetime.strptime(plan['prepared_at'], '%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError):
        raise ValueError('Data do plano invalida') from None
    return plan


def prepare(folder, targets, first='before'):
    if not targets_valid(targets) or first not in VARIANTS:
        raise ValueError('Confirmar identificadores DEV validos')
    folder.mkdir(exist_ok=False)
    plan = {'schema': PLAN_SCHEMA, 'scope': 'PREPARATION_ONLY_NO_MEASUREMENTS', 'benchmark_id': uuid.uuid4().hex,
            'prepared_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'order': [first, next(v for v in VARIANTS if v != first)], 'targets': targets,
            'workflows': {v: digest(build(v)) for v in VARIANTS}, 'cases_sha256': digest(CASES),
            'current_router_sha256': hashlib.sha256(CURRENT.read_bytes()).hexdigest()}
    for variant in VARIANTS:
        write_new(folder / ('router-' + variant + '-benchmark-dev.json'), build(variant))
    write_new(folder / 'plan.json', plan)
    return plan


def payload(plan, variant, sequence):
    sample = CASES[(sequence - 1) % 5]
    return {'review_id': 'BMR-' + plan['benchmark_id'] + '-' + variant + '-0' + str(sample['case_id']),
            'customer_name': 'BENCHMARK_SINTETICO', 'source': 'formulario', 'rating': sample['rating'],
            'review_text': sample['text'], 'benchmark_id': plan['benchmark_id'], 'benchmark_sequence': sequence,
            **plan['targets']}


def validate_packet(packet, plan, variant, sequence, record=False):
    invalid = lambda: ValueError('Pacote de benchmark invalido ou sem correlacao; conteudo descartado')
    if (not isinstance(packet, dict) or set(packet) != (RECORD_KEYS if record else PACKET_KEYS)
            or packet['schema'] != PACKET_SCHEMA or packet['benchmark_id'] != plan['benchmark_id']
            or packet['variant'] != variant or type(packet['sequence']) is not int or packet['sequence'] != sequence
            or type(packet['case_id']) is not int or packet['case_id'] != (sequence - 1) % 5 + 1):
        raise invalid()
    try:
        report = canonical(packet['report'])
    except (ValueError, KeyError, TypeError, OverflowError):
        raise invalid() from None
    if (report['source'] != 'n8n' or report['kind'] != 'run' or report['correlation'] != 'execution'
            or packet['delivery_status'] not in ('not_needed', 'disabled', 'sent', 'failed', 'blocked', 'not_configured', 'delivery_failed')):
        raise invalid()
    queries = packet['airtable_queries_attempted']
    if (not isinstance(queries, dict) or set(queries) != {'precheck', 'final'}
            or any(type(v) is not int or v not in (0, 1) for v in queries.values())
            or variant == 'before' and queries['precheck'] != 0):
        raise invalid()
    classification = packet['persisted_classification']
    if classification is not None:
        if (report['metrics']['persisted'] != 1 or not isinstance(classification, dict)
                or set(classification) != {'sentiment', 'theme'}
                or classification['sentiment'] not in ('positivo', 'neutro', 'negativo')
                or classification['theme'] not in ('entrega', 'produto', 'atendimento', 'preco', 'app_bug')):
            raise invalid()
    if record:
        if (not isinstance(packet['configuration_sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', packet['configuration_sha256'])
                or packet['completion_status'] != 'terminal_confirmed'):
            raise invalid()
    else:
        config = packet['configuration']
        if (not isinstance(config, dict) or set(config) != CONFIG_KEYS or config['environment'] != 'DEV'
                or config['dev_base_id'] != plan['targets']['dev_base_id']
                or config['dev_table_id'] != plan['targets']['dev_table_id']
                or config['slack_channel_id'] != plan['targets']['dev_slack_channel_id']
                or not isinstance(config['observer_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', config['observer_id'])
                or any(config[k] is not None and (type(config[k]) not in (int, float)
                       or not math.isfinite(config[k]) or not 0 < config[k] <= 1e6) for k in ('input_price', 'output_price'))):
            raise invalid()
    return packet


# Defaults comprovados no n8n 2.28.7. Nao generalizar para outros tipos/versoes.
N8N_2287_PARAMETER_DEFAULTS = {
    ('n8n-nodes-base.code', 2): {'mode': 'runOnceForAllItems', 'language': 'javaScript'},
    ('n8n-nodes-base.httpRequest', 4.4): {'method': 'GET'},
    ('n8n-nodes-base.executeWorkflow', 1): {'source': 'database', 'mode': 'once'},
    ('n8n-nodes-base.stopAndError', 1): {'errorType': 'errorMessage'},
}
BENCHMARK_STOP_NODES = {
    'Validar benchmark DEV': ('n8n-nodes-base.code', 2),
    'Coletar benchmark DEV': ('n8n-nodes-base.code', 2),
    'Responder benchmark DEV': ('n8n-nodes-base.respondToWebhook', 1.4),
    'Responder falha benchmark DEV': ('n8n-nodes-base.respondToWebhook', 1.4),
}


def normalized_benchmark_node(node):
    """Copia em memoria; preserva codigo, expressoes, valores explicitos e settings."""
    normalized = dict(node)
    node_type = (node.get('type'), node.get('typeVersion'))
    parameters = node.get('parameters')
    if isinstance(parameters, dict):
        normalized['parameters'] = dict(parameters)
        for key, value in N8N_2287_PARAMETER_DEFAULTS.get(node_type, {}).items():
            normalized['parameters'].setdefault(key, value)
    if BENCHMARK_STOP_NODES.get(node.get('name')) == node_type:
        if node.get('continueOnFail', False) is not False:
            raise ValueError('Politica de erro invalida em node do benchmark DEV')
        # Ausencia de onError interrompe somente com o legado continueOnFail falso.
        # null, strings e politicas explicitas de continuacao nao sao substituidos.
        normalized.setdefault('onError', 'stopWorkflow')
        normalized.setdefault('continueOnFail', False)
    return normalized


def verify_live(workflow, variant):
    expected = build(variant)
    if (not isinstance(workflow, dict) or workflow.get('active') is not True or workflow.get('pinData')
            or workflow.get('connections') != expected['connections']):
        raise ValueError('Copia DEV nao publicada ou grafo alterado')
    if workflow.get('activeVersionId') and workflow['activeVersionId'] != workflow.get('versionId'):
        raise ValueError('Versao salva difere da publicada; publicar a copia revisada antes do benchmark')
    actual = {n['name']: n for n in workflow.get('nodes', [])}
    if len(actual) != len(expected['nodes']) or len(actual) != len(workflow.get('nodes', [])):
        raise ValueError('Nodes da copia DEV divergentes')
    credentials = {}
    for node in expected['nodes']:
        current = actual.get(node['name'], {})
        normalized_current = normalized_benchmark_node(current)
        normalized_expected = normalized_benchmark_node(node)
        for key in ('type', 'typeVersion', 'parameters', 'onError', 'retryOnFail', 'disabled', 'continueOnFail'):
            if normalized_current.get(key) != normalized_expected.get(key):
                raise ValueError('Parametros/protecoes da copia DEV alterados')
        if node['type'] == 'n8n-nodes-base.httpRequest':
            creds = current.get('credentials')
            if not isinstance(creds, dict) or not creds:
                raise ValueError('Credencial DEV ausente em transporte')
            credentials[node['name']] = {key: value.get('id') for key, value in creds.items()}
            if any(not isinstance(value, str) or not value for value in credentials[node['name']].values()):
                raise ValueError('Referencia de credencial invalida')
    if any(workflow.get('settings', {}).get(k) != v for k, v in expected['settings'].items()):
        raise ValueError('Persistencia de payloads/configuracao do workflow alterada')
    return credentials


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalN8n:
    def __init__(self, base_url, api_key):
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1')
                or parsed.port != 5678 or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('Permitido somente http://127.0.0.1:5678 ou http://localhost:5678')
        if not api_key:
            raise ValueError('Definir N8N_BENCHMARK_API_KEY somente no ambiente do processo')
        self.base_url, self.api_key = base_url.rstrip('/'), api_key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, body=None):
        headers = {'Accept': 'application/json'}
        if path.startswith('/api/v1/'):
            headers['X-N8N-API-KEY'] = self.api_key
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base_url + path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with self.opener.open(request, timeout=180) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError('Resposta excede limite')
                return json.loads(raw)
        except (OSError, ValueError, urllib.error.URLError):
            # Erros HTTP podem conter payloads/headers; nao imprimir nem salvar.
            raise ValueError('Falha na API/webhook local: verificar execucao no DEV; nao reenviar o lote') from None

def run(plan_path, ids, client):
    plan = validate_plan(read_json(plan_path))
    if set(ids) != set(VARIANTS) or len(set(ids.values())) != 2 or any(
            not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value) for value in ids.values()):
        raise ValueError('Informar dois IDs locais distintos das copias de benchmark')
    folder = plan_path.parent
    # Reserva exclusiva antes de qualquer POST; sem resume/retry de namespaces usados.
    write_new(folder / 'started.json', {'benchmark_id': plan['benchmark_id'], 'scope': 'REAL_DEV_ATTEMPT', 'workflow_ids': ids})
    credentials = {v: verify_live(client.request('/api/v1/workflows/' + ids[v]), v) for v in VARIANTS}
    for name, creds in credentials['before'].items():
        if credentials['after'].get(name) != creds:
            raise ValueError('Credenciais precisam ser as mesmas nas duas variantes')
    if credentials['after']['Airtable Precheck DEV'] != credentials['after']['Airtable Buscar review_id']:
        raise ValueError('Precheck e busca final precisam usar a mesma credencial DEV')
    write_new(folder / 'session.json', {'benchmark_id': plan['benchmark_id'], 'scope': 'REAL_DEV_CONTROLLED',
        'plan_sha256': digest(plan), 'workflows': plan['workflows'], 'credential_references_sha256': digest(credentials),
        'latency_source': 'terminal report.duration_ms, not HTTP wall clock'})
    config_hash, seen = None, set()
    with (folder / 'records.ndjson').open('x', encoding='utf-8', newline='\n') as output, \
            (folder / 'dispatch.ndjson').open('x', encoding='utf-8', newline='\n') as dispatch:
        for variant in plan['order']:
            for sequence in range(1, 16):
                dispatch.write(json.dumps({'benchmark_id': plan['benchmark_id'], 'variant': variant,
                    'sequence': sequence, 'case_id': (sequence - 1) % 5 + 1}) + '\n')
                dispatch.flush()  # Tentativa registrada antes do POST; nao equivale a aceite HTTP.
                packet = client.request('/webhook/benchmark-router-' + variant + '-dev', payload(plan, variant, sequence))
                validate_packet(packet, plan, variant, sequence)
                run_id = packet['report']['run_id']
                if run_id in seen:
                    raise ValueError('run_id repetido: benchmark interrompido')
                seen.add(run_id)
                fingerprint = digest(packet.pop('configuration'))
                changed = config_hash is not None and fingerprint != config_hash
                config_hash = fingerprint
                packet['configuration_sha256'] = fingerprint
                # A resposta vem do ultimo node apos negocio + observador, nao do ACK inicial.
                # Nao depender do historico n8n nem habilitar armazenamento de payloads.
                packet['completion_status'] = 'terminal_confirmed'
                output.write(json.dumps(packet, ensure_ascii=False) + '\n')
                output.flush()
                if changed or not healthy(packet):
                    raise ValueError('Lote interrompido: falha, colisao, coleta incompleta ou configuracao mudou; preparar novos IDs')
                print(variant + ' ' + str(sequence) + '/15: terminal confirmado')
    return folder / 'records.ndjson'


def healthy(row):
    report, sequence = row['report'], row['sequence']
    m = report['metrics']
    return (row['completion_status'] == 'terminal_confirmed' and row['delivery_status'] in ('not_needed', 'sent', 'disabled')
            and report['status'] == ('success' if sequence <= 5 else 'duplicate')
            and m['persisted'] == int(sequence <= 5)
            and m['llm_calls_attempted'] == int(row['variant'] == 'before' or sequence <= 5)
            and m['llm_responses'] == m['llm_calls_attempted']
            and m['classification_valid'] == m['llm_responses']
            and row['airtable_queries_attempted'] == {'precheck': int(row['variant'] == 'after'),
                'final': int(row['variant'] == 'before' or sequence <= 5)})


def read_records(path):
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('Coleta acima de 10 MiB')
    try:
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    except ValueError:
        raise ValueError('Coleta JSONL invalida; conteudo descartado') from None


def summarize(plan, rows, dispatch=None):
    validate_plan(plan)
    expected = [(v, seq) for v in plan['order'] for seq in range(1, 16)]
    if len(rows) > len(expected):
        raise ValueError('Coleta excede o lote')
    if dispatch is not None:
        if len(dispatch) > len(expected) or len(rows) > len(dispatch):
            raise ValueError('Coleta nao reconcilia com o registro de envios')
        for item, (variant, sequence) in zip(dispatch, expected):
            if (not isinstance(item, dict) or type(item.get('sequence')) is not int or type(item.get('case_id')) is not int
                    or item != {'benchmark_id': plan['benchmark_id'], 'variant': variant, 'sequence': sequence,
                                'case_id': (sequence - 1) % 5 + 1}):
                raise ValueError('Registro de envios invalido ou duplicado')
    seen, config_hashes = set(), set()
    for row, (variant, sequence) in zip(rows, expected):
        validate_packet(row, plan, variant, sequence, record=True)
        if row['report']['run_id'] in seen:
            raise ValueError('run_id duplicado na coleta')
        seen.add(row['report']['run_id'])
        config_hashes.add(row['configuration_sha256'])
    same_config = len(config_hashes) == 1
    result = {'schema': 'vozdocliente.router.real-benchmark.result.v1', 'scope': 'REAL_DEV_CONTROLLED_NOT_PRODUCTION',
              'benchmark_id': plan['benchmark_id'], 'order': plan['order'], 'configuration_consistent': same_config,
              'variants': {}, 'comparison': {}, 'limitations': [
                  'Amostra sintetica limitada, 15 envios por variante; sem representatividade de producao.',
                  'p95/p99 com N=15 selecionam o maximo; custos estimados nao sao fatura.',
                  'Chamadas/consultas sao tentativas instrumentadas, nao comprovantes de faturamento.',
                  'Contadores somam terminais recebidos; envios sem resposta permanecem inconclusivos.',
                  'Qualidade persistida usa enums confirmados na resposta de criacao, sem releitura independente.',
                  'Ordem fixa do par pode sofrer cache e variacao temporal; repetir com novos IDs e ordem invertida.']}
    for variant in VARIANTS:
        selected = [r for r in rows if r['variant'] == variant]
        metrics = [r['report']['metrics'] for r in selected]
        latency = [r['report']['duration_ms'] for r in selected if r['report']['duration_ms'] is not None]
        calls = [m for m in metrics if m['llm_calls_attempted']]
        unknown_calls = sum(m['llm_calls_attempted'] is None for m in metrics)
        costs = [m['estimated_cost_usd'] for m in calls if m['estimated_cost_usd'] is not None]
        counts = lambda key: sum(m[key] for m in metrics) if metrics and all(m[key] is not None for m in metrics) else None
        subtotal = sum(costs) if costs else 0 if metrics and not calls and not unknown_calls else None
        persisted = [r for r in selected if r['report']['metrics']['persisted'] == 1]
        classified = [r for r in persisted if r['persisted_classification'] is not None]
        sentiment = sum(r['persisted_classification']['sentiment'] == CASES[r['case_id'] - 1]['sentiment'] for r in classified)
        theme = sum(r['persisted_classification']['theme'] == CASES[r['case_id'] - 1]['theme'] for r in classified)
        joint = sum(r['persisted_classification'] == {k: CASES[r['case_id'] - 1][k] for k in ('sentiment', 'theme')} for r in classified)
        responses = counts('llm_responses')
        dispatched = sum(item['variant'] == variant for item in dispatch) if dispatch is not None else None
        evaluated = [m for m in metrics if m['llm_responses'] is not None and m['classification_valid'] is not None]
        evaluated_responses = sum(m['llm_responses'] for m in evaluated)
        result['variants'][variant] = {
            'requests_recorded': len(selected), 'expected_requests': 15,
            'requests_attempted': dispatched,
            'terminal_reconciliation_rate': len(selected) / dispatched if dispatched else None,
            'healthy_complete': len(selected) == 15 and all(healthy(r) for r in selected),
            'success': sum(r['report']['status'] == 'success' for r in selected),
            'duplicates': sum(r['report']['status'] == 'duplicate' for r in selected),
            'failure': sum(r['report']['status'] == 'failure' for r in selected),
            'llm_calls_attempted': counts('llm_calls_attempted'), 'llm_responses': responses,
            'llm_calls_unknown_runs': unknown_calls,
            'airtable_precheck_queries_attempted': sum(r['airtable_queries_attempted']['precheck'] for r in selected),
            'airtable_final_queries_attempted': sum(r['airtable_queries_attempted']['final'] for r in selected),
            'airtable_queries_attempted': sum(sum(r['airtable_queries_attempted'].values()) for r in selected),
            'records_persisted_confirmed': counts('persisted'),
            'prompt_tokens': counts('prompt_tokens'), 'completion_tokens': counts('completion_tokens'),
            'prompt_tokens_known_subtotal': sum(m['prompt_tokens'] for m in metrics if m['prompt_tokens'] is not None) if metrics else None,
            'completion_tokens_known_subtotal': sum(m['completion_tokens'] for m in metrics if m['completion_tokens'] is not None) if metrics else None,
            'tokens_unknown_runs': sum(m['prompt_tokens'] is None or m['completion_tokens'] is None for m in metrics),
            'cost_known_classifications': len(costs), 'cost_unknown_llm_runs': len(calls) - len(costs) + unknown_calls,
            'estimated_cost_usd_known_subtotal': subtotal,
            'estimated_cost_usd_total': subtotal if len(selected) == 15 and len(costs) == len(calls) and not unknown_calls else None,
            'estimated_cost_usd_mean_known_classification': subtotal / len(costs) if costs else None,
            'latency_known_runs': len(latency), 'latency_unknown_runs': len(selected) - len(latency),
            'latency_mean_ms': sum(latency) / len(latency) if latency else None,
            **{f'p{int(q * 100)}_ms': percentile(latency, q) for q in (.5, .95, .99)},
            'schema_valid_rate': sum(m['classification_valid'] for m in evaluated) / evaluated_responses if evaluated_responses else None,
            'schema_evaluated_responses': evaluated_responses,
            'persisted_classifications_evaluated': len(classified),
            'persisted_classifications_unknown': len(persisted) - len(classified),
            'persisted_sentiment_accuracy': sentiment / len(classified) if classified else None,
            'persisted_theme_accuracy': theme / len(classified) if classified else None,
            'persisted_joint_accuracy': joint / len(classified) if classified else None}
    before, after = (result['variants'][v] for v in VARIANTS)
    comparable = same_config and all(result['variants'][v]['healthy_complete'] for v in VARIANTS)
    def reduction(key):
        a, b = before[key], after[key]
        return (a - b) / a * 100 if comparable and a is not None and b is not None and a > 0 else None
    persisted_by_case = {v: {r['case_id']: r['persisted_classification'] for r in rows
                            if r['variant'] == v and r['persisted_classification']} for v in VARIANTS}
    compared = sorted(set(persisted_by_case['before']) & set(persisted_by_case['after']))
    differing = [case for case in compared if persisted_by_case['before'][case] != persisted_by_case['after'][case]]
    result['comparison'] = {'comparable_complete_pair': comparable,
        'llm_calls_reduction_percent': reduction('llm_calls_attempted'),
        'estimated_cost_reduction_percent': reduction('estimated_cost_usd_total'),
        'additional_airtable_queries': after['airtable_queries_attempted'] - before['airtable_queries_attempted'] if comparable else None,
        'persisted_cases_compared': len(compared), 'persisted_classifications_differing_case_ids': differing}
    return result


def render(result):
    keys = list(result['variants']['before'])
    rows = ''.join('<tr><th>' + html.escape(key) + '</th>' + ''.join('<td>' + html.escape(
        'nao medido' if result['variants'][v][key] is None else str(result['variants'][v][key])) + '</td>' for v in VARIANTS)
        + '</tr>' for key in keys)
    return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Benchmark Router DEV</title>'
            '<style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:20px}table{border-collapse:collapse;width:100%}'
            'th,td{text-align:left;padding:8px;border-bottom:1px solid #ddd}pre{white-space:pre-wrap}</style>'
            '<h1>Benchmark real controlado DEV</h1><p>Amostra sintetica e limitada; nao representa producao. '
            'Latencia vem do evento terminal, nao do tempo HTTP. Valores desconhecidos permanecem nao medidos.</p>'
            '<table><tr><th>Metrica</th><th>Antes</th><th>Depois</th></tr>' + rows + '</table><h2>Comparacao</h2><pre>'
            + html.escape(json.dumps(result['comparison'], ensure_ascii=False, indent=2)) + '</pre><ul>'
            + ''.join('<li>' + html.escape(item) + '</li>' for item in result['limitations']) + '</ul></html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare', help='Offline: gerar plano e copias, sem medições')
    prep.add_argument('--output-dir', type=Path, required=True)
    for key in ('dev-base-id', 'dev-table-id', 'dev-slack-channel-id'):
        prep.add_argument('--' + key, required=True)
    prep.add_argument('--first', choices=VARIANTS, default='before')
    execute = sub.add_parser('run', help='Somente posteriormente: chamadas reais DEV')
    execute.add_argument('--plan', type=Path, required=True)
    execute.add_argument('--execute-real-dev', action='store_true')
    execute.add_argument('--base-url', default='http://127.0.0.1:5678')
    for variant in VARIANTS:
        execute.add_argument('--' + variant + '-workflow-id', required=True)
    report = sub.add_parser('report', help='Offline: comparar somente a coleta fornecida')
    report.add_argument('--plan', type=Path, required=True)
    report.add_argument('--records', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            plan = prepare(args.output_dir, {k: getattr(args, k) for k in ('dev_base_id', 'dev_table_id', 'dev_slack_channel_id')}, args.first)
            print('Preparado offline: ' + plan['benchmark_id'] + '; nenhum resultado medido')
        elif args.command == 'run':
            if not args.execute_real_dev:
                raise ValueError('run exige --execute-real-dev; prepare e report nao fazem chamadas')
            run(args.plan, {v: getattr(args, v + '_workflow_id') for v in VARIANTS},
                LocalN8n(args.base_url, os.environ.get('N8N_BENCHMARK_API_KEY')))
        else:
            dispatch_path = args.plan.parent / 'dispatch.ndjson'
            result = summarize(read_json(args.plan), read_records(args.records),
                               read_records(dispatch_path) if dispatch_path.exists() else None)
            folder = args.plan.parent
            write_new(folder / 'report.json', result)
            with (folder / 'report.html').open('x', encoding='utf-8') as output:
                output.write(render(result))
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        # Mensagens de validacao sao fixas; nao ecoar caminhos, dados ou erros HTTP.
        message = str(error) if type(error) is ValueError else 'Entrada/saida invalida; nenhum conteudo bruto registrado'
        parser.exit(2, 'Benchmark interrompido: ' + message + '\n')


if __name__ == '__main__':
    main()
