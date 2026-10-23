"""One-command repair of a real case: dataset pinning, case guard and step order (no network, Docker or model)."""
import hashlib
import io
import json

import pytest

import scripts.repair_case as rc


def test_dataset_is_downloaded_once_and_rejected_on_a_hash_mismatch(tmp_path, monkeypatch):
    data = b'parquet-bytes'
    monkeypatch.setattr(rc, 'DATASET_SHA256', hashlib.sha256(data).hexdigest())
    calls = []

    def opener(url, timeout):
        calls.append(url)
        return io.BytesIO(data)
    target = tmp_path / 'swe-bench-test.parquet'
    assert rc.ensure_dataset(target, opener) == target and target.read_bytes() == data
    rc.ensure_dataset(target, opener)
    assert len(calls) == 1 and calls[0] == rc.DATASET_URL
    monkeypatch.setattr(rc, 'DATASET_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='hash'):
        rc.ensure_dataset(tmp_path / 'other.parquet', opener)
    assert not (tmp_path / 'other.parquet').exists()


def test_protected_validation_and_holdout_cases_are_refused(monkeypatch):
    monkeypatch.setattr(rc, 'bucket', lambda case: 'holdout')
    with pytest.raises(SystemExit, match='protected holdout'):
        rc.pick([{'instance_id': 'django__django-1', 'repo': 'django/django', 'version': '3.2'}], 'django__django-1')


def test_only_cases_the_pinned_image_can_run_are_accepted(monkeypatch):
    monkeypatch.setattr(rc, 'bucket', lambda case: 'development')
    rows = [{'instance_id': 'django__django-1', 'repo': 'django/django', 'version': '3.2'},
            {'instance_id': 'django__django-2', 'repo': 'django/django', 'version': '4.1'}]
    assert rc.pick(rows, 'django__django-1')['version'] == '3.2'
    with pytest.raises(SystemExit, match='4.1'):
        rc.pick(rows, 'django__django-2')
    with pytest.raises(SystemExit, match='not in SWE-bench'):
        rc.pick(rows, 'django__django-9')


def test_steps_qualify_then_repair_then_score_in_order(tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(rc, 'qualify', lambda case, row, work: order.append('qualify') or True)
    monkeypatch.setattr(rc, 'repair', lambda row, work, model, samples: order.append('repair'))
    monkeypatch.setattr(rc, 'score', lambda work: order.append('score') or {'fair_pick_verified': 1})
    assert rc.run_case({'instance_id': 'django__django-1'}, tmp_path, 'm', 1)['fair_pick_verified'] == 1
    assert order == ['qualify', 'repair', 'score']
    roots = json.loads((tmp_path / 'storage-roots.json').read_text())['roots']
    assert str(tmp_path) in roots


def test_unqualified_case_stops_before_any_model_call(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, 'qualify', lambda case, row, work: False)
    monkeypatch.setattr(rc, 'repair', lambda *a: pytest.fail('model called for an unqualified case'))
    with pytest.raises(SystemExit, match='did not qualify'):
        rc.run_case({'instance_id': 'django__django-1'}, tmp_path, 'm', 1)


def test_case_work_lives_outside_the_repository_work_tree():
    assert not rc.RUNTIME.resolve().is_relative_to(rc.ROOT.resolve())
