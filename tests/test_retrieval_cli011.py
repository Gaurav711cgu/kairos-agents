"""Exercise local commands and preserve original-source/output authority."""
import json
import sys
from pathlib import Path
import pytest
from scripts.retrieval011.__main__ import main


def options(tmp_path):
    source = tmp_path / 'source'
    package = source / 'package'
    package.mkdir(parents=True)
    (package / 'cache.py').write_text('def expiry(ttl):\n    return ttl < 1\n')
    return source, ['--source-root', str(source), '--approved-prefix', 'package/',
                    '--revision', 'a' * 40, '--index-root', str(tmp_path / 'indexes'),
                    '--budget-root', str(tmp_path)]


def invoke(monkeypatch, arguments):
    monkeypatch.setattr(sys, 'argv', ['retrieval011', *arguments])
    main()


def test_build_and_query_lexical_commands_use_saved_source(tmp_path, monkeypatch):
    source, args = options(tmp_path)
    built = tmp_path / 'built.json'
    invoke(monkeypatch, ['build', *args, '--output', str(built)])
    index = json.loads(built.read_text())
    result = tmp_path / 'result.json'
    invoke(monkeypatch, ['query', *args, '--index-id', index['index_id'],
                        '--query', 'expiry', '--output', str(result)])
    value = json.loads(result.read_text())
    assert value['regions'][0]['path'] == 'package/cache.py'
    assert list(source.rglob('*.json')) == []
    assert value['audit']['dense_backend'] is None


def test_command_cannot_write_evidence_into_original_source(tmp_path, monkeypatch, capsys):
    source, args = options(tmp_path)
    target = source / 'new-evidence.json'
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, ['build', *args, '--output', str(target)])
    assert error.value.code == 1 and not target.exists()
    assert 'outside the original source' in capsys.readouterr().err


def test_missing_semantic_profile_fails_without_lexical_substitution(tmp_path, monkeypatch, capsys):
    source, args = options(tmp_path)
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, ['build', *args, '--mode', 'dense'])
    assert error.value.code == 1
    assert 'requires explicit pinned profile' in capsys.readouterr().err
    assert not (tmp_path / 'indexes').exists()
