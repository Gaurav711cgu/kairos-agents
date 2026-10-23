from copy import deepcopy
from types import SimpleNamespace
import pytest
from scripts import verify_coding_candidate021 as candidate

PATCH = 'diff --git a/moto/value.py b/moto/value.py\n--- a/moto/value.py\n+++ b/moto/value.py\n@@ -1 +1 @@\n-value = 0\n+value = 1\n'

def fixture():
    row = {'instance_id': 'getmoto__moto-5752', 'repository': 'getmoto/moto', 'source_commit': 'a' * 40,
           'source_digest': 'b' * 64, 'input': {'issue': 'Fix value', 'instruction': 'Replace original lines',
           'original_source': [{'path': 'moto/value.py', 'source_id': 'S123456789abc', 'start_line': 1, 'end_line': 1,
                                'numbered_original_source': '1: value = 0\n'}]},
           'assistant_target': {'action': 'propose_patch', 'edits': [{'source_id': 'S123456789abc', 'start_line': 1, 'end_line': 1, 'new': 'value = 1\n'}]}}
    raw = {'instance_id': row['instance_id'], 'repo': row['repository'], 'base_commit': row['source_commit'],
           'problem_statement': row['input']['issue'], 'version': '3.0', 'patch': PATCH}
    corpus = {'version': candidate.VERSION, 'training_ready': False, 'train': [], 'development': [row]}
    return row, raw, corpus


def test_development_complete_target_selected():
    row, raw, corpus = fixture()
    assert candidate.selected(corpus, {row['instance_id']: raw}, row['instance_id']) == (row, raw, 'Moto3.0')

@pytest.mark.parametrize('failure', ['ready', 'version', 'training', 'absent', 'duplicate', 'issue', 'target', 'environment'])
def test_invalid_candidate_rejected(failure):
    row, raw, corpus = fixture(); identifier = row['instance_id']
    if failure == 'ready': corpus['training_ready'] = True
    elif failure == 'version': corpus['version'] = 'historical014'
    elif failure == 'training': corpus['train'] = [deepcopy(row)]
    elif failure == 'absent': corpus['development'] = []
    elif failure == 'duplicate': corpus['development'].append(deepcopy(row))
    elif failure == 'issue': raw['problem_statement'] = 'Different'
    elif failure == 'target': row['assistant_target']['edits'][0]['new'] = 'value = 0\n'
    elif failure == 'environment': raw['version'] = '99.0'
    with pytest.raises(ValueError): candidate.selected(corpus, {identifier: raw}, identifier)


def test_completeness_fails_before_environment(monkeypatch):
    row, raw, corpus = fixture(); raw['version'] = '4.0'
    row['assistant_target']['edits'][0]['new'] = 'value = 0\n'
    with pytest.raises(ValueError, match='complete reference'): candidate.selected(corpus, {row['instance_id']: raw}, row['instance_id'])


def test_original_excerpt_authority():
    row, _, _ = fixture()
    work = SimpleNamespace(read_original=lambda *a: {'text': '1: value = 0\n', 'reference': {'excerpt_id': '123456789abc' + '0' * 52}})
    assert candidate.captured_sources(work, row)['S123456789abc']['excerpt_id'].startswith('123456789abc')
    row['input']['original_source'][0]['source_id'] = 'S000000000000'
    with pytest.raises(ValueError, match='handle'): candidate.captured_sources(work, row)


def test_excerpt_content_changed():
    row, _, _ = fixture()
    work = SimpleNamespace(read_original=lambda *a: {'text': '1: value = 9\n', 'reference': {}})
    with pytest.raises(ValueError, match='original-source bytes'): candidate.captured_sources(work, row)


def test_existing_receipt_binding_rejected(tmp_path):
    candidate.q.immutable(tmp_path / 'receipt.json', {'binding': 'old', 'model_calls': 0})
    with pytest.raises(ValueError, match='binding'): candidate.replay_completed(tmp_path, 'new')


def test_unsupported_environment_never_touches_docker(tmp_path, monkeypatch):
    row, raw, corpus = fixture(); raw['version'] = '99.0'
    path = tmp_path / 'corpus.json'; candidate.q.immutable(path, corpus)
    monkeypatch.setattr(candidate, 'dataset_rows', lambda _: {row['instance_id']: raw})
    monkeypatch.setattr(candidate, 'image_identity', lambda *_: pytest.fail('Must not inspect Docker'))
    args = SimpleNamespace(corpus=path, dataset=tmp_path / 'dataset', task_id=row['instance_id'],
                           image_receipt=tmp_path / 'image.json', output=tmp_path / 'out', budget_root=[tmp_path])
    with pytest.raises(ValueError, match='version 99.0'): candidate.execute(args)
    assert not args.output.exists()


