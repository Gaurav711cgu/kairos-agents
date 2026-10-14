"""Qualify a bounded fresh-case study without model execution or historical writes.

References and test patches live in an isolated hidden runtime namespace. Source
entry files are human-localized; no reference-derived source line hints are emitted.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.sandbox import Workspace

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT
PARENT_RUNTIME = ORIGINAL / '.runtime/investigations'
REPOSITORIES = ('django/django', 'pytest-dev/pytest', 'psf/requests')
PREFIXES = {'django/django': 'django/', 'pytest-dev/pytest': 'src/_pytest/', 'psf/requests': 'requests/'}
# These are the only Requests cases without a model attempt in the frozen data.
# Retrying their documented preflight exclusions is explicit, never silent.
PREFLIGHT_RETRIES = {'psf__requests-1724', 'psf__requests-2317'}
CAPACITY = 6 * 1024**3
RESERVE = 4 * 1024**3
MAX_ARCHIVE = 80 * 1024**2


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def save(path: Path, value, *, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = encoded(value)
    if immutable:
        with path.open('xb') as target:
            target.write(data)
    else:
        path.write_bytes(data)


def storage_guard(parent: Path, projected=0):
    size = sum(p.stat().st_size for p in parent.rglob('*') if p.is_file() and not p.is_symlink())
    free = shutil.disk_usage(parent).free
    if size + projected > CAPACITY:
        raise ValueError(f'Global investigation storage budget exceeded: {size} + {projected} > {CAPACITY}')
    if free - projected < RESERVE:
        raise ValueError(f'Global free-space reserve would fall below {RESERVE} bytes')
    return {'parent_bytes': size, 'free_bytes': free, 'budget_bytes': CAPACITY, 'reserve_bytes': RESERVE}


def scope(row):
    paths = [line[6:] for line in row['patch'].splitlines() if line.startswith('+++ b/')]
    changed = sum(1 for line in row['patch'].splitlines() if line[:1] in ('+', '-') and not line.startswith(('+++', '---')))
    prefix = PREFIXES[row['repo']]
    if not paths or len(set(paths)) > 3 or changed > 200:
        raise ValueError('Maintainer repair exceeds three-file/200-line source-only scope')
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not name.startswith(prefix) or not name.endswith('.py'):
            raise ValueError('Maintainer repair escapes approved Python source prefix')
    return paths, prefix, changed


def test_paths(row):
    paths = [line[6:] for line in row['test_patch'].splitlines() if line.startswith('+++ b/')]
    if not paths or any(PurePosixPath(p).is_absolute() or '..' in PurePosixPath(p).parts or not p.endswith('.py') for p in paths):
        raise ValueError('Hidden regression patch does not identify bounded Python test modules')
    return sorted(set(paths))


def added_test_selectors(row, source: Path):
    """Inspect only hidden test material, never the reference repair, for omitted tests."""
    names = set(re.findall(r'^\+\s*(?:async\s+)?def (test_\w+)\(', row['test_patch'], re.MULTILINE))
    if not names:
        return []
    with tempfile.TemporaryDirectory(prefix='kairos-hidden-test-localization-') as temporary:
        target = Path(temporary) / 'source'
        shutil.copytree(source, target, symlinks=True)
        result = subprocess.run(['git', 'apply', '-'], cwd=target, input=row['test_patch'], text=True, capture_output=True, timeout=10)
        if result.returncode:
            raise ValueError('Hidden regression patch cannot be installed on original source')
        selectors = []
        for name in test_paths(row):
            tree = ast.parse((target / name).read_text())
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
                    selectors.append(name + '::' + node.name)
                elif isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name in names:
                            selectors.append(name + '::' + node.name + '::' + method.name)
        if not selectors:
            raise ValueError('Added hidden test functions could not be independently collected')
        return sorted(set(selectors))


def verifier(row, source: Path):
    regression = json.loads(row['FAIL_TO_PASS'])
    existing = json.loads(row['PASS_TO_PASS'])
    if not regression:
        raise ValueError('Dataset has no behavioral regression declarations')
    if row['repo'] == 'django/django':
        modules = [name[6:-3].replace('/', '.') for name in test_paths(row) if name.startswith('tests/') and not name.endswith('__init__.py')]
        if not modules:
            raise ValueError('No Django regression modules')
        argv = ['python', 'tests/runtests.py', *modules, '--parallel=1', '--verbosity=2']
        script = (
            'import subprocess,sys,re,json\n'
            f'p=subprocess.run({argv!r},capture_output=True,text=True)\n'
            'text=p.stdout+p.stderr\nprint(p.stdout);print(p.stderr,file=sys.stderr)\n'
            "m=re.search(r'Ran (\\d+) tests?',text)\n"
            f'expected={regression!r}\n'
            "reports={}\nfor item in expected:\n match=re.search(re.escape(item)+r'[^\\n]*?\\.\\.\\. (ok|FAIL|ERROR|skipped[^\\n]*)',text)\n if match:reports[item]=match.group(1)\n"
            "finished=bool(m) and int(m.group(1))>0 and len(reports)==len(expected)\n"
            "failed=[k for k,v in reports.items() if v in ('FAIL','ERROR')]\n"
            "passed=[k for k,v in reports.items() if v=='ok']\n"
            "summary={'tests_run':int(m.group(1)) if m else 0,'execution_complete':finished,'complete':finished and p.returncode==0 and len(passed)==len(expected),'regression_failed':failed,'regression_passed':passed}\n"
            "print('KAIROS_VERIFIER_RESULT '+json.dumps(summary))\nsys.exit(p.returncode if finished else 126)\n"
        )
        return script, {'test_modules': modules, 'declared_regressions': regression, 'omissions': [], 'completion': 'All declared regression statuses and final unittest count required'}
    added = added_test_selectors(row, source)
    omissions = []
    if row['repo'] == 'pytest-dev/pytest':
        # Some historical dataset node IDs are truncated at spaces. Collect full
        # changed test modules instead of silently accepting incomplete selectors.
        selected = test_paths(row)
        required = added or regression
        bootstrap = (
            "import sys,types\nsys.path.insert(0,'/workspace/src')\n"
            f"v=types.ModuleType('_pytest._version');v.version={row['version']!r};v.version_tuple=tuple(int(n) for n in v.version.split('.'));sys.modules['_pytest._version']=v\n"
            'import _pytest;_pytest._version=v\n'
        )
    else:
        # The server is local. Tests with hard-coded external requests cannot run
        # under the mandatory network-none verifier and are omitted explicitly.
        nonhermetic = {'test_requests_history_is_saved', 'test_auth_is_stripped_on_redirect_off_host'}
        selected = []
        for identifier in list(dict.fromkeys(regression + existing[:20] + added)):
            if identifier.rsplit('::', 1)[-1] in nonhermetic:
                omissions.append({'test': identifier, 'reason': 'Hard-coded external network request; runtime network is disabled'})
            else:
                selected.append(identifier)
        selected.sort()  # Match normal unittest order; legacy netrc test mutates globals.
        required = added or [i for i in regression if i in selected]
        bootstrap = (
            'import os,threading\nfrom httpbin import app\nfrom werkzeug.serving import make_server\n'
            "server=make_server('127.0.0.1',8765,app,threaded=True)\nthreading.Thread(target=server.serve_forever,daemon=True).start()\nos.environ['HTTPBIN_URL']='http://127.0.0.1:8765/'\n"
        )
    if not selected or not required:
        raise ValueError('No hermetic regression test remains')
    script = bootstrap + (
        'import pytest,json\n'
        'class Report:\n'
        ' def __init__(self):self.passed=set();self.failed=set();self.finished=set();self.collected=set();self.collection_errors=[]\n'
        ' def pytest_collection_finish(self,session):self.collected={item.nodeid for item in session.items}\n'
        ' def pytest_collectreport(self,report):\n  if report.failed:self.collection_errors.append(report.nodeid)\n'
        ' def pytest_runtest_logreport(self,report):\n  if report.when=="call" and report.passed:self.passed.add(report.nodeid)\n  if report.failed:self.failed.add(report.nodeid)\n  if report.when=="teardown":self.finished.add(report.nodeid)\n'
        f'p=Report()\ncode=pytest.main({["-q", "-p", "no:cacheprovider", *selected]!r},plugins=[p])\n'
        f'required={required!r}\n'
        'def matches(selector,node):return node==selector or node.startswith(selector+"[")\n'
        'seen=all(any(matches(selector,node) for node in p.collected) for selector in required)\n'
        'finished=bool(p.collected) and p.collected.issubset(p.finished) and not p.collection_errors and seen\n'
        'regression_failed=sorted(node for node in p.failed if any(matches(s,node) for s in required))\n'
        'regression_passed=all(any(matches(s,node) for node in p.passed) for s in required)\n'
        'complete=finished and code==0 and not p.failed and regression_passed\n'
        "print('KAIROS_VERIFIER_RESULT '+json.dumps({'tests_run':len(p.finished),'collected':len(p.collected),'execution_complete':finished,'complete':complete,'regression_failed':regression_failed,'regression_passed':regression_passed,'failed':sorted(p.failed),'collection_errors':p.collection_errors}))\n"
        'raise SystemExit(0 if complete else code or 126)\n'
    )
    return script, {'selected': selected, 'declared_regressions': regression, 'required_regressions': required, 'added_hidden_tests': added, 'omissions': omissions, 'completion': 'Every collected selected test must finish; all required regressions must be collected and pass after repair'}


def summary(result):
    markers = re.findall(r'KAIROS_VERIFIER_RESULT (\{[^\n]+\})', result.get('stdout', '') + result.get('stderr', ''))
    return json.loads(markers[-1]) if markers else {}


def plan(rows, original: Path):
    history = {}
    def remember(identifier, reason):
        history.setdefault(identifier, []).append(reason)
    for row in json.loads((original / 'cases/provenance.json').read_text())['records']:
        remember(row['instance_id'], 'Build003 provenance candidate')
    for case in json.loads((original / 'cases/investigations.json').read_text())['cases']:
        remember(case['id'], 'Previously registered/attempted case')
    for path in sorted((original / 'evidence/build004/qualification').glob('*.json')):
        remember(path.stem, 'Build004 qualification candidate')
    for release in ('build003', 'build004'):
        for path in sorted((original / 'evidence' / release).glob('*qualification*.json')):
            data = json.loads(path.read_text())
            for item in data.get('exclusions', []):
                if item.get('id'):
                    remember(item['id'], release + ' prior exclusion: ' + item.get('reason', ''))
    selected = {}
    exclusions = []
    retries = []
    for repo in REPOSITORIES:
        candidates = []
        for row in sorted((r for r in rows if r['repo'] == repo), key=lambda r: r['instance_id']):
            identifier = row['instance_id']
            if identifier in history and identifier not in PREFLIGHT_RETRIES:
                exclusions.append({'id': identifier, 'reason': 'Historical candidate excluded before model execution', 'history': history[identifier]})
                continue
            if identifier in PREFLIGHT_RETRIES:
                active_ids = {c['id'] for c in json.loads((original / 'cases/investigations.json').read_text())['cases']}
                if identifier in active_ids:
                    raise ValueError('Explicit preflight retry unexpectedly became an active/attempted case')
                retries.append({'id': identifier, 'reason': 'Explicit retry of unattempted preflight exclusion; only remaining unattempted Requests records', 'history': history.get(identifier, [])})
            candidates.append(identifier)
            if len(candidates) == 8:
                break
        selected[repo] = candidates
    return {'version': 'qualification-plan-v1', 'target_per_repository': 2, 'maximum_candidates_per_repository': 8, 'ordering': 'instance ID ascending', 'repositories': list(REPOSITORIES), 'candidate_ids': selected, 'historical_exclusions': exclusions, 'explicit_preflight_retries': retries, 'split': 'validation only; development remains frozen older cases', 'source_hints': 'Human-localized entry files only; no reference-derived entry lines', 'contamination': 'Public historical cases may have appeared in model training'}


def prepare_source(row, directory: Path, parent: Path):
    if directory.exists():
        prior = ROOT / 'evidence/build006/qualification' / (row['instance_id'] + '.json')
        receipt = json.loads(prior.read_text()) if prior.exists() else {}
        case = receipt.get('case', {})
        source = directory / 'source'
        if case.get('revision') != row['base_commit'] or not source.is_dir() or tree_hash(source) != case.get('source_digest'):
            raise ValueError('Existing qualification source lacks matching immutable provenance')
        return source, {**receipt.get('source', {}), 'reused_original_tree': True}
    directory.mkdir(parents=True, exist_ok=False)
    archive = directory / 'source.tar.gz'
    storage_guard(parent, MAX_ARCHIVE * 3)
    url = 'https://codeload.github.com/' + row['repo'] + '/tar.gz/' + row['base_commit']
    with urllib.request.urlopen(url, timeout=60) as response, archive.open('xb') as target:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_ARCHIVE:
                raise ValueError('Source archive exceeds 80 MiB bounded download')
            target.write(chunk)
    source = directory / 'source'
    source.mkdir()
    with tarfile.open(archive) as files:
        members = []
        expanded = 0
        for member in files.getmembers():
            parts = member.name.split('/', 1)
            if len(parts) != 2 or not parts[1]:
                continue
            member.name = parts[1]
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.islnk() or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Source archive contains traversal, hard links or special files')
            # tarfile's data filter independently rejects escaping symbolic links.
            if member.issym() and PurePosixPath(member.linkname).is_absolute():
                raise ValueError('Source archive contains an absolute symbolic link')
            expanded += member.size
            if expanded > MAX_ARCHIVE * 3:
                raise ValueError('Expanded source exceeds 240 MiB safety bound')
            members.append(member)
        storage_guard(parent, expanded)
        files.extractall(source, members=members, filter='data')
    archive_sha = sha(archive)
    archive.unlink()  # Immutable source digest binds extraction; avoid duplicate persistent archive.
    return source, {'source_url': url, 'archive_sha256': archive_sha, 'downloaded_bytes': total, 'expanded_bytes': expanded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Run Docker baseline/reference checks after freezing the candidate plan')
    parser.add_argument('--original', type=Path, default=ORIGINAL)
    parser.add_argument('--dependency-revision', choices=['original', 'toml', 'toml-reuse'], default='original')
    args = parser.parse_args()
    parent = args.original / '.runtime/investigations'
    runtime = parent / 'study006'
    out = ROOT / 'evidence/build006' / ('qualification-' + args.dependency_revision if args.dependency_revision != 'original' else '')
    rows_path = parent / 'study004/records.json'
    rows = json.loads(rows_path.read_text())
    frozen = {**plan(rows, args.original), 'dataset_sha256': sha(rows_path)}
    plan_path = out / 'qualification-plan.json'
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != frozen:
            raise ValueError('Frozen qualification plan differs; historical selection will not be overwritten')
    else:
        save(plan_path, frozen, immutable=True)
    print('Frozen candidates:', json.dumps(frozen['candidate_ids']), flush=True)
    if not args.execute:
        print('Plan only. Docker/source downloads/model execution were not started.', flush=True)
        return
    storage_guard(parent)
    runtime.mkdir(exist_ok=True)
    images = {}
    for repo in REPOSITORIES:
        tag = 'kairos-investigation-django:build003' if repo == 'django/django' else ('kairos-investigation-study:build004-pytest' if repo == 'pytest-dev/pytest' else 'kairos-investigation-study:build004')
        if repo == 'pytest-dev/pytest' and args.dependency_revision != 'original':
            tag = 'kairos-investigation-pytest:build006'
        identifier = subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'], text=True).strip()
        images[repo] = {'tag': tag, 'id': identifier}
    images_path = out / 'qualification-images.json'
    image_record = {'version': 'qualification-images-v1', 'images': images, 'runtime_network': 'none', 'user': '10001:10001', 'memory': '1g', 'cpus': 2, 'timeout_seconds': 120}
    if images_path.exists() and json.loads(images_path.read_text()) != image_record:
        raise ValueError('Qualification images changed after freeze')
    if not images_path.exists():
        save(images_path, image_record, immutable=True)
    index = {row['instance_id']: row for row in rows}
    cases, receipts = [], []
    for repository in REPOSITORIES:
        accepted = 0
        for identifier in frozen['candidate_ids'][repository]:
            if accepted == 2:
                break
            row = index[identifier]
            receipt_path = out / 'qualification' / (identifier + '.json')
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
            else:
                directory = runtime / 'cases' / identifier
                try:
                    paths, prefix, changed = scope(row)
                    source, source_receipt = prepare_source(row, directory, parent)
                    script, test_scope = verifier(row, source)
                    # All scope choices and exclusions are frozen before checks/model execution.
                    save(out / 'qualification' / (identifier + '-scope.json'), test_scope, immutable=True)
                    for name, text in [('reference.patch', row['patch']), ('test.patch', row['test_patch']), ('verify.py', script)]:
                        (directory / name).write_text(text)
                    case = {'id': identifier, 'title': row['problem_statement'].splitlines()[0], 'issue': row['problem_statement'], 'repository': repository, 'revision': row['base_commit'], 'source_url': 'https://github.com/' + repository + '/tree/' + row['base_commit'], 'issue_url': 'https://github.com/' + repository + '/pull/' + identifier.rsplit('-', 1)[1], 'entry_files': paths, 'approved_prefix': prefix, 'split': 'validation', 'provenance': 'Build006 fresh model-unattempted SWE-bench Verified case. Human-localized entry files only; no reference-derived line windows. Explicit preflight retries and hermetic verification omissions are recorded separately. Public training contamination possible.', 'image': images[repository]['id'], 'qualified': True, 'command': ['python', '/verification/verify.py'], 'source_digest': tree_hash(source), 'reference_digest': sha(directory / 'reference.patch'), 'verification_digest': hashlib.sha256((row['test_patch'] + script).encode()).hexdigest()}
                    registry_path = runtime / 'qualification-registry.json'
                    save(registry_path, {'version': 'repository-cases-v1', 'cases': [case]})
                    workspace = Workspace(CaseRegistry(registry_path, runtime), case)
                    try:
                        baseline = workspace.checks()
                        workspace.propose(row['patch'])
                        reference = workspace.checks()
                    finally:
                        workspace.close()
                    before, after = summary(baseline), summary(reference)
                    qualified = bool(not baseline['passed'] and not baseline['environment_error'] and baseline.get('returncode') not in (124, 125, 126, 127) and before.get('execution_complete') is True and before.get('regression_failed') and reference['passed'] and after.get('complete') is True and after.get('tests_run', 0) > 0)
                    receipt = {'id': identifier, 'qualified': qualified, 'reason': None if qualified else 'Behavioral regression failure and complete reference repair were not both reproduced under the registered hermetic verifier', 'baseline': baseline, 'reference': reference, 'baseline_summary': before, 'reference_summary': after, 'case': case, 'source': source_receipt, 'patch_changed_lines': changed, 'test_scope': test_scope, 'explicit_preflight_retry': identifier in PREFLIGHT_RETRIES}
                except Exception as error:
                    receipt = {'id': identifier, 'qualified': False, 'reason': type(error).__name__ + ': ' + str(error)[:500], 'explicit_preflight_retry': identifier in PREFLIGHT_RETRIES}
                save(receipt_path, receipt, immutable=True)
            receipts.append(receipt)
            if receipt['qualified']:
                cases.append(receipt['case'])
                accepted += 1
            save(out / 'qualification-progress.json', {'complete': False, 'qualified': len(cases), 'receipts': [{'id': r['id'], 'qualified': r['qualified'], 'reason': r.get('reason')} for r in receipts]})
            print(identifier, receipt['qualified'], receipt.get('reason'), flush=True)
    counts = {repo: sum(c['repository'] == repo for c in cases) for repo in REPOSITORIES}
    complete = all(count == 2 for count in counts.values())
    manifest = {'version': 'repository-cases-v1', 'cases': cases, 'selection': {**frozen, 'qualified_by_repository': counts, 'complete': complete, 'status': 'qualified; no model execution', 'runtime': str(runtime)}}
    manifest_path = ROOT / ('cases/study006-' + args.dependency_revision + '.json' if args.dependency_revision != 'original' else 'cases/study006.json')
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Final study006 manifest already differs; refusing overwrite')
    if not manifest_path.exists():
        save(manifest_path, manifest, immutable=True)
    result = {'version': 'qualification006-v1', 'complete': complete, 'qualified': len(cases), 'qualified_by_repository': counts, 'shortfalls': {repo: 2 - count for repo, count in counts.items() if count < 2}, 'receipts': [str(out.relative_to(ROOT) / 'qualification' / (r['id'] + '.json')) for r in receipts], 'storage': storage_guard(parent), 'model_calls': 0, 'historical_files_overwritten': 0, 'validation_locked': complete, 'dependency_revision': args.dependency_revision}
    result_path = out / 'qualification.json'
    if result_path.exists() and json.loads(result_path.read_text()) != result:
        raise ValueError('Final qualification receipt differs; refusing overwrite')
    if not result_path.exists():
        save(result_path, result, immutable=True)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
