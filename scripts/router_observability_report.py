"""Relatorio HTML local a partir SOMENTE de eventos permitidos. Sem rede/dependencias."""
import argparse
import html
import json
import math
from datetime import datetime
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'n8n-mirror/observability/router-contract.json').read_text(encoding='utf-8'))


def canonical(raw):
    if not isinstance(raw, dict) or set(raw) != set(CONTRACT['fields']):
        raise ValueError('Evento invalido')
    if (raw['schema'] != CONTRACT['schema'] or raw['source'] not in CONTRACT['sources']
            or raw['kind'] not in ('stage', 'run') or raw['stage'] not in CONTRACT['stages']
            or raw['status'] not in CONTRACT['statuses'] or raw['error_code'] not in CONTRACT['codes']
            or not isinstance(raw['run_id'], str) or not re.fullmatch(r'router-(?:\d{1,30}|error-\d{1,30})', raw['run_id'])
            or raw['correlation'] not in ('execution', 'error_handler')
            or (raw['correlation'] == 'error_handler') != raw['run_id'].startswith('router-error-')
            or raw['event_id'] != ':'.join((raw['run_id'], raw['kind'], raw['stage'], raw['status']))
            or not isinstance(raw['at'], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', raw['at'])):
        raise ValueError('Evento invalido')
    datetime.strptime(raw['at'], '%Y-%m-%dT%H:%M:%S.%fZ')

    def number(value, integer=False):
        return value is None or type(value) in ((int,) if integer else (int, float)) and math.isfinite(value) and 0 <= value <= 1e12

    if (not number(raw['duration_ms'], True) or not isinstance(raw['metrics'], dict)
            or set(raw['metrics']) != set(CONTRACT['counters'] + CONTRACT['measures'])
            or any(not number(raw['metrics'][key], True) for key in CONTRACT['counters'])
            or any(not number(raw['metrics'][key]) for key in CONTRACT['measures'])
            or raw['kind'] == 'run' and raw['status'] == 'started'
            or (raw['status'] == 'failure') != (raw['error_code'] != 'NONE')):
        raise ValueError('Evento invalido')
    expected = {'runs_total': int(raw['kind'] == 'run'),
                **{'runs_' + key: int(raw['kind'] == 'run' and raw['status'] == status)
                   for key, status in (('success', 'success'), ('duplicate', 'duplicate'), ('failure', 'failure'))}}
    if any(raw['metrics'][key] != value for key, value in expected.items()):
        raise ValueError('Evento invalido')
    for smaller, larger in (('classification_valid', 'llm_responses'), ('llm_responses', 'llm_calls_attempted')):
        if raw['metrics'][smaller] is not None and raw['metrics'][larger] is not None and raw['metrics'][smaller] > raw['metrics'][larger]:
            raise ValueError('Evento invalido')
    return raw


def read_events(path):
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('Entrada excede limite local de 10 MiB')
    events, rejected = [], 0
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        try:
            # Aceita JSONL puro ou prefixo de stdout; nunca salva o texto descartado.
            start = line.find('{')
            if start < 0:
                rejected += 1
                continue
            raw, _ = json.JSONDecoder().raw_decode(line[start:])
            # docker logs --format/json-file: log externo contem a linha interna.
            if isinstance(raw, dict) and isinstance(raw.get('log'), str):
                text = raw['log']
                raw, _ = json.JSONDecoder().raw_decode(text[text.index('{'):])
            if isinstance(raw, str):
                raw = json.loads(raw)
            events.append(canonical(raw))
        except (ValueError, TypeError, KeyError, OverflowError):
            rejected += 1
    return events, rejected


def percentile(values, quantile):
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def aggregate(events):
    result = {}
    for source in CONTRACT['sources']:
        selected = [event for event in events if event['source'] == source]
        if not selected:
            continue
        # Recoleta do mesmo evento nao conta novamente. Nunca misturar fontes.
        unique = {(e['run_id'], e['event_id']): e for e in selected}
        by_run = {}
        for event in unique.values():
            by_run.setdefault(event['run_id'], []).append(event)
        terminal = []
        for values in by_run.values():
            ends = [e for e in values if e['kind'] == 'run']
            if ends:
                # Falha prevalece; no mesmo status, evento inline tem mais metricas.
                terminal.append(max(ends, key=lambda e: (
                    {'success': 0, 'duplicate': 1, 'failure': 2}[e['status']],
                    e['error_code'] != 'WORKFLOW_INTERRUPTED')))
        latencies = [e['duration_ms'] for e in terminal if e['duration_ms'] is not None]
        failures = sum(e['status'] == 'failure' for e in terminal)
        prices = [e['metrics']['estimated_cost_usd'] for e in terminal if e['metrics']['estimated_cost_usd'] is not None]
        attempts = [e['metrics']['llm_calls_attempted'] for e in terminal if e['metrics']['llm_calls_attempted'] is not None]
        persisted = [e['metrics']['persisted'] for e in terminal if e['metrics']['persisted'] is not None]
        evaluated = [e for e in terminal if e['metrics']['llm_responses'] is not None and e['metrics']['classification_valid'] is not None]
        responses = sum(e['metrics']['llm_responses'] for e in evaluated)
        stage_latency = {}
        for stage in CONTRACT['stages']:
            values = [e['duration_ms'] for e in unique.values() if e['kind'] == 'stage' and e['stage'] == stage
                      and e['status'] == 'success' and e['duration_ms'] is not None]
            if values:
                stage_latency[stage] = {'n': len(values), **{f'p{int(q*100)}_ms': percentile(values, q) for q in (.5, .95, .99)}}
        times = sorted(e['at'] for e in selected)
        result[source] = {'window_start': times[0], 'window_end': times[-1], 'observed_runs': len(by_run),
            'terminal_runs': len(terminal), 'incomplete_runs': len(by_run) - len(terminal),
            'telemetry_failures': sum(e['kind'] == 'stage' and e['stage'] == 'telemetry' and e['status'] == 'failure' for e in unique.values()),
            'handler_only_incidents': sum(e['correlation'] == 'error_handler' for e in terminal),
            'received_known': sum(e['metrics']['received'] or 0 for e in terminal),
            'received_unknown_runs': sum(e['metrics']['received'] is None for e in terminal),
            'success': sum(e['status'] == 'success' for e in terminal),
            'duplicate': sum(e['status'] == 'duplicate' for e in terminal), 'failure': failures,
            'error_rate': failures / len(terminal) if terminal else None,
            'latency_n': len(latencies), **{f'p{int(q*100)}_ms': percentile(latencies, q) for q in (.5, .95, .99)},
            'llm_attempts_known': sum(attempts) if attempts else None,
            'llm_attempts_unknown_runs': len(terminal) - len(attempts),
            'persisted_confirmed': sum(persisted) if persisted else None,
            'persisted_unknown_runs': len(terminal) - len(persisted),
            'estimated_cost_usd_known_subtotal': sum(prices) if prices else None,
            'cost_known_runs': len(prices), 'cost_unknown_runs': len(terminal) - len(prices),
            'schema_valid_rate': sum(e['metrics']['classification_valid'] for e in evaluated) / responses if responses else None,
            'schema_evaluated_responses': responses, 'classification_accuracy': None, 'human_labels': 0,
            'quality_unknown_runs': len(terminal) - len(evaluated),
            'stage_latency': stage_latency}
    return result


def render(summary, rejected):
    sections = []
    for source, data in summary.items():
        label = 'SIMULACAO OFFLINE — sem APIs' if source == 'offline_simulation' else 'EVENTOS n8n — revisar origem da coleta'
        cells = [(key, 'nao medido' if value is None else value) for key, value in data.items() if key != 'stage_latency']
        rows = ''.join('<tr><th>' + html.escape(key) + '</th><td>' + html.escape(str(value)) + '</td></tr>' for key, value in cells)
        bars = ''.join('<div>' + name + ': ' + str(data[name]) + '<span style="width:'
                       + str(round(data[name] / max(1, data['terminal_runs']) * 100, 2)) + '%"></span></div>'
                       for name in ('success', 'duplicate', 'failure'))
        stages = ''.join('<tr><td>' + html.escape(stage) + '</td><td>' + str(value['n']) + '</td><td>'
                         + str(value['p50_ms']) + '</td><td>' + str(value['p95_ms']) + '</td><td>' + str(value['p99_ms']) + '</td></tr>'
                         for stage, value in data['stage_latency'].items())
        sections.append('<section><h2>' + label + '</h2><div class="bars">' + bars + '</div><table>' + rows
                        + '</table><h3>Latencia por etapa concluida (ms)</h3><table><tr><th>Etapa</th><th>N</th><th>p50</th><th>p95</th><th>p99</th></tr>'
                        + stages + '</table></section>')
    return '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VozDoCliente — observabilidade Router DEV</title><style>
body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;background:#f3f6fa;color:#17273b}
section{background:white;padding:24px;margin:20px 0;border-radius:12px}table{border-collapse:collapse;width:100%}
th,td{text-align:left;border-bottom:1px solid #dce3ec;padding:8px}th{font-weight:600}.bars div{margin:12px 0}
.bars span{display:block;height:14px;background:#186a86;border-radius:4px;margin-top:4px}p{line-height:1.6}</style>
<h1>VozDoCliente · Router DEV</h1><p>Janela = eventos fornecidos. Percentis por nearest-rank; amostras pequenas nao demonstram SLO.
Tentativas LLM nao sao chamadas faturadas. Custo e estimativa parcial, nao fatura. Validade de schema nao e acuracia.
Fontes simuladas e n8n permanecem separadas. Nao ha CDN, JavaScript remoto ou envio de dados.</p>''' + (
        '<p>Linhas rejeitadas/ignoradas: ' + str(rejected) + ' (conteudo descartado).</p>'
        + ''.join(sections) + ('<p>Nenhum evento valido coletado.</p>' if not sections else '') + '</html>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--events-output', type=Path)
    args = parser.parse_args()
    events, rejected = read_events(args.input)
    summary = aggregate(events)
    args.output.write_text(render(summary, rejected), encoding='utf-8')
    if args.events_output:
        args.events_output.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events), encoding='utf-8')
    print(json.dumps({'valid_events': len(events), 'rejected_lines': rejected, 'summary': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
