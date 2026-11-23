"""Consolida evidencia local existente, sem rede, payloads, destinos ou credenciais."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from router_real_benchmark import read_json, read_records, summarize, render as render_benchmark
from router_observability_report import (CONTRACT, aggregate, read_events, read_labels,
                                         render as render_dashboard)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/evidencias'
BENCHMARK_ID = '097ec2ffc37c4e4081bb54d9a0c174c0'
LABELS = ROOT / 'docs/evidencias/router-qualidade-dev-rotulos.json'
NAMES = ('benchmark-dev-real.json', 'benchmark-dev-real.html', 'benchmark-dev-amostras.json',
         'router-observabilidade-dev-real.json', 'router-observabilidade-dev-real.html')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def number(value, integer=False):
    return (type(value) in (int, float) and math.isfinite(value) and value >= 0
            and (not integer or type(value) is int))


def benchmark_html(result):
    note = ('<p><strong>Acurácia das classificações persistidas: não avaliada neste benchmark.</strong> '
            'Zero snapshots disponíveis; lista vazia de divergências não comprova equivalência semântica. '
            'A avaliação separada de cinco exemplos teve 80% de acurácia conjunta e não integra este lote.</p>')
    return render_benchmark(result).replace('<h1>Benchmark real controlado DEV</h1>',
        '<h1>Benchmark real controlado DEV</h1>' + note)


def dashboard_html(data):
    note = ('<p><strong>Coleta operacional separada: 11 execuções DEV.</strong> '
            'As três falhas foram intencionais: 27,27% descreve o experimento, não operação normal. '
            'Custo médio estimado: US$ 0,0000434 nas cinco classificações com custo conhecido; '
            'outras duas classificações têm custo desconhecido, nunca zero. '
            'A qualidade manual (cinco exemplos, conjunta 80%) não foi medida no benchmark antes/depois.</p>')
    return render_dashboard(data['summary'], data['rejected_lines']).replace(
        '<h1>VozDoCliente · Router DEV</h1>', '<h1>VozDoCliente · Router DEV</h1>' + note)


def collect(benchmark_dir, events_path):
    plan = read_json(benchmark_dir / 'plan.json')
    records = read_records(benchmark_dir / 'records.ndjson')
    dispatch = read_records(benchmark_dir / 'dispatch.ndjson')
    result = summarize(plan, records, dispatch)
    if result['benchmark_id'] != BENCHMARK_ID or not result['comparison']['comparable_complete_pair']:
        raise ValueError('Evidencia exige o par real completo identificado na entrega')
    if result != read_json(benchmark_dir / 'report.json'):
        raise ValueError('Relatorio local diverge do recalculo offline')
    if any(row['persisted_classification'] is not None for row in records):
        raise ValueError('Este lote foi documentado sem avaliacao de qualidade persistida')
    samples = {'schema': 'vozdocliente.benchmark.numeric-samples.v1', 'benchmark_id': BENCHMARK_ID,
               'scope': 'REAL_DEV_CONTROLLED_NOT_PRODUCTION', 'persisted_quality': 'not_evaluated',
               'samples': [{
                   'variant': row['variant'], 'sequence': row['sequence'], 'status': row['report']['status'],
                   'duration_ms': row['report']['duration_ms'], 'metrics': row['report']['metrics'],
                   'airtable_queries_attempted': row['airtable_queries_attempted']
               } for row in records]}
    # Os leitores existentes aplicam allowlists estritas antes de qualquer gravacao.
    events, rejected = read_events(events_path)
    if rejected or any(e['source'] != 'n8n' for e in events):
        raise ValueError('Dashboard publico exige coleta n8n valida, sem fontes simuladas')
    summary = aggregate(events, read_labels(LABELS))
    if summary.get('n8n', {}).get('terminal_runs') != 11:
        raise ValueError('Dashboard exige a coleta separada de 11 execucoes')
    dashboard = {'schema': 'vozdocliente.observability.public-summary.v1',
                 'scope': 'SEPARATE_DEV_COLLECTION_SYNTHETIC_LIMITED',
                 'valid_events': len(events), 'rejected_lines': rejected, 'summary': summary}
    artifacts = dict(zip(NAMES, (json_text(result), benchmark_html(result), json_text(samples),
                                json_text(dashboard), dashboard_html(dashboard))))
    sources = {name: sha((benchmark_dir / name).read_bytes()) for name in ('plan.json', 'records.ndjson', 'dispatch.ndjson', 'report.json')}
    manifest = {'schema': 'vozdocliente.etapa2.public-evidence.v1', 'benchmark_id': BENCHMARK_ID,
        'source_sha256': sources, 'observability_events_sha256': sha(events_path.read_bytes()),
        'quality_labels_sha256': sha(LABELS.read_bytes()), 'exporter_sha256': sha(Path(__file__).read_bytes()),
        'artifacts_sha256': {name: sha(text.encode('utf-8')) for name, text in artifacts.items()},
        'privacy': 'Somente agregados e amostras numericas permitidas; sem logs brutos, run IDs, destinos ou credenciais.',
        'interpretation': 'Hashes comprovam consistencia, nao autenticidade independente. Benchmark sem avaliacao semantica; qualidade 80% em amostra separada.'}
    artifacts['etapa-2-evidencias-manifesto.json'] = json_text(manifest)
    return artifacts


def check_public(folder):
    """Validacao reproduzivel no checkout, sem depender de coletas locais ignoradas."""
    manifest = read_json(folder / 'etapa-2-evidencias-manifesto.json')
    if manifest['benchmark_id'] != BENCHMARK_ID or set(manifest['artifacts_sha256']) != set(NAMES):
        raise ValueError('Manifesto publico invalido')
    for name in NAMES:
        if sha((folder / name).read_bytes()) != manifest['artifacts_sha256'][name]:
            raise ValueError('Hash de evidencia publica divergente')
    if manifest['exporter_sha256'] != sha(Path(__file__).read_bytes()):
        raise ValueError('Exportador alterado; revalidar/regenerar evidencia')
    result = read_json(folder / 'benchmark-dev-real.json')
    samples = read_json(folder / 'benchmark-dev-amostras.json')
    dashboard = read_json(folder / 'router-observabilidade-dev-real.json')
    if (set(samples) != {'schema', 'benchmark_id', 'scope', 'persisted_quality', 'samples'}
            or samples['schema'] != 'vozdocliente.benchmark.numeric-samples.v1'
            or samples['scope'] != 'REAL_DEV_CONTROLLED_NOT_PRODUCTION'
            or samples['benchmark_id'] != result['benchmark_id'] or samples['persisted_quality'] != 'not_evaluated'
            or len(samples['samples']) != 30):
        raise ValueError('Amostras publicas divergentes')
    for row in samples['samples']:
        if (set(row) != {'variant', 'sequence', 'status', 'duration_ms', 'metrics', 'airtable_queries_attempted'}
                or row['variant'] not in ('before', 'after')
                or row['status'] not in ('success', 'duplicate', 'failure')
                or not number(row['sequence'], True) or row['sequence'] is None
                or not number(row['duration_ms'], True) or row['duration_ms'] is None
                or set(row['metrics']) != set(CONTRACT['counters'] + CONTRACT['measures'])
                or any(v is None or not number(v) for v in row['metrics'].values())
                or set(row['airtable_queries_attempted']) != {'precheck', 'final'}
                or any(v is None or not number(v, True) for v in row['airtable_queries_attempted'].values())):
            raise ValueError('Amostra fora da allowlist numerica publica')
    from router_observability_report import percentile
    for variant in ('before', 'after'):
        rows = [r for r in samples['samples'] if r['variant'] == variant]
        data = result['variants'][variant]
        if [r['sequence'] for r in rows] != list(range(1, 16)):
            raise ValueError('Sequencia publica incompleta ou duplicada')
        metrics = [r['metrics'] for r in rows]
        known = [r['duration_ms'] for r in rows if r['duration_ms'] is not None]
        measured = {
            'requests_recorded': len(rows), 'success': sum(r['status'] == 'success' for r in rows),
            'duplicates': sum(r['status'] == 'duplicate' for r in rows), 'failure': sum(r['status'] == 'failure' for r in rows),
            'llm_calls_attempted': sum(m['llm_calls_attempted'] for m in metrics),
            'llm_responses': sum(m['llm_responses'] for m in metrics),
            'schema_valid_rate': sum(m['classification_valid'] for m in metrics) / sum(m['llm_responses'] for m in metrics),
            'schema_evaluated_responses': sum(m['llm_responses'] for m in metrics),
            'records_persisted_confirmed': sum(m['persisted'] for m in metrics),
            'prompt_tokens': sum(m['prompt_tokens'] for m in metrics), 'completion_tokens': sum(m['completion_tokens'] for m in metrics),
            'estimated_cost_usd_total': sum(m['estimated_cost_usd'] for m in metrics if m['llm_calls_attempted']),
            'airtable_queries_attempted': sum(sum(r['airtable_queries_attempted'].values()) for r in rows),
            'latency_mean_ms': sum(known) / len(known),
            **{f'p{int(q * 100)}_ms': percentile(known, q) for q in (.5, .95, .99)}}
        if any(data[k] != value for k, value in measured.items()):
            raise ValueError('Agregados nao correspondem as amostras numericas')
        if data['persisted_classifications_evaluated'] != 0 or any(data[k] is not None for k in (
                'persisted_sentiment_accuracy','persisted_theme_accuracy','persisted_joint_accuracy')):
            raise ValueError('Benchmark nao contem avaliacao semantica')
    before, after = (result['variants'][v] for v in ('before', 'after'))
    for key, metric in (('llm_calls_reduction_percent', 'llm_calls_attempted'),
                        ('estimated_cost_reduction_percent', 'estimated_cost_usd_total')):
        if not math.isclose(result['comparison'][key], (1 - after[metric] / before[metric]) * 100, abs_tol=1e-12):
            raise ValueError('Reducao percentual divergente')
    if (result['comparison']['additional_airtable_queries'] != after['airtable_queries_attempted'] - before['airtable_queries_attempted']
            or result['comparison']['persisted_cases_compared'] != 0):
        raise ValueError('Comparacao publica divergente')
    if (folder / 'benchmark-dev-real.html').read_text(encoding='utf-8') != benchmark_html(result):
        raise ValueError('HTML de benchmark divergente')
    if (folder / 'router-observabilidade-dev-real.html').read_text(encoding='utf-8') != dashboard_html(dashboard):
        raise ValueError('HTML de observabilidade divergente')
    if sha(LABELS.read_bytes()) != manifest['quality_labels_sha256']:
        raise ValueError('Rotulos da avaliacao separada divergentes')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark-dir', type=Path, default=ROOT / 'router-benchmark-local-02')
    parser.add_argument('--events', type=Path, default=ROOT / 'router-local-final-permitido.ndjson')
    parser.add_argument('--check', action='store_true', help='Somente evidencia publica, offline')
    args = parser.parse_args()
    if args.check:
        check_public(OUTPUT)
        print('[OK] Evidencias publicas: hashes, agregados, HTMLs e separacao de qualidade')
    else:
        artifacts = collect(args.benchmark_dir, args.events)
        for name, text in artifacts.items():
            (OUTPUT / name).write_text(text, encoding='utf-8', newline='\n')
        print('[OK] Seis evidencias sanitizadas consolidadas offline; coletas originais preservadas')


if __name__ == '__main__':
    main()
