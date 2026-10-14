"""Portable locations, immutable experiment identity and shared acceptance."""
from types import SimpleNamespace
import json
from pathlib import Path
import pytest
from scripts.study007_runtime import locations,save,load_environment
from scripts.study007_qualification import plan
from scripts.acceptance007 import backend_files


def arguments(**kwargs):
    return SimpleNamespace(runtime=None,model_cache=None,dataset=None,case_root=None,environment_file=None,**kwargs)


def test_external_paths_with_spaces_need_no_developer_desktop(tmp_path):
    args=arguments();args.runtime=str(tmp_path/'checkout with spaces/runtime');args.model_cache=str(tmp_path/'external weights')
    paths=locations(args)
    assert paths['cache']==tmp_path/'external weights'
    assert paths['cases']==tmp_path/'checkout with spaces/runtime/verification'


def test_frozen_receipts_refuse_changes(tmp_path):
    path=tmp_path/'receipt.json';save(path,{'value':1},immutable=True)
    save(path,{'value':1},immutable=True)
    with pytest.raises(ValueError,match='Frozen'):save(path,{'value':2},immutable=True)


def test_environment_requires_private_mode_and_allowed_keys(tmp_path,monkeypatch):
    path=tmp_path/'environment.json';path.write_text(json.dumps({'DATABASE_URL':'private-fixture'}));path.chmod(0o644)
    with pytest.raises(ValueError,match='mode0600'):load_environment({'environment':path,'state':tmp_path})
    path.chmod(0o600);path.write_text(json.dumps({'DATABASE_URL':'fixture','UNSUPPORTED':'value'}))
    with pytest.raises(ValueError,match='unsupported'):load_environment({'environment':path,'state':tmp_path})


def test_selection_is_bounded_and_instance_ordered(monkeypatch):
    monkeypatch.setattr('scripts.study007_qualification.historical_ids',lambda:{'django__django-1'})
    rows=[{'repo':'django/django','instance_id':f'django__django-{i}'} for i in range(8,0,-1)]
    selection=plan(rows)
    assert selection['candidate_ids']['django/django']==[f'django__django-{i}' for i in range(2,7)]
    assert selection['maximum_candidates_per_repository']==5


def test_acceptance_includes_new_protocol_and_delivery_tests():
    files=backend_files()
    assert 'tests/test_protocol_v7.py' in files and 'tests/test_migrations007.py' in files
    assert 'tests/test_package_release006.py' in files


def test_terminal_inspection_preserves_original_measurement_bytes(tmp_path):
    from scripts.study007 import capture_measurement
    path=tmp_path/'measurement.json';record={'id':'captured-investigation'}
    capture_measurement(path,record,42.5,True)
    raw=path.read_bytes()
    result=capture_measurement(path,record,0.001,False)
    assert path.read_bytes()==raw and result['elapsed_seconds']==42.5
    with pytest.raises(ValueError,match='different investigation'):
        capture_measurement(path,{'id':'another-investigation'},0.001,False)


def test_terminal_record_without_stopwatch_does_not_invent_latency(tmp_path):
    from scripts.study007 import capture_measurement
    result=capture_measurement(tmp_path/'measurement.json',{'id':'terminal'},0.001,False)
    assert result['elapsed_seconds'] is None and result['new_execution'] is False
