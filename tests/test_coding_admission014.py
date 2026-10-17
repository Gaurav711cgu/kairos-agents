"""Isolated evidence fixtures never constitute admitted training data."""
import base64
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest
from scripts import coding_admission014 as admission
from scripts.coding_train014 import encoded, sha_file


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def fixture_bundle(root, monkeypatch, mutate=None):
    root.mkdir(exist_ok=True)
    row = {'instance_id': 'owner__repo-1', 'repository': 'owner/repo', 'source_commit': 'a' * 40,
           'source_digest': 'b' * 64, 'family_id': 'owner/repo#1',
           'input': {'issue': 'Fix the source', 'original_source': [], 'instruction': 'Edit source'},
           'assistant_target': {'action': 'propose_patch', 'edits': []}}
    issue_sha = admission.issue_digest(row['input']['issue'])
    exposure = {'exposures': [], 'reserved014_ids': [], 'exposed_issue_digests': []}
    monkeypatch.setattr(admission, 'EXPOSURE_SHA256', sha(exposure))
    scope = {'version': 'coding-selected-suite014-v1', 'regressions': ['tests/test_x.py::test_bad'],
             'existing': ['tests/test_x.py::test_ok'], 'selected': ['tests/test_x.py::test_bad', 'tests/test_x.py::test_ok'], 'omissions': []}
    case = {'dataset_instance_id': row['instance_id'], 'repository': row['repository'],
            'revision': row['source_commit'], 'source_digest': row['source_digest'],
            'issue': row['input']['issue'], 'image': 'sha256:' + 'c' * 64}
    screen = {'candidate_ids': [row['instance_id']], 'ledger': [{'instance_id': row['instance_id'],
              'repository': row['repository'], 'base_commit': row['source_commit'], 'issue_sha256': issue_sha}]}
    image = {'id': case['image']}
    identity = sha({'case': case, 'scope': scope, 'screen_sha256': sha(screen), 'image_receipt_sha256': sha(image)})
    binding = {'version': 'coding-qualification-binding014-v1', 'binding': identity, 'model_calls': 0, 'case': case, 'scope': scope}
    def capture(passed):
        summary = {'tests_run': 2, 'collected': 2, 'execution_complete': True, 'complete': passed,
                   'regression_failed': [] if passed else scope['regressions'],
                   'regression_passed': scope['regressions'] if passed else [],
                   'existing_required': 1, 'existing_passed': scope['existing'], 'skipped': [], 'collection_errors': []}
        text = 'KAIROS_VERIFIER_RESULT ' + json.dumps(summary) + '\n'
        def stream(value):
            data = value.encode()
            return {'bytes': len(data), 'observed_bytes': len(data), 'truncated': False,
                    'sha256': hashlib.sha256(data).hexdigest(), 'data': base64.b64encode(data).decode()}
        return {'binding': identity, 'stage': 'reference' if passed else 'baseline',
                'result': {'passed': passed, 'returncode': 0 if passed else 1, 'stdout': text, 'stderr': '',
                'raw_output': {'complete': True, 'encoding': 'base64', 'stdout': stream(text), 'stderr': stream('')}}}
    baseline, reference = capture(False), capture(True)
    qualification = {'version': 'coding-qualification014-v1', 'instance_id': row['instance_id'],
                     'binding': identity, 'image': case['image'], 'qualified': True, 'model_calls': 0,
                     'original_source_unchanged': True, 'checks_sha256': {'baseline': sha(baseline), 'reference': sha(reference)}}
    example = {k: deepcopy(row[k]) for k in ['instance_id', 'repository', 'source_commit', 'source_digest', 'input', 'assistant_target']}
    example.update(version='coding-action-example014-v1', qualification_receipt_sha256=sha(qualification), reference_derived_supervision=True)
    preparation = {'version': 'coding-action-preparation014-v1', 'instance_id': row['instance_id'],
                   'status': 'converted_not_admitted', 'model_calls': 0, 'source_unchanged': True,
                   'example_sha256': sha(example), 'input_sha256': sha(row['input']), 'target_sha256': sha(row['assistant_target']),
                   'rendered_patch_sha256': 'd' * 64}
    review_identity = {k: row[k] for k in ['instance_id', 'repository', 'source_commit', 'source_digest']}
    rights = {'version': 'coding-rights-review014-v1', **review_identity, 'issue_sha256': issue_sha,
              'approved_for_training': True, 'reviewer': 'fixture reviewer', 'reviewed_at': '2026-10-17',
              'materials': {name: {'license': 'fixture-license', 'provenance': 'isolated fixture', 'basis': 'isolated test only'}
                            for name in ['source', 'issue', 'reference_patch']}}
    family = {'version': 'coding-family-review014-v1', **review_identity, 'issue_sha256': issue_sha,
              'family_id': row['family_id'], 'near_duplicate_reviewed': True, 'reviewer': 'fixture reviewer',
              'reviewed_at': '2026-10-17', 'method': 'isolated fixture', 'rationale': 'isolated fixture only'}
    documents = dict(exposure=exposure, screen=screen, image=image, binding=binding, baseline=baseline,
                     reference=reference, qualification=qualification, example=example, preparation=preparation,
                     rights=rights, family=family)
    if mutate:
        mutate(documents, row)
    # Rebind dependent hashes: semantic checks must still reject invalid evidence.
    qualification['checks_sha256'] = {name: sha(documents[name]) for name in ['baseline', 'reference']}
    example['qualification_receipt_sha256'] = sha(qualification)
    preparation['example_sha256'] = sha(example)
    files = {}
    for name, document in documents.items():
        (root / (name + '.json')).write_bytes(encoded(document))
        files[sha(document)] = name + '.json'
    refs = {name: sha(documents[name]) for name in documents if name != 'exposure'}
    for name in ['qualification', 'rights', 'family']:
        row[name + '_receipt_sha256'] = refs[name]
    index = {'version': 'coding-admission-index014-v1', 'files': files,
             'exposure_sha256': sha(exposure), 'rows': {row['instance_id']: refs}}
    (root / 'index.json').write_bytes(encoded(index))
    corpus = {'train': [row], 'development': [], 'exposure_inventory_sha256': sha(exposure)}
    return corpus, sha(index)