def test_unknown_check_stops_before_image_inspection(tmp_path, monkeypatch):
    row, raw, corpus = fixture(); corpus_path = tmp_path / 'corpus.json'; candidate.q.immutable(corpus_path, corpus)
    image = tmp_path / 'image.json'; review = tmp_path / 'review.json'
    candidate.q.immutable(review, {'repository_version': 'Moto3.0'})
    candidate.q.immutable(image, {'review_sha256': candidate.q.sha(review)})
    dataset = tmp_path / 'dataset'; dataset.write_text('fixture')
    output = tmp_path / 'out'; output.mkdir(); (output / 'candidate.started.json').write_text('{}')
    monkeypatch.setattr(candidate, 'dataset_rows', lambda _: {row['instance_id']: raw})
    monkeypatch.setattr(candidate.q, 'storage_guard', lambda *_: {})
    monkeypatch.setattr(candidate, 'image_identity', lambda *_: pytest.fail('Unknown dispatch must not inspect Docker'))
    args = SimpleNamespace(corpus=corpus_path, dataset=dataset, task_id=row['instance_id'], image_receipt=image, output=output, budget_root=[tmp_path])
    with pytest.raises(RuntimeError, match='unknown dispatch'): candidate.execute(args)


@pytest.mark.parametrize('version', ['4.0', '4.1'])
def test_moto4_requires_explicit_matching_review_before_docker(tmp_path, monkeypatch, version):
    row, raw, corpus = fixture(); raw['version'] = version
    corpus_path = tmp_path / 'corpus.json'; candidate.q.immutable(corpus_path, corpus)
    review = tmp_path / 'review.json'; candidate.q.immutable(review, {'repository_version': 'Moto3.0'})
    image = tmp_path / 'image.json'; candidate.q.immutable(image, {'review_sha256': candidate.q.sha(review)})
    monkeypatch.setattr(candidate, 'dataset_rows', lambda _: {row['instance_id']: raw})
    monkeypatch.setattr(candidate, 'image_identity', lambda *_: pytest.fail('Wrong-version recipe must not inspect Docker'))
    args = SimpleNamespace(corpus=corpus_path, dataset=tmp_path / 'dataset', task_id=row['instance_id'],
                           image_receipt=image, output=tmp_path / 'out', budget_root=[tmp_path])
    with pytest.raises(ValueError, match='environment version differs'): candidate.execute(args)
    assert not args.output.exists()


def test_projected_workspace_budget_releases_verified_archive_first(tmp_path, monkeypatch):
    row, raw, corpus = fixture()
    corpus_path = tmp_path / 'corpus.json'; candidate.q.immutable(corpus_path, corpus)
    dataset = tmp_path / 'dataset'; dataset.write_text('fixture')
    review = tmp_path / 'review.json'; candidate.q.immutable(review, {'repository_version': 'Moto3.0'})
    image = tmp_path / 'image.json'; candidate.q.immutable(image, {'review_sha256': candidate.q.sha(review)})
    output = tmp_path / 'out'; output.mkdir()
    source = output / 'source'; source.mkdir(); (source / 'value.py').write_text('value = 0\n')
    archive = output / 'source.tar.gz'; archive.write_bytes(b'verified archive')
    source_receipt = {'source_digest': row['source_digest'], 'archive_sha256': candidate.q.sha(archive)}
    monkeypatch.setattr(candidate, 'dataset_rows', lambda _: {row['instance_id']: raw})
    monkeypatch.setattr(candidate, 'image_identity', lambda *_: {'id': 'reviewed-image'})
    monkeypatch.setattr(candidate.q, 'pinned_source', lambda *_: (source, source_receipt))
    projections = []
    def guard(roots, projected=0):
        if projected:
            assert not archive.exists()
            projections.append(projected)
    monkeypatch.setattr(candidate.q, 'storage_guard', guard)
    def stop_before_checks(_):
        raise RuntimeError('Reached verifier after resource admission')
    monkeypatch.setattr(candidate, 'verifier', stop_before_checks)
    args = SimpleNamespace(corpus=corpus_path, dataset=dataset, task_id=row['instance_id'],
                           image_receipt=image, output=output, budget_root=[tmp_path], allow_source_download=False)
    with pytest.raises(RuntimeError, match='Reached verifier'):
        candidate.execute(args)
    assert projections == [2 * len('value = 0\n') + candidate.q.CHECK_RESERVATION]
    assert (output / 'registry/cases' / row['instance_id'] / 'source/value.py').read_text() == 'value = 0\n'


def test_pydantic_requires_its_own_environment_review(tmp_path, monkeypatch):
    row, raw, corpus = fixture()
    row['repository'] = raw['repo'] = 'pydantic/pydantic'; raw['version'] = '2.0'
    corpus_path = tmp_path/'corpus.json'; candidate.q.immutable(corpus_path, corpus)
    review = tmp_path/'review.json'; candidate.q.immutable(review, {'repository_version':'Moto4.0'})
    image = tmp_path/'image.json'; candidate.q.immutable(image, {'review_sha256':candidate.q.sha(review)})
    monkeypatch.setattr(candidate, 'dataset_rows', lambda _: {row['instance_id']:raw})
    monkeypatch.setattr(candidate, 'image_identity', lambda *_: pytest.fail('Wrong repository review must not inspect Docker'))
    args = SimpleNamespace(corpus=corpus_path, dataset=tmp_path/'dataset', task_id=row['instance_id'],
                           image_receipt=image, output=tmp_path/'out', budget_root=[tmp_path])
    with pytest.raises(ValueError, match='environment version differs'): candidate.execute(args)
