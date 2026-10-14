"""Fingerprint build004 evidence and the final working tree without rewriting history.
This is a local inventory, not a signed attestation or a claim that every target passed.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/build004'


def fingerprint(path):
    with path.open('rb') as source:
        value = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'sha256': value, 'bytes': path.stat().st_size}


def load(name):
    return json.loads((OUT / name).read_text())


def main():
    study = load('study-qwen3/comparison.json')
    smoke = load('docker-smoke.json')
    restored = load('restore-final.json')
    crash = load('crash-recovery.json')
    reproduction = load('repair-reproduction-final.json')
    assert study['complete'] and len(study['attempts']) == 36
    assert smoke['passed'] and all(smoke['checks'].values())
    assert restored['passed'] and crash['passed']
    assert load('browser-live004.json')['passed']
    assert load('verifier-image-recovery.json')['passed']
    assert load('verifier-image-reference-smoke.json')['passed']
    assert reproduction['outcome_reproduced'] and reproduction['checks']['passed']
    assert '11 passed' in (OUT / 'browser-final-public.txt').read_text()
    assert '3 passed' in (OUT / 'browser-oidc-final.txt').read_text()
    assert '2 passed' in (OUT / 'real-provider-docker.txt').read_text()
    for name in ('frontend-lint-final.txt', 'frontend-types-final.txt', 'frontend-build-final.txt'):
        assert (OUT / name).stat().st_size > 0
    receipts = load('final-checks.json')
    assert all(receipts['checks'].values())
    historical = json.loads((ROOT / 'evidence/build003/manifest.json').read_text())
    mismatches = [name for name, expected in historical['evidence'].items()
                  if not (ROOT / name).is_file() or fingerprint(ROOT / name) != expected]
    assert not mismatches, 'Historical evidence changed: ' + repr(mismatches)
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT
    ).decode().split('\0')
    prefixes = ('kairos_api/', 'dashboard/', 'scripts/', 'tests/', '.github/', 'docs/', 'cases/')
    root_files = {'AGENTS.md', 'README.md', 'ARCHITECTURE.md', 'BRAIN.md', 'DESIGN.md', 'PLAN.md',
                  'Dockerfile.api', 'Dockerfile.web', 'Dockerfile.investigation-django',
                  'Dockerfile.investigation-study', '.dockerignore', '.gitignore',
                  'compose.production.yaml', 'compose.yaml', 'requirements-api.txt',
                  'requirements-api.lock'}
    sources = {name: fingerprint(ROOT / name) for name in sorted(set(names))
               if (ROOT / name).is_file() and not (ROOT / name).is_symlink()
               and (name.startswith(prefixes) or name in root_files)}
    evidence = {str(path.relative_to(ROOT)): fingerprint(path) for path in sorted(OUT.rglob('*'))
                if path.is_file() and path.name not in {'manifest.json', '.DS_Store'}}
    capacity = load('capacity-summary-final.json')
    output = {
        'build': '004', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'repository_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'scope': 'Local working-tree source and receipts. No commit, push, public hosting or paid API.',
        'validation': receipts,
        'historical_evidence': {'build003_files_verified': len(historical['evidence']), 'mismatches': []},
        'repair_study': {'complete': study['complete'], 'attempts': len(study['attempts']),
                         'strategies': study['strategies'], 'quality_target': study['declared_quality_target'],
                         'incomplete_duration_attempts': study.get('incomplete_duration_attempts', 0)},
        'capacity': capacity,
        'tested_images': {key: smoke[key] for key in ('api_image_id', 'web_image_id', 'api_uid', 'web_uid')},
        'sources': sources, 'evidence': evidence,
        'limits': ['Local hashes do not establish immutable history or signed provenance.',
                   'The original pooled soak failed; capacity targets are not inferred from successful latency alone.',
                   'Curated, human-localized public cases do not establish broad repair competence or leaderboard performance.',
                   'Candidate Python shares its verifier environment; adversarial test-forgery resistance is unproven.',
                   'Lenovo hardware, public hosting, external adoption, hosted CI and personal code ownership are unassessed.']}
    (OUT / 'manifest.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'source_files': len(sources), 'evidence_files': len(evidence),
                      'quality_target_met': study['declared_quality_target']['met']}, indent=2))


if __name__ == '__main__':
    main()
