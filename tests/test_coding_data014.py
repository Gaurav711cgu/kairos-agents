"""Training intake never admits reserved cases or declares static patches verified."""
import copy
import pytest
from scripts.coding_data014 import screen, patch_scope


def row(n=1):
    return {'instance_id':f'org__repo-{n}','repo':'org/repo','base_commit':f'{n:040x}',
            'problem_statement':f'Repair unique behavior {n}',
            'patch':f'diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-old{n}\n+new{n}\n',
            'test_patch':'test change','FAIL_TO_PASS':'["tests/test_one.py::test_one"]','PASS_TO_PASS':[]}


def exposure():return {'exposures':[],'exposed_issue_digests':[]}


def test_pending_never_means_verified_or_uploadable():
    result=screen([row()],exposure())
    assert result['candidate_ids']==['org__repo-1']
    assert result['independently_verified_training_repairs']==0
    assert not result['training_ready'] and not result['cloud_upload_allowed']


def test_reserved_ids_issues_and_repositories_are_excluded():
    from scripts.retrieval_study011 import issue_digest
    values=[row(i) for i in range(1,5)];values[2]['repo']='psf/requests';values[3]['repo']='sympy/sympy'
    guard={'exposures':[{'instance_id':'org__repo-1'}],'exposed_issue_digests':[issue_digest(values[1]['problem_statement'])]}
    assert screen(values,guard)['candidate_ids']==[]


def test_duplicate_source_issue_and_patch_are_excluded_in_id_order():
    values=[row(i) for i in range(1,5)]
    values[1]['patch']=values[0]['patch'];values[2]['base_commit']=values[0]['base_commit'];values[3]['problem_statement']=values[0]['problem_statement']
    result=screen(list(reversed(values)),exposure())
    assert result['candidate_ids']==['org__repo-1']
    with pytest.raises(ValueError,match='duplicate'):screen([row(),row()],exposure())


def test_paths_operations_and_large_patches_are_rejected():
    patch=row()['patch']
    for name in ['../secret.py','/secret.py','src/test_x.py','tests/a.py','src/.secret.py','src/a.txt','src/./a.py']:
        with pytest.raises(ValueError):patch_scope(patch.replace('src/a.py',name))
    for suffix in ['\nnew mode 100755','\nGIT binary patch','\nrename from x.py']:
        with pytest.raises(ValueError):patch_scope(patch+suffix)
    with pytest.raises(ValueError):patch_scope(patch.replace('--- a/src/a.py','--- /dev/null'))


def test_missing_or_empty_regression_does_not_enter_candidates():
    value=row();value['FAIL_TO_PASS']='[]'
    assert screen([value],exposure())['candidate_ids']==[]
    del value['test_patch']
    assert screen([value],exposure())['candidate_ids']==[]


def test_candidate_bound_retains_every_disposition(monkeypatch):
    import scripts.coding_data014 as module
    monkeypatch.setattr(module,'MAX_CANDIDATES',2)
    result=screen([row(i) for i in range(1,5)],exposure())
    assert len(result['ledger'])==4
    assert result['candidate_ids']==['org__repo-1','org__repo-2']
    assert result['exclusion_reasons']['Predeclared candidate inspection bound reached']==2


def test_corrupt_download_never_becomes_final(tmp_path,monkeypatch):
    import hashlib,io
    import scripts.coding_data014 as module
    root=tmp_path.resolve()
    monkeypatch.setattr(module,'BYTES',3)
    monkeypatch.setattr(module,'SHA256',hashlib.sha256(b'abc').hexdigest())
    monkeypatch.setattr(module,'storage_guard',lambda *_:None)
    runtime=root/'intake'
    with pytest.raises(ValueError,match='SHA-256'):
        module.fetch(runtime,[root],opener=lambda *_args,**_kw:io.BytesIO(b'bad'))
    assert not (runtime/'swe-gym.parquet').exists()
    assert (runtime/'swe-gym.parquet.pending').read_bytes()==b'bad'
    with pytest.raises(ValueError,match='Partial'):
        module.fetch(runtime,[root],opener=lambda *_args,**_kw:io.BytesIO(b'abc'))


def test_download_is_digest_checked_and_reused(tmp_path,monkeypatch):
    import hashlib,io
    import scripts.coding_data014 as module
    root=tmp_path.resolve()
    monkeypatch.setattr(module,'BYTES',3)
    monkeypatch.setattr(module,'SHA256',hashlib.sha256(b'abc').hexdigest())
    monkeypatch.setattr(module,'storage_guard',lambda *_:None)
    runtime=root/'intake';calls=[]
    def opener(*_args,**_kw):calls.append(1);return io.BytesIO(b'abc')
    assert module.fetch(runtime,[root],opener=opener).read_bytes()==b'abc'
    assert module.fetch(runtime,[root],opener=opener).read_bytes()==b'abc'
    assert calls==[1]
    with pytest.raises(ValueError,match='counted'):
        module.fetch(root.parent/'outside',[root],opener=opener)


def test_cli_exposure_guard_cannot_be_replaced_with_an_empty_inventory(tmp_path):
    import scripts.coding_data014 as module
    path=tmp_path/'guard.json';path.write_text('{}')
    with pytest.raises(ValueError,match='exposure inventory'):module.checked_exposure(path)
