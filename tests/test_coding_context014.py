"""Training context follows public symbols and captured original source only."""
from types import SimpleNamespace
import pytest
from kairos_api.investigations.sandbox import Workspace
from scripts.coding_context014 import select


def make_workspace(tmp_path,text,issue):
    directory=tmp_path/'case';source=directory/'source/package';source.mkdir(parents=True)
    (source/'value.py').write_text(text)
    registry=SimpleNamespace(verify=lambda _:None,directory=lambda _:directory)
    return Workspace(registry,{'issue':issue,'approved_prefix':'package/','entry_files':['package/hidden_answer.py']})


def test_named_class_methods_are_captured_without_entry_hints(tmp_path):
    text='class CropSamples:\n    """'+('detail\\n'*90)+'"""\n    def __init__(self):\n        self.seed = 0\n    def __call__(self):\n        return self.seed\n'.replace('\\n','\n')
    w=make_workspace(tmp_path,text,'CropSamples must preserve set_random_state')
    try:
        regions=select(w)
        assert any('self.seed = 0' in r['text'] for r in regions)
        assert all(r['reference']['end_line']-r['reference']['start_line']<80 for r in regions)
        assert len(regions)<=4
        assert all('hidden_answer' not in r['path'] for r in regions)
    finally:w.close()


def test_public_file_and_function_precede_indirect_class_matches(tmp_path):
    w=make_workspace(tmp_path,'class Saver:\n    def __call__(self):\n        return 0\n\ndef filename_base(name):\n    return name\n','Saver fails; filename_base in package/value.py should retain periods')
    try:
        r=select(w)
        assert 'def filename_base' in r[0]['text']
        assert r[0]['reference']['start_line']==1  # Bounded original neighbors, not reference-derived context.
    finally:w.close()


def test_hidden_verification_is_never_read(tmp_path,monkeypatch):
    from pathlib import Path
    w=make_workspace(tmp_path,'def target():\n    return 1\n','target() is wrong')
    original=Path.read_text
    def guarded(path,*args,**kwargs):
        if path.name in {'reference.patch','test.patch','verify.py'}:raise AssertionError('Hidden material was read')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guarded)
    try:assert select(w)
    finally:w.close()


def test_source_symlink_cannot_expand_context_authority(tmp_path):
    w=make_workspace(tmp_path,'def target():\n    return 1\n','target() is wrong')
    root=w.registry.directory(w.case)/'source/package'
    outside=tmp_path/'outside.py';outside.write_text('def target():\n    return "secret"\n')
    (root/'escape.py').symlink_to(outside)
    try:assert all('secret' not in item['text'] for item in select(w))
    finally:w.close()
