"""Verify isolated reviewer setup without printing private credential values."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import subprocess
import psycopg
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

def private_files_ignored(root: Path, files: list[Path]) -> bool:
    # Git's quiet mode accepts one pathname. Check every private file independently.
    return all(subprocess.run(['git', 'check-ignore', '--quiet', str(path)],
                              cwd=root, capture_output=True, check=False).returncode == 0
               for path in files)

def environment(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        if not key or key in values:
            raise ValueError('Duplicate or empty environment key')
        values[key] = value
    return values

def urls(value: object) -> set[str]:
    if isinstance(value, str):
        return {value.rstrip('/')} if value.startswith('http://') else set()
    if isinstance(value, dict):
        return set().union(*(urls(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(urls(item) for item in value)) if value else set()
    return set()

def verify(runtime: Path) -> dict:
    checks: dict[str, bool] = {}
    credential = runtime / 'identity.local.json'
    application = runtime / 'application.env'
    services = runtime / 'services.json'
    for name, file in [('identity', credential), ('application', application)]:
        checks[name + '_private_regular_file'] = (file.is_file() and not file.is_symlink()
            and stat.S_IMODE(file.stat().st_mode) == 0o600)
    if not all(checks.values()):
        return {'passed': False, 'checks': checks, 'error': 'Private reviewer setup files require mode 0600.'}
    try:
        identity = json.loads(credential.read_text())
        env = environment(application)
        public = json.loads(services.read_text())
        accounts = identity['accounts']
        populated = [item for item in accounts if item.get('role')]
        subjects = [item['subject'] for item in accounts]
        checks['unique_account_subjects'] = len(subjects) == len(set(subjects)) and len(subjects) >= 3
        primary = {role: next((item for item in populated if item['role'] == role), None)
                   for role in ('admin', 'viewer', 'operator')}
        checks['required_roles'] = all(primary.values())
        if checks['required_roles']:
            checks['viewer_and_admin_share_workspace'] = primary['admin']['tenant_id'] == primary['viewer']['tenant_id']
            checks['operator_uses_other_workspace'] = primary['operator']['tenant_id'] != primary['admin']['tenant_id']
        checks['account_passwords_generated'] = all(isinstance(item.get('password'), str)
            and len(item['password']) >= 20 for item in accounts)
        database = urlparse(env['DATABASE_URL'])
        checks['isolated_database_port'] = database.hostname == '127.0.0.1' and database.port == 55434
        setup = environment(runtime / 'migration.env')
        test_database = urlparse(setup['TEST_DATABASE_URL'])
        checks['matching_database_target'] = (database.hostname,database.port,database.path) == (test_database.hostname,test_database.port,test_database.path)
        checks['runtime_and_migration_roles_separate'] = database.username != test_database.username and setup.get('KAIROS_MIGRATION_DATABASE_URL') == setup['TEST_DATABASE_URL']
        checks['runtime_environment_excludes_owner_credentials'] = 'TEST_DATABASE_URL' not in env and 'KAIROS_MIGRATION_DATABASE_URL' not in env
        with psycopg.connect(env['DATABASE_URL'],connect_timeout=5) as connection:
            checks['runtime_lock_deadline'] = connection.execute('SHOW lock_timeout').fetchone()[0] == '2s'
            checks['runtime_statement_deadline'] = connection.execute('SHOW statement_timeout').fetchone()[0] == '15s'
            checks['runtime_no_schema_create'] = not connection.execute("SELECT has_schema_privilege(current_user,'public','CREATE')").fetchone()[0]
            checks['runtime_no_ledger_write'] = not connection.execute("SELECT has_table_privilege(current_user,'kairos_schema_migrations','UPDATE')").fetchone()[0]

        checks['oidc_mode'] = env.get('KAIROS_IDENTITY_MODE') == 'oidc'
        checks['isolated_oidc_issuer'] = env.get('KAIROS_OIDC_ISSUER') == 'http://127.0.0.1:8090/realms/kairos'
        checks['isolated_oidc_callback'] = env.get('KAIROS_OIDC_CALLBACK') == 'http://127.0.0.1:8310/api/auth/callback'
        checks['isolated_web_origin'] = env.get('KAIROS_WEB_ORIGIN') == 'http://127.0.0.1:3310'
        checks['isolated_cors_origin'] = env.get('KAIROS_CORS_ORIGINS') == 'http://127.0.0.1:3310'
        checks['explicit_live_mode'] = env.get('KAIROS_EVIDENCE_MODE') == 'live'
        for name in ('KAIROS_BLOB_DIR', 'KAIROS_INVESTIGATION_ROOT'):
            candidate = Path(env.get(name, '')).resolve()
            checks[name.lower() + '_isolated'] = candidate.is_relative_to(runtime) and candidate != runtime
        checks['inference_disabled'] = public.get('inference') is False
        checks['isolated_service_urls'] = {'http://127.0.0.1:3310', 'http://127.0.0.1:8310'}.issubset(urls(public))
        secrets = [item.get('password', '') for item in accounts]
        secrets += [value for key, value in env.items() if any(part in key for part in ('PASSWORD', 'SECRET'))]
        if identity.get('admin_password'):
            secrets.append(identity['admin_password'])
        public_text = services.read_text()
        checks['service_metadata_has_no_credentials'] = all(value not in public_text for value in secrets if len(value) >= 12)
        if runtime.is_relative_to(ROOT):
            in_private_tree = runtime.is_relative_to(ROOT / '.runtime')
            configured = '.runtime/' in (ROOT / '.gitignore').read_text().splitlines()
            checks['private_state_excluded_from_source'] = in_private_tree and configured
            if (ROOT / '.git').exists():
                checks['private_state_git_ignored'] = private_files_ignored(ROOT, [credential, application])
        else:
            checks['private_state_excluded_from_source'] = True
    except (KeyError, TypeError, ValueError, OSError, psycopg.Error) as error:
        return {'passed': False, 'checks': checks,
                'error': 'Reviewer runtime is incomplete or invalid (' + type(error).__name__ + ').'}
    return {'passed': all(checks.values()), 'checks': checks,
            'method': 'Read-only preflight of CLI-generated isolated runtime; values are redacted.',
            'limits': 'Browser journeys separately verify actual identity and API behavior.'}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=Path(os.environ.get('KAIROS_REVIEWER_RUNTIME', ROOT / '.runtime/reviewer005')))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.runtime.resolve())
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    output = args.output or args.runtime / 'checks/private-runtime-preflight.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    os.chmod(output, 0o600)
    print(json.dumps({'passed': result['passed'], 'checks': result['checks']}))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
