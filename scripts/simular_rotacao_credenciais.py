"""Exercicio offline de ESTADOS; nao implementa cifragem n8n nem APIs de provedores.

Nao le .env, variaveis de ambiente, cofre, banco n8n ou credenciais reais.
Somente le artefatos publicos permitidos e escreve o relatorio explicitamente pedido.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "docs/security/evidencias"
ARTIFACTS = [
    "n8n-mirror/workflows/vozdocliente-router-v3.json",
    "n8n-mirror/workflows/vozdocliente-router-v4.json",
    "n8n-mirror/workflows/vozdocliente-retencao-v1.json",
    "n8n-mirror/workflows/vozdocliente-retencao-demo.json",
    "n8n-mirror/docker-compose.yml",
    "n8n-mirror/docker-compose.retention.yml",
    "Dockerfile", ".env.example",
]


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def artifact_hashes():
    result = {}
    for name in ARTIFACTS:
        text = (ROOT / name).read_text(encoding="utf-8")  # Normaliza CRLF para LF.
        value = json.loads(text) if name.endswith(".json") else text
        result[name] = digest(value)
    return result


def scenarios():
    results = []

    def check(name, expected, observed):
        passed = expected == observed
        results.append({"scenario": name, "expected": expected, "observed": observed, "passed": passed})
        if not passed:
            raise RuntimeError("SIMULATION_ASSERTION_FAILED")

    # Mesmo modelo abstrato em todos os casos: nao promete semantica de um fornecedor.
    for provider in ("openai_mock", "airtable_mock", "slack_mock", "railway_secret_mock"):
        valid_versions = {"old"}
        bound_version = "old"
        accepts = lambda version, environment="DEV": version in valid_versions and environment == "DEV"
        check(provider + ":baseline", True, accepts(bound_version))
        valid_versions.add("new")
        bound_version = "invalid"
        check(provider + ":replacement_invalid_rejected", False, accepts(bound_version))
        bound_version = "old"
        check(provider + ":rollback_before_revocation", True, accepts(bound_version))
        bound_version = "new"
        check(provider + ":replacement_validated", True, accepts(bound_version))
        check(provider + ":dev_not_prod", False, accepts(bound_version, "PROD"))
        valid_versions.remove("old")
        check(provider + ":old_revoked", False, accepts("old"))
        check(provider + ":new_remains_valid", True, accepts(bound_version))
        check(provider + ":rollback_to_revoked_blocked", False, accepts("old"))

    # Modelo de compatibilidade chave/estado: NENHUM cifrador, segredo ou dado real.
    snapshot = {"requires_key_version": "key-v1", "credential_labels": ["CRED-SIM-A", "CRED-SIM-B"]}
    can_read = lambda store, key_version: store["requires_key_version"] == key_version
    check("n8n_model:matching_key_and_snapshot", True, can_read(snapshot, "key-v1"))
    check("n8n_model:blind_master_key_change_fails", False, can_read(snapshot, "key-v2"))
    check("n8n_model:restoring_original_pair_recovers", True, can_read(snapshot, "key-v1"))
    # Uma migracao real de todos os dados sensiveis nao e implementada aqui.
    migrated_model = {**snapshot, "requires_key_version": "key-v2"}
    check("n8n_model:migrated_state_needs_matching_key", True, can_read(migrated_model, "key-v2"))
    check("n8n_model:mixed_old_key_new_state_fails", False, can_read(migrated_model, "key-v1"))
    refresh_implemented = False
    check("slack_model:native_rotation_blocked_without_refresh", False, refresh_implemented)
    return results


def make_report():
    before = artifact_hashes()
    result = scenarios()
    after = artifact_hashes()
    if before != after:
        raise RuntimeError("ARTIFACTS_CHANGED")
    report = {
        "schema_version": 1,
        "scope": "SIMULACAO_OFFLINE_DE_ESTADOS",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "real_rotation": False,
        "real_provider_validation": False,
        "n8n_crypto_validated": False,
        "network_calls": 0,
        "simulator_sha256": digest(Path(__file__).read_text(encoding="utf-8")),
        "artifacts_hash_algorithm": "SHA256_OF_CANONICAL_JSON_OR_JSON_ENCODED_LF_TEXT",
        "artifacts_before": before, "artifacts_after": after,
        "artifacts_unchanged": True,
        "scenarios": result,
        "passed": len(result), "failed": 0,
    }
    report["report_sha256"] = digest(report)
    return report


def verify_report(path):
    # Verifica consistencia/reprodutibilidade; checksum nao e assinatura ou prova de autoria.
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise RuntimeError("REPORT_SCHEMA_INVALID")
    checksum = report.pop("report_sha256")
    if checksum != digest(report):
        raise RuntimeError("REPORT_CHECKSUM_INVALID")
    expected = make_report()
    for key, value in expected.items():
        if key not in {"executed_at_utc", "report_sha256"} and report.get(key) != value:
            raise RuntimeError("REPORT_STALE_OR_INVALID")
    time = datetime.fromisoformat(report["executed_at_utc"])
    if time.utcoffset() != timezone.utc.utcoffset(time):
        raise RuntimeError("REPORT_TIMESTAMP_INVALID")
    if set(report) != set(expected) - {"report_sha256"}:
        raise RuntimeError("REPORT_SCHEMA_INVALID")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--output", type=Path, help="Relatorio JSON dentro de docs/security/evidencias")
    group.add_argument("--verify", type=Path, help="Verifica checksum, cenarios e artefatos atuais")
    args = parser.parse_args()
    try:
        if args.verify:
            evidence = args.verify.resolve()
            if not evidence.is_relative_to(EVIDENCE_DIR.resolve()) or evidence.suffix != ".json":
                raise RuntimeError("INPUT_NOT_ALLOWED")
            report = verify_report(evidence)
            print(f"[OK] Relatorio consistente: {report['passed']} cenarios simulados. Nenhuma rotacao real comprovada.")
            return 0
        report = make_report()
        if args.output:
            output = args.output.resolve()
            if not output.is_relative_to(EVIDENCE_DIR.resolve()) or output.suffix != ".json" or output.is_symlink():
                raise RuntimeError("OUTPUT_NOT_ALLOWED")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"[OK] Relatorio salvo: {output.relative_to(ROOT).as_posix()}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"RESULTADO: {report['passed']} cenarios simulados passaram, 0 falharam; chamadas de rede: 0.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        # Nao inclui conteudo do arquivo ou valores recebidos em mensagens de erro.
        print("[FALHA] Simulacao ou verificacao invalida. Confira caminho, artefatos e checksum; nenhum segredo foi lido.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
