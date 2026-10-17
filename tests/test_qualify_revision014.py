"""Capture reuse and safe interruption tests; no Docker or source downloads."""
import json
from pathlib import Path
import pytest
from scripts import qualify_revision014 as revision


def previous(tmp_path, *, interrupted=True):
    cases = [{'instance_id': 'example__project-1', 'split': 'development'}]
    report = {'binding': 'bound', 'model_calls': 0, 'execution_complete': False,
        'candidates': [{**cases[0], 'status': 'eligible'}]}
    if interrupted:
        report['interruption'] = {'reason': 'Reviewed dependency revision before model execution', 'no_uncaptured_checks': True}
    for name, value in [('binding', {'binding': 'bound'}), ('plan', {'binding': 'bound'}), ('report', report)]:
        (tmp_path / (name + '.json')).write_text(json.dumps(value))
    return {'candidates': cases}


def test_partial_run_preserves_unattempted_status_without_failure_relabel(tmp_path):
    cohort = previous(tmp_path)
    _, _, report, receipts = revision.previous_run(tmp_path, cohort)
    assert report['candidates'][0]['status'] == 'eligible'
    assert receipts == {}


def test_partial_run_without_safe_boundary_is_refused(tmp_path):
    cohort = previous(tmp_path, interrupted=False)
    with pytest.raises(ValueError, match='safe-boundary'):
        revision.previous_run(tmp_path, cohort)


def test_unknown_check_cannot_become_an_automatic_environment_retry(tmp_path):
    cohort = previous(tmp_path)
    case = tmp_path / 'cases/example__project-1';case.mkdir(parents=True)
    (case / 'baseline.started.json').write_text('{}')
    with pytest.raises(ValueError, match='uncertain dispatch'):
        revision.previous_run(tmp_path, cohort)


def test_pre_model_gate_rejects_any_prior_inference(tmp_path):
    cohort = {'candidates': [{'instance_id': 'example__project-1'}]}
    path = tmp_path / 'gate.json'
    gate = {'cohort_sha256': revision.q.COHORT_SHA256, 'candidate_ids': ['example__project-1'],
        'model_calls': 0, 'dispatch_intents': 1, 'evaluation_started': False}
    path.write_text(json.dumps(gate))
    with pytest.raises(ValueError, match='zero-model/zero-intent'):
        revision.pre_model_gate(path, cohort)


def test_reused_receipts_keep_exact_bytes_and_explicit_provenance(tmp_path, monkeypatch):
    source = tmp_path / 'old';source.mkdir()
    path = source / 'receipt.json';revision.q.immutable(path, {'model_calls': 0, 'qualified': True})
    target = tmp_path / 'new'
    monkeypatch.setattr(revision.q, 'storage_guard', lambda *_: {})
    revision.copy_receipt(path, target, 'new-bound', [tmp_path])
    assert (target / path.name).read_bytes() == path.read_bytes()
    provenance = json.loads((target / 'reuse-provenance.json').read_text())
    assert provenance['checks_rerun'] == 0
    assert provenance['original_receipt_sha256'] == revision.q.sha(path)
