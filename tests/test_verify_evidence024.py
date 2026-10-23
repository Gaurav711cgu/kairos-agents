import hashlib
import json

from scripts.verify_evidence024 import main, verify


def sha(data):
    return hashlib.sha256(data).hexdigest()


def make(tmp_path, bad=None):
    d = tmp_path / 'h1'
    d.mkdir()
    (d / 'a.json').write_bytes(b'A')
    (d / 'sub').mkdir()
    (d / 'sub' / 'b.json').write_bytes(b'B')
    files = {'a.json': sha(b'A'), 'sub/b.json': sha(b'B'), **(bad or {})}
    (d / 'MANIFEST.json').write_text(json.dumps({'files': files}))
    return d


def test_clean_tree_passes(tmp_path, capsys):
    make(tmp_path)
    assert verify(tmp_path) == (2, [])
    assert main([str(tmp_path)]) == 0
    assert 'checked 2 files, 0 problems' in capsys.readouterr().out


def test_mismatch_missing_and_bad_entry_fail_nonzero(tmp_path, capsys):
    d = make(tmp_path, {'gone.json': sha(b'x'), 'bad.json': 5})
    (d / 'a.json').write_bytes(b'tampered')
    (d / 'bad.json').write_bytes(b'')
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert 'h1/MANIFEST.json: a.json: mismatch' in out and 'gone.json: missing' in out and 'bad.json: bad entry' in out
    assert (d / 'a.json').read_bytes() == b'tampered'  # read-only
