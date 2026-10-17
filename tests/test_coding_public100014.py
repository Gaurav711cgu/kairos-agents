"""Public-supervision fixtures are isolated tests, never training evidence."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest
from scripts import coding_public100014 as study
from scripts import coding_train014 as runner


def example(i):
    return {'instance_id': 'fixture-' + str(i), 'repository': 'fixture/repo' + str(i % 3),
            'family_id': 'fixture-family-' + str(i), 'source_commit': f'{i:040x}', 'source_digest': f'{i:064x}',
            'input': {'issue': 'Repair fixture behavior ' + str(i), 'instruction': 'Replace original source lines',
                      'original_source': [{'source_id': 'S' + f'{i:012x}', 'path': 'package/value.py',
                        'start_line': 1, 'end_line': 1, 'numbered_original_source': '1: value = 0\n'}]},
            'assistant_target': {'action': 'propose_patch', 'edits': [{'source_id': 'S' + f'{i:012x}',
                'start_line': 1, 'end_line': 1, 'new': 'value = ' + str(i + 1) + '\n'}]}}


def corpus():
    train = [example(i) for i in range(100)]
    evaluation = [{**{key: example(i)[key] for key in ('instance_id', 'repository', 'family_id', 'source_commit', 'source_digest')},
                   'issue_sha256': study.issue_digest(example(i)['input']['issue'])} for i in range(110, 130)]
    return {'version': study.VERSION, 'training_ready': True, 'protocol_sha256': study.digest(study.PROTOCOL),
            'exposure_inventory_sha256': study.EXPOSURE_SHA256, 'train': train,
            'development': [example(i) for i in range(100, 110)], 'evaluation': evaluation,
            'training_audit_ids': study.audit_ids(train)}


def test_distinct_100_10_20_corpus_and_seeded_audit():
    data = corpus()
    assert study.admit_corpus(data) is data
    assert study.audit_ids(list(reversed(data['train']))) == data['training_audit_ids']
    with pytest.raises(ValueError):
        runner.admit_corpus(data)


@pytest.mark.parametrize('failure', ['count', 'protocol', 'audit', 'family', 'target', 'issue', 'source',
                                    'repository_cap', 'repository_diversity', 'evaluation_label', 'range', 'protected'])
def test_bad_or_overlapping_corpora_are_rejected(failure):
    data = corpus()
    if failure == 'count': data['train'].pop()
    elif failure == 'protocol': data['protocol_sha256'] = '0' * 64
    elif failure == 'audit': data['training_audit_ids'] = [r['instance_id'] for r in data['train'][:10]]
    elif failure == 'family': data['evaluation'][0]['family_id'] = data['train'][0]['family_id']
    elif failure == 'target': data['train'][1]['assistant_target'] = deepcopy(data['train'][0]['assistant_target'])
    elif failure == 'issue': data['evaluation'][0]['issue_sha256'] = study.issue_digest(data['train'][0]['input']['issue'])
    elif failure == 'source':
        data['train'][3]['source_commit'] = data['train'][0]['source_commit']
    elif failure == 'repository_cap':
        for row in data['train'][:51]: row['repository'] = 'fixture/overrepresented'
    elif failure == 'repository_diversity':
        for i, row in enumerate(data['train']): row['repository'] = 'fixture/repo' + str(i % 2)
    elif failure == 'evaluation_label': data['evaluation'][0]['assistant_target'] = {}
    elif failure == 'range': data['train'][0]['assistant_target']['edits'][0]['end_line'] = 2
    elif failure == 'protected': data['train'][0]['input']['original_source'][0]['path'] = '../secret.py'
    with pytest.raises(ValueError): study.admit_corpus(data)


def bundle(root, monkeypatch, mutate=None):
    data = corpus()
    exposure = {'exposures': [], 'reserved014_ids': [], 'exposed_issue_digests': []}
    exposure_sha = study.digest(exposure)
    monkeypatch.setattr(study, 'EXPOSURE_SHA256', exposure_sha)
    data['exposure_inventory_sha256'] = exposure_sha
    prior_training={'version':'coding-data-screen014-v1','candidate_ids':[]}
    screen_sha=study.digest(prior_training)
    monkeypatch.setattr(study,'TRAINING_SCREEN_SHA256',screen_sha)
    documents = {exposure_sha: exposure,screen_sha:prior_training}
    rows = {}
    dataset = {}
    for row in data['train'] + data['development']:
        raw = {'instance_id': row['instance_id'], 'repo': row['repository'], 'base_commit': row['source_commit'],
               'problem_statement': row['input']['issue'],
               'patch': 'diff --git a/package/value.py b/package/value.py\n--- a/package/value.py\n+++ b/package/value.py\n@@ -1 +1 @@\n-value = 0\n+value = 1\n'}
        dataset[row['instance_id']] = raw
        identity = {key: row[key] for key in ('instance_id', 'repository', 'source_commit', 'source_digest')}
        reviews = {name: {'version': 'coding-' + name + '-review014-v1', **identity,
                    'issue_sha256': study.issue_digest(row['input']['issue']), 'reviewer': 'isolated fixture',
                    'reviewed_at': '2026-10-17'} for name in ('rights', 'family')}
        reviews['rights'].update(approved_for_training=True, materials={name: {'license': 'fixture', 'provenance': 'fixture', 'basis': 'isolated test'} for name in ('source', 'issue', 'reference_patch')})
        reviews['family'].update(family_id=row['family_id'], near_duplicate_reviewed=True, method='fixture', rationale='fixture')
        reviews['example'] = {**deepcopy(row), 'version': 'coding-action-example014-v1', 'reference_derived_supervision': True}
        patch_sha = hashlib.sha256(raw['patch'].encode()).hexdigest()
        reviews['supervision'] = {'version': 'coding-public-supervision014-v1', 'dataset': study.DATASET,
            'revision': study.REVISION, 'dataset_sha256': study.SHA256, 'row_sha256': study.digest(raw),
            'reference_patch_sha256': patch_sha, 'verification_basis': 'dataset_authors; not locally reproduced'}
        reviews['preparation'] = {'version': 'coding-action-preparation014-v1', 'instance_id': row['instance_id'],
            'status': 'converted_not_admitted', 'source_unchanged': True, 'model_calls': 0,
            'example_sha256': study.digest(reviews['example']), 'input_sha256': study.digest(row['input']),
            'target_sha256': study.digest(row['assistant_target']), 'reference_patch_sha256': patch_sha,
            'rendered_patch_sha256': 'a' * 64}
        if mutate: mutate(row, reviews, exposure)
        references = {name: study.digest(value) for name, value in reviews.items()}
        documents.update({references[name]: value for name, value in reviews.items()})
        rows[row['instance_id']] = references
    # The nested captured-verifier graph has its own real tests. This fixture
    # isolates the new dispatch/binding layer and never simulates a GPU fit.
    required = set(data['training_audit_ids']) | {r['instance_id'] for r in data['development'] + data['evaluation']}
    local_rows = [deepcopy(row) for row in data['train'] + data['development'] if row['instance_id'] in required]
    local_rows += [example(i) for i in range(110, 130)]
    local = {'train': local_rows, 'development': [], 'exposure_inventory_sha256': exposure_sha}
    (root / 'independent').mkdir()
    (root / 'independent' / 'corpus.json').write_bytes(runner.encoded(local))
    (root / 'independent' / 'admission').mkdir()
    index = {'version': 'coding-public100-index014-v1', 'rows': rows, 'files': {},
             'independent': {'corpus': 'independent/corpus.json', 'corpus_sha256': study.digest(local),
                             'directory': 'independent/admission', 'index_sha256': 'b' * 64}}
    for key, document in documents.items():
        name = key + '.json'; (root / name).write_bytes(runner.encoded(document)); index['files'][key] = name
    (root / 'index.json').write_bytes(runner.encoded(index))
    monkeypatch.setattr(study, 'dataset_rows', lambda path: dataset)
    calls = []
    def independent_graph(local, directory, sha):
        calls.append((local, directory, sha))
        return {'verified_rows': len(local['train']) + len(local['development']), 'verified_files': 400}
    monkeypatch.setattr(study, 'verify_admission_bundle', independent_graph)
    return data, study.digest(index), calls


def test_public_and_independent_verification_levels_remain_distinct(tmp_path, monkeypatch):
    data, sha, calls = bundle(tmp_path, monkeypatch)
    result = study.verify_bundle(data, tmp_path, sha, tmp_path / 'fixture-dataset')
    assert result['public_training_rows'] == 100
    assert result['independently_verified_training_rows'] == 10
    assert result['independently_verified_evaluation_rows'] == 20
    assert result['training_started'] is False
    assert len(calls) == 1 and len(calls[0][0]['train']) == 40


@pytest.mark.parametrize('failure', ['rights', 'family', 'provenance', 'conversion', 'source', 'missing', 'corrupt', 'local_membership', 'local_identity'])
def test_invalid_rebound_receipts_fail_before_independent_dispatch(tmp_path, monkeypatch, failure):
    def mutate(row, reviews, exposure):
        if row['instance_id'] != 'fixture-0': return
        if failure == 'rights': reviews['rights']['approved_for_training'] = False
        elif failure == 'family': reviews['family']['family_id'] = 'unrelated'
        elif failure == 'provenance': reviews['supervision']['verification_basis'] = 'locally reproduced'
        elif failure == 'conversion': reviews['preparation']['reference_patch_sha256'] = '0' * 64
        elif failure == 'source': reviews['example']['source_commit'] = 'f' * 40
    data, sha, calls = bundle(tmp_path, monkeypatch, mutate)
    index = json.loads((tmp_path / 'index.json').read_bytes())
    if failure in {'missing', 'corrupt'}:
        path = tmp_path / index['files'][index['rows']['fixture-0']['rights']]
        if failure == 'missing': path.unlink()
        else: path.write_text('{}')
    if failure.startswith('local_'):
        path = tmp_path / 'independent' / 'corpus.json'
        local = json.loads(path.read_bytes())
        if failure == 'local_membership': local['train'].pop()
        else: local['train'][0]['source_commit'] = 'f' * 40
        path.write_bytes(runner.encoded(local)); index['independent']['corpus_sha256'] = study.digest(local)
        (tmp_path / 'index.json').write_bytes(runner.encoded(index)); sha = study.digest(index)
    with pytest.raises(ValueError): study.verify_bundle(data, tmp_path, sha, tmp_path / 'fixture-dataset')
    assert not calls


def test_nested_independent_failure_is_not_promoted_to_ready(tmp_path, monkeypatch):
    data, sha, _ = bundle(tmp_path, monkeypatch)
    def rejected(*args): raise ValueError('Captured regression did not pass')
    monkeypatch.setattr(study, 'verify_admission_bundle', rejected)
    with pytest.raises(ValueError, match='regression'): study.verify_bundle(data, tmp_path, sha, tmp_path / 'fixture-dataset')


def test_unpinned_dataset_fails_without_importing_arrow(tmp_path):
    dataset = tmp_path / 'not-the-dataset'; dataset.write_bytes(b'not parquet')
    with pytest.raises(ValueError, match='dataset bytes'): study.dataset_rows(dataset)


def test_incomplete_study_fails_before_output_or_model_import(tmp_path):
    data = corpus(); data['train'].pop()
    path = tmp_path / 'corpus.json'; path.write_bytes(runner.encoded(data))
    args = SimpleNamespace(study='public100', profile='14B', corpus=path, corpus_sha256=runner.sha_file(path),
                           admission_directory=tmp_path / 'missing', admission_index_sha256='a' * 64,
                           output=tmp_path / 'output')
    with pytest.raises(ValueError, match='100/10/20'): runner.run(args)
    assert not args.output.exists()


def test_public_study_cannot_silently_switch_to_smaller_model(tmp_path):
    path = tmp_path / 'corpus.json'; path.write_bytes(runner.encoded(corpus()))
    args = SimpleNamespace(study='public100', profile='7B', corpus=path, corpus_sha256=runner.sha_file(path))
    with pytest.raises(ValueError, match='14B'): runner.admitted_inputs(args)


def test_prior_training_only_candidates_cannot_become_evaluation(tmp_path,monkeypatch):
    data,sha,calls=bundle(tmp_path,monkeypatch)
    index=json.loads((tmp_path/'index.json').read_bytes())
    old=study.TRAINING_SCREEN_SHA256
    screen={'version':'coding-data-screen014-v1','candidate_ids':[data['evaluation'][0]['instance_id']]}
    new=study.digest(screen);path=tmp_path/(new+'.json');path.write_bytes(runner.encoded(screen))
    index['files'].pop(old);index['files'][new]=path.name
    monkeypatch.setattr(study,'TRAINING_SCREEN_SHA256',new)
    (tmp_path/'index.json').write_bytes(runner.encoded(index))
    with pytest.raises(ValueError,match='training-only'):
        study.verify_bundle(data,tmp_path,study.digest(index),tmp_path/'fixture-dataset')
    assert not calls


def test_protected_test_files_cannot_be_training_source():
    data=corpus();data['train'][0]['input']['original_source'][0]['path']='tests/test_value.py'
    with pytest.raises(ValueError,match='Protected'):study.admit_corpus(data)


def test_candidate_plan_is_order_independent_and_not_admitted():
    raw={};ledger=[];training=[]
    for i in range(150):
        repository=('fixture/repo'+str(i%3)) if i<100 else ('getmoto/moto' if i%2 else 'pydantic/pydantic')
        value={'instance_id':'case-'+str(i).zfill(4),'repo':repository,'base_commit':f'{i:040x}'}
        raw[value['instance_id']]=value
        item={'instance_id':value['instance_id'],'repository':repository,'base_commit':value['base_commit'],
              'row_sha256':study.digest(value),'issue_sha256':f'{i:064x}'}
        if i<100:training.append(value['instance_id'])
        else:item['reason']='Predeclared candidate inspection bound reached'
        ledger.append(item)
    screen={'version':'coding-data-screen014-v1','dataset_sha256':study.SHA256,'ledger':ledger,'candidate_ids':training}
    first=study.candidate_plan(screen,raw)
    screen['ledger'].reverse();screen['candidate_ids'].reverse()
    assert study.candidate_plan(screen,raw)==first
    assert first['counts']=={'train':100,'development':10,'evaluation':20}
    assert first['training_ready'] is False and first['model_calls']==0
    raw[training[0]]['base_commit']='f'*40
    with pytest.raises(ValueError,match='row differs'):study.candidate_plan(screen,raw)


def test_build_bundle_produces_fully_verified_admission_bundle(tmp_path, monkeypatch):
    data = corpus()
    exposure = {'exposures': [], 'reserved014_ids': [], 'exposed_issue_digests': []}
    exposure_sha = study.digest(exposure)
    monkeypatch.setattr(study, 'EXPOSURE_SHA256', exposure_sha)
    data['exposure_inventory_sha256'] = exposure_sha
    prior_training = {'version': 'coding-data-screen014-v1', 'candidate_ids': []}
    screen_sha = study.digest(prior_training)
    monkeypatch.setattr(study, 'TRAINING_SCREEN_SHA256', screen_sha)

    dataset = {}
    reviews_by_id = {}
    for row in data['train'] + data['development']:
        raw = {'instance_id': row['instance_id'], 'repo': row['repository'], 'base_commit': row['source_commit'],
               'problem_statement': row['input']['issue'],
               'patch': 'diff --git a/package/value.py b/package/value.py\n--- a/package/value.py\n+++ b/package/value.py\n@@ -1 +1 @@\n-value = 0\n+value = 1\n'}
        dataset[row['instance_id']] = raw
        identity = {key: row[key] for key in ('instance_id', 'repository', 'source_commit', 'source_digest')}
        rights = {'version': 'coding-rights-review014-v1', **identity,
                  'issue_sha256': study.issue_digest(row['input']['issue']), 'reviewer': 'test reviewer',
                  'reviewed_at': '2026-10-17', 'approved_for_training': True,
                  'materials': {name: {'license': 'fixture', 'provenance': 'fixture', 'basis': 'test'} for name in ('source', 'issue', 'reference_patch')}}
        family = {'version': 'coding-family-review014-v1', **identity,
                  'issue_sha256': study.issue_digest(row['input']['issue']), 'reviewer': 'test reviewer',
                  'reviewed_at': '2026-10-17', 'family_id': row['family_id'], 'near_duplicate_reviewed': True,
                  'method': 'fixture', 'rationale': 'fixture'}
        reviews_by_id[row['instance_id']] = {'rights': rights, 'family': family}

    monkeypatch.setattr(study, 'dataset_rows', lambda path: dataset)

    required = set(data['training_audit_ids']) | {r['instance_id'] for r in data['development'] + data['evaluation']}
    local_rows = [deepcopy(row) for row in data['train'] + data['development'] if row['instance_id'] in required]
    local_rows += [example(i) for i in range(110, 130)]
    local = {'train': local_rows, 'development': [], 'exposure_inventory_sha256': exposure_sha}

    monkeypatch.setattr(study, 'verify_admission_bundle', lambda *args: {'verified_rows': 40, 'verified_files': 400})

    bundle_dir = tmp_path / 'admitted_bundle'
    independent_spec = {'corpus': local, 'admission_dir': None, 'index_sha256': 'b' * 64}
    index, index_sha = study.build_bundle(
        data, bundle_dir, tmp_path / 'dataset.parquet', reviews_by_id, independent_spec,
        screen_doc=prior_training, exposure_doc=exposure
    )

    assert (bundle_dir / 'index.json').exists()
    assert (bundle_dir / 'independent' / 'corpus.json').exists()
    assert len(index['rows']) == 110
    verification = study.verify_bundle(data, bundle_dir, index_sha, tmp_path / 'dataset.parquet')
    assert verification['public_training_rows'] == 100
    assert verification['independently_verified_training_rows'] == 10
    assert verification['independently_verified_development_rows'] == 10
    assert verification['independently_verified_evaluation_rows'] == 20


def test_protocol_v2_bundle_with_shortfall(tmp_path, monkeypatch):
    data = corpus()
    data['protocol_sha256'] = study.digest(study.PROTOCOL_V2)
    exposure = {'exposures': [], 'reserved014_ids': [], 'exposed_issue_digests': []}
    exposure_sha = study.digest(exposure)
    monkeypatch.setattr(study, 'EXPOSURE_SHA256', exposure_sha)
    data['exposure_inventory_sha256'] = exposure_sha
    prior_training = {'version': 'coding-data-screen014-v1', 'candidate_ids': []}
    screen_sha = study.digest(prior_training)
    monkeypatch.setattr(study, 'TRAINING_SCREEN_SHA256', screen_sha)

    dataset = {}
    reviews_by_id = {}
    for row in data['train'] + data['development']:
        raw = {'instance_id': row['instance_id'], 'repo': row['repository'], 'base_commit': row['source_commit'],
               'problem_statement': row['input']['issue'],
               'patch': 'diff --git a/package/value.py b/package/value.py\n--- a/package/value.py\n+++ b/package/value.py\n@@ -1 +1 @@\n-value = 0\n+value = 1\n'}
        dataset[row['instance_id']] = raw
        identity = {key: row[key] for key in ('instance_id', 'repository', 'source_commit', 'source_digest')}
        rights = {'version': 'coding-rights-review014-v1', **identity,
                  'issue_sha256': study.issue_digest(row['input']['issue']), 'reviewer': 'test reviewer',
                  'reviewed_at': '2026-10-17', 'approved_for_training': True,
                  'materials': {name: {'license': 'fixture', 'provenance': 'fixture', 'basis': 'test'} for name in ('source', 'issue', 'reference_patch')}}
        family = {'version': 'coding-family-review014-v1', **identity,
                  'issue_sha256': study.issue_digest(row['input']['issue']), 'reviewer': 'test reviewer',
                  'reviewed_at': '2026-10-17', 'family_id': row['family_id'], 'near_duplicate_reviewed': True,
                  'method': 'fixture', 'rationale': 'fixture'}
        reviews_by_id[row['instance_id']] = {'rights': rights, 'family': family}

    monkeypatch.setattr(study, 'dataset_rows', lambda path: dataset)

    local_rows = [deepcopy(row) for row in data['train'][:2]]
    local = {'train': local_rows, 'development': [], 'exposure_inventory_sha256': exposure_sha}

    monkeypatch.setattr(study, 'verify_admission_bundle', lambda *args: {'verified_rows': 2, 'verified_files': 20})

    shortfall_doc = {
        'version': 'coding-qualification-shortfall014-v1',
        'shortfall_recorded': True,
        'protocol_version': 'coding-public100-protocol014-v2',
        'reason': 'Multi-stack environment qualification shortfall recorded per protocol.',
        'verified_pilot_rows': 2,
    }

    bundle_dir = tmp_path / 'admitted_bundle_v2'
    independent_spec = {'corpus': local, 'admission_dir': None, 'index_sha256': 'b' * 64}
    index, index_sha = study.build_bundle(
        data, bundle_dir, tmp_path / 'dataset.parquet', reviews_by_id, independent_spec,
        screen_doc=prior_training, exposure_doc=exposure, shortfall_doc=shortfall_doc
    )

    verification = study.verify_bundle(data, bundle_dir, index_sha, tmp_path / 'dataset.parquet')
    assert verification['version'] == 'coding-public100-verification014-v2'
    assert verification['public_training_rows'] == 100
    assert verification['shortfall_recorded'] is True
    assert verification['independently_verified_training_rows'] == 2


