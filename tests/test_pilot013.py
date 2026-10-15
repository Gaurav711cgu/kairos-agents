"""Development isolation and no-redispatch gates; no model/service execution."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import Mock
import pytest
from scripts import pilot013
from scripts.repair012.retrieval_loop012 import VERSION, RuntimePolicy012


def options(tmp_path):
    return SimpleNamespace(manifest=tmp_path/'manifest',case_root=tmp_path/'cases',task_id='case',
                           runtime=tmp_path/'new',checkout=tmp_path)


@pytest.mark.parametrize('split',['holdout','evaluation','unresolved',None])
def test_locked_or_unknown_split_never_reaches_policy_or_runtime(tmp_path,monkeypatch,split):
    registry=SimpleNamespace(get=lambda _: {'id':'case','split':split},verify=Mock())
    monkeypatch.setattr(pilot013,'CaseRegistry',lambda *a:registry)
    forbidden=Mock(side_effect=AssertionError('No policy/provider call'))
    monkeypatch.setattr(pilot013.study012,'policy012',forbidden)
    with pytest.raises(ValueError,match='locked evaluation'):
        pilot013.prepare(options(tmp_path))
    assert not registry.verify.called and not forbidden.called and not (tmp_path/'new').exists()


def test_development_case_verifies_original_and_freezes_exposure_scope(tmp_path,monkeypatch):
    case={'id':'case','split':'development'}
    verify=Mock()
    registry=SimpleNamespace(get=lambda _:case,verify=verify)
    monkeypatch.setattr(pilot013,'CaseRegistry',lambda *a:registry)
    monkeypatch.setattr(pilot013.study010,'checked_runtime010',lambda runtime,*a:runtime)
    policy=RuntimePolicy012(VERSION,'loop-v8',{}, {'retrieval':{}},('existing.py',))
    monkeypatch.setattr(pilot013.study012,'policy012',lambda *a:policy)
    _,_,_,frozen=pilot013.prepare(options(tmp_path))
    verify.assert_called_once_with(case)
    assert frozen.metadata['scope']==pilot013.SCOPE and frozen.metadata['exposed_development']
    assert frozen.source_files[-1]=='scripts/pilot013.py'
    assert policy.metadata=={'retrieval':{}} and not (tmp_path/'new').exists()


def test_existing_uncertain_runtime_reports_without_execution(tmp_path,monkeypatch):
    args=options(tmp_path);args.runtime.mkdir()
    monkeypatch.setattr(pilot013,'prepare',lambda _: (object(),{'id':'case'},args.runtime,object()))
    saved={'status':'unknown','outcome':'unknown_dispatch','automatic_redispatch':False}
    monkeypatch.setattr(pilot013.study010,'existing_runtime010',lambda *a,**k:saved)
    monkeypatch.setattr(pilot013.study010,'runner_lock010',Mock(side_effect=AssertionError('No execution')))
    assert pilot013.run(args)==saved
