"""Model-release integrity tests use opaque isolated fixtures, never model loads."""
import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from scripts import prepare_hf_model as m


def exported(tmp_path, extra=None, receipt=None):
 files={m.PREFIX+'adapter_model.safetensors':b'opaque isolated adapter fixture',
        m.PREFIX+'adapter_config.json':b'{"base_model_name_or_path":"/content/private-model","r":8}',
        'runs/public100/receipt.json':json.dumps(receipt or {'completed_steps':40,'run_complete':True,'adapter_updated':True}).encode(),
        m.PREFIX+'optimizer.pt':b'opaque optimizer - not for publication'}
 files.update(extra or {})
 manifest={'version':'coding-real-train014-full100-export-v1','contains_base_weights':False,'full_corpus_training_complete':True,'training_rows':100,'training_steps':40,
   'files':{n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in files.items()}}
 path=tmp_path/'training.zip'
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for n,v in files.items():z.writestr(n,v)
  z.writestr('manifest.json',json.dumps(manifest))
 return path,m.sha(path)


def test_only_selected_public_files_are_derived_with_original_archive_unchanged(tmp_path):
 archive,digest=exported(tmp_path);out=tmp_path/'adapter'
 manifest=m.prepare_bundle(archive,out,expected_sha256=digest)
 assert set(p.name for p in out.iterdir())==m.PUBLIC_FILES|{'release-manifest.json'}
 assert not (out/'optimizer.pt').exists()
 assert m.sha(archive)==digest and manifest['repair_effectiveness_verified'] is False
 assert m.verify_bundle(out)==manifest
 assert '/content/private-model' not in (out/'adapter_config.json').read_text()
 assert '100.0%' not in (out/'README.md').read_text() and 'p < 0.001' not in (out/'README.md').read_text()


def test_changed_export_rejected_before_any_output(tmp_path):
 archive,digest=exported(tmp_path);out=tmp_path/'adapter'
 with pytest.raises(ValueError,match='digest'):m.prepare_bundle(archive,out,expected_sha256='0'*64)
 assert not out.exists()


def test_incomplete_training_receipt_is_not_publishable(tmp_path):
 archive,digest=exported(tmp_path,receipt={'completed_steps':39,'run_complete':False,'adapter_updated':True})
 with pytest.raises(ValueError,match='completion'):m.prepare_bundle(archive,tmp_path/'adapter',expected_sha256=digest)


def test_traversal_member_rejected_without_extraction(tmp_path):
 archive,digest=exported(tmp_path,{'../secret':b'not approved'})
 with pytest.raises(ValueError,match='Unsafe'):m.prepare_bundle(archive,tmp_path/'adapter',expected_sha256=digest)
 assert not (tmp_path.parent/'secret').exists()


def test_existing_release_is_never_overwritten(tmp_path):
 archive,digest=exported(tmp_path);out=tmp_path/'adapter';out.mkdir();(out/'sentinel').write_text('preserve')
 with pytest.raises(ValueError,match='Preserve'):m.prepare_bundle(archive,out,expected_sha256=digest)
 assert (out/'sentinel').read_text()=='preserve'


def test_modified_or_extra_release_file_rejected(tmp_path):
 archive,digest=exported(tmp_path);out=tmp_path/'adapter'
 m.prepare_bundle(archive,out,expected_sha256=digest)
 (out/'adapter_model.safetensors').write_bytes(b'changed')
 with pytest.raises(ValueError,match='changed'):m.verify_bundle(out)


def test_optimizer_state_cannot_be_added_to_public_bundle(tmp_path):
 archive,digest=exported(tmp_path);out=tmp_path/'adapter'
 m.prepare_bundle(archive,out,expected_sha256=digest)
 (out/'optimizer.pt').write_bytes(b'extra')
 with pytest.raises(ValueError,match='unselected'):m.verify_bundle(out)


def test_uploader_validates_before_import_or_network(tmp_path):
 from scripts.upload_to_hf import upload_adapter
 with pytest.raises(FileNotFoundError):upload_adapter('fixture/not-uploaded',tmp_path)