def test_complete_evidence_graph_validates_without_execution(tmp_path, monkeypatch):
    corpus, index_sha = fixture_bundle(tmp_path, monkeypatch)
    result = admission.verify_admission_bundle(corpus, tmp_path, index_sha)
    assert result['verified_rows'] == 1
    assert result['admission_index_sha256'] == index_sha


@pytest.mark.parametrize('mutation', [
    lambda d, r: d['rights'].update(approved_for_training=False),
    lambda d, r: d['rights']['materials'].pop('issue'),
    lambda d, r: d['family'].update(family_id='unrelated'),
    lambda d, r: d['family'].update(near_duplicate_reviewed=False),
    lambda d, r: d['preparation'].update(status='rejected'),
    lambda d, r: d['example']['assistant_target'].update(action='final'),
    lambda d, r: r.update(source_commit='f' * 40),
    lambda d, r: d['binding']['case'].update(repository='wrong/repository'),
    lambda d, r: d['baseline']['result']['raw_output']['stdout'].update(data='corrupt!'),
    lambda d, r: d['reference']['result'].update(passed=False),
    lambda d, r: d['binding']['scope'].update(omissions=['missing test']),
    lambda d, r: d['exposure']['exposed_issue_digests'].append(admission.issue_digest(r['input']['issue'])),
    lambda d, r: d['exposure']['reserved014_ids'].append(r['instance_id']),
])
def test_rebound_invalid_evidence_still_rejects(tmp_path, monkeypatch, mutation):
    corpus, index_sha = fixture_bundle(tmp_path, monkeypatch, mutation)
    with pytest.raises(ValueError):
        admission.verify_admission_bundle(corpus, tmp_path, index_sha)


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'symlink', 'traversal', 'extra_row', 'extra_file'])
def test_package_integrity_and_membership(tmp_path, monkeypatch, failure):
    corpus, index_sha = fixture_bundle(tmp_path, monkeypatch)
    index = json.loads((tmp_path / 'index.json').read_bytes())
    if failure == 'missing':
        (tmp_path / 'rights.json').unlink()
    elif failure == 'corrupt':
        (tmp_path / 'rights.json').write_text('{}')
    elif failure == 'symlink':
        (tmp_path / 'rights.json').rename(tmp_path / 'other.json')
        (tmp_path / 'rights.json').symlink_to(tmp_path / 'other.json')
    else:
        if failure == 'traversal':
            index['files'][corpus['train'][0]['rights_receipt_sha256']] = '../secret.json'
        elif failure == 'extra_row':
            index['rows']['unrelated'] = index['rows'][corpus['train'][0]['instance_id']]
        else:
            (tmp_path / 'extra.json').write_text('{}')
            index['files'][sha({})] = 'extra.json'
        (tmp_path / 'index.json').write_bytes(encoded(index)); index_sha = sha(index)
    with pytest.raises(ValueError):
        admission.verify_admission_bundle(corpus, tmp_path, index_sha)


def test_runner_rejects_missing_evidence_before_output_or_model_loading(tmp_path):
    from scripts import coding_train014 as runner
    from tests.test_coding_train014 import corpus
    path = tmp_path / 'corpus.json'; path.write_bytes(encoded(corpus()))
    args = SimpleNamespace(corpus=path, corpus_sha256=sha_file(path), admission_directory=tmp_path / 'absent',
                           admission_index_sha256='a' * 64, output=tmp_path / 'output')
    with pytest.raises(ValueError):
        runner.run(args)
    assert not args.output.exists()


@pytest.mark.parametrize('failure', ['skipped', 'missing_regression', 'incomplete', 'false_success', 'lost_output'])
def test_check_content_not_success_flags_controls_admission(tmp_path, monkeypatch, failure):
    def change(documents, row):
        capture = documents['reference']
        result = capture['result']
        verdict = json.loads(result['stdout'].split(' ', 1)[1])
        if failure == 'skipped': verdict['skipped'] = ['tests/test_x.py::test_ok']
        elif failure == 'missing_regression': verdict['regression_passed'] = []
        elif failure == 'incomplete': verdict['execution_complete'] = False
        elif failure == 'false_success': verdict['complete'] = False
        else: result['raw_output']['complete'] = False
        text = 'KAIROS_VERIFIER_RESULT ' + json.dumps(verdict) + '\n'
        data = text.encode()
        result['raw_output']['stdout'].update(data=base64.b64encode(data).decode(), bytes=len(data),
            observed_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        # A separate friendly stdout value cannot override the original stream.
        result['stdout'] = 'All tests passed'
    corpus, index_sha = fixture_bundle(tmp_path, monkeypatch, change)
    with pytest.raises(ValueError):
        admission.verify_admission_bundle(corpus, tmp_path, index_sha)


def test_doctor_requires_evidence_bundle_even_with_structurally_valid_rows(tmp_path, monkeypatch, capsys):
    import sys
    from scripts import coding_train014 as runner
    from tests.test_coding_train014 import corpus
    path = tmp_path / 'corpus.json'; path.write_bytes(encoded(corpus()))
    monkeypatch.setattr(sys, 'argv', ['coding_train014', 'doctor', '--corpus', str(path), '--corpus-sha256', sha_file(path)])
    runner.main()
    assert json.loads(capsys.readouterr().out)['ready'] is False
