"""Seal local build003 receipts without altering historical evaluation records."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/build003'


def fingerprint(path):
    content = path.read_bytes()
    return {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}


def main():
    log = (EVIDENCE / 'backend-tests.txt').read_text()
    assert '199 passed, 2 warnings' in log
    smoke = json.loads((EVIDENCE / 'docker-smoke.json').read_text())
    reproduction = json.loads((EVIDENCE / 'repair-reproduction.json').read_text())
    browser = json.loads((EVIDENCE / 'browser-acceptance.json').read_text())
    npm = json.loads((EVIDENCE / 'npm-audit.json').read_text())
    python = json.loads((EVIDENCE / 'python-audit.json').read_text())
    assert smoke['passed'] and all(smoke['checks'].values())
    assert reproduction['outcome_reproduced'] and reproduction['checks']['passed']
    assert all(browser['checks'].values())
    assert npm['metadata']['vulnerabilities']['total'] == 0
    assert all(not row.get('vulns') for row in python['dependencies'])
    assert 'pass 4' in (EVIDENCE / 'frontend-boundary-tests.txt').read_text()
    for name in ('frontend-lint.txt', 'frontend-types.txt', 'frontend-build.txt'):
        assert (EVIDENCE / name).stat().st_size > 0
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT
    ).decode().split('\0')
    prefixes = ('kairos_api/', 'dashboard/', 'scripts/', 'tests/', '.github/', 'docs/', 'cases/')
    root_files = {'README.md', 'ARCHITECTURE.md', 'BRAIN.md', 'DESIGN.md', 'PLAN.md',
                  'Dockerfile.api', 'Dockerfile.web', 'Dockerfile.investigation-django',
                  '.dockerignore', '.gitignore', 'compose.production.yaml', 'compose.yaml',
                  'requirements-api.txt', 'requirements-api.lock'}
    sources = {}
    for name in sorted(set(names)):
        path = ROOT / name
        if path.is_file() and not path.is_symlink() and (name.startswith(prefixes) or name in root_files):
            sources[name] = fingerprint(path)
    evidence = {str(path.relative_to(ROOT)): fingerprint(path)
                for path in sorted(EVIDENCE.rglob('*'))
                if path.is_file() and path.name != 'manifest.json'}
    output = {
        'build': '003', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'repository_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'scope': 'Local working-tree source and receipts. No commit, push or public deployment.',
        'validation': {'backend_passed': 199, 'backend_skipped': 0, 'dependency_warnings': 2,
                       'frontend_boundary_passed': 4, 'frontend_lint': 'pass',
                       'frontend_types': 'pass', 'frontend_build': 'pass',
                       'container_smoke': 'pass', 'fresh_repair_reproduction': 'pass',
                       'browser_acceptance': 'pass', 'npm_known_findings': 0,
                       'api_lock_known_findings': 0, 'hosted_ci': 'not_run'},
        'model_result': {'final_attempts': 12, 'verified_attempts': 2,
                         'distinct_repaired_cases': 1, 'qualified_cases': 6,
                         'loop_advantage_demonstrated': False, 'api_spend_usd': 0},
        'tested_images': {key: smoke[key] for key in ('api_image_id', 'web_image_id', 'api_uid', 'web_uid')},
        'sources': sources, 'evidence': evidence,
        'limits': ['Local SHA256 fingerprints do not establish signed provenance or immutable history.',
                   'Model comparison is small, human-localized and descriptive; no leaderboard or superiority claim.',
                   'Verifier is not an adversarial attestation system for hostile candidate Python.',
                   'Historical reproduction dependencies are not qualified as production services.',
                   'Public hosting, outside-user adoption and model research remain separate milestones.']}
    (EVIDENCE / 'manifest.json').write_text(json.dumps(output, indent=2) + '\n')
    print(f'Sealed {len(sources)} source files and {len(evidence)} evidence files.')


if __name__ == '__main__':
    main()
