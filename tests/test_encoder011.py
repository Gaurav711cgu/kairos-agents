"""Pre-import integrity and resource guards; no model-quality fixture claims."""
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from scripts.retrieval011.encoder import verify_profile
from scripts.retrieval011.__main__ import storage_guard
from scripts.prepare_retrieval011 import prepare


@pytest.fixture
def prepared(tmp_path):
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / 'profiles/coderank011.json').read_text())
    directory = tmp_path / 'encoder'
    directory.mkdir()
    # Explicit tiny integrity fixtures; never used for embeddings or performance.
    for name in profile['files']:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = ('software-integrity-fixture:' + name).encode()
        path.write_bytes(raw)
        profile['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return directory, profile


def test_verified_profile_does_not_import_optional_torch(prepared):
    directory, profile = prepared
    assert verify_profile(directory, profile) == directory


@pytest.mark.parametrize('field,value', [('revision', 'a' * 40), ('model', 'other/model'),
    ('pooling', 'mean'), ('max_tokens', 8192), ('query_prefix', ''), ('dimension', 12)])
def test_changed_model_recipe_rejected_before_loading(prepared, field, value):
    directory, profile = prepared
    profile[field] = value
    with pytest.raises(ValueError, match='profile'):
        verify_profile(directory, profile)


def test_corrupt_or_missing_model_bytes_rejected(prepared):
    directory, profile = prepared
    target = directory / 'model.fp16.safetensors'
    target.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash or size'):
        verify_profile(directory, profile)
    target.unlink()
    with pytest.raises(ValueError, match='hash or size'):
        verify_profile(directory, profile)


def test_symlink_model_and_parent_refused(prepared, tmp_path):
    directory, profile = prepared
    target = directory / 'model.fp16.safetensors'
    outside = tmp_path / 'outside'
    target.replace(outside)
    target.symlink_to(outside)
    with pytest.raises(ValueError, match='symlink'):
        verify_profile(directory, profile)
    alias = tmp_path / 'alias'
    alias.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        verify_profile(alias, profile)


def test_extra_encoder_file_inventory_rejected(prepared):
    directory, profile = prepared
    profile['files']['arbitrary.py'] = {'bytes': 1, 'sha256': 'a' * 64}
    with pytest.raises(ValueError, match='inventory'):
        verify_profile(directory, profile)


def test_storage_guard_counts_overlapping_roots_once(tmp_path):
    nested = tmp_path / 'cache'
    nested.mkdir()
    (nested / 'one').write_bytes(b'1234')
    assert storage_guard([tmp_path, nested])['owned_bytes'] == 4


def test_storage_reserve_refuses_before_prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, 'disk_usage', lambda _: SimpleNamespace(free=4 * 1024**3))
    with pytest.raises(ValueError, match='reserve'):
        storage_guard([tmp_path], projected=1)


def test_existing_model_check_is_offline_and_does_not_import_torch(prepared):
    directory, profile = prepared
    result = prepare(directory, profile, {}, [directory.parent], check_only=True)
    assert result['network_requests'] == 0 and result['reused']


def test_encoder_storage_outside_declared_roots_is_refused(prepared, tmp_path):
    directory, profile = prepared
    unrelated = tmp_path / 'unrelated'
    unrelated.mkdir()
    with pytest.raises(ValueError, match='declared'):
        prepare(directory, profile, {}, [unrelated], check_only=True)
