"""Context packing uses complete original lines and never reads target answers."""
import json
from pathlib import Path
import sys
from types import ModuleType
import pytest

from scripts.coding_context_v4_014 import select, load_tokenizer
from scripts.coding_train014 import sha_file
from test_coding_context014 import make_workspace


class SourceOnlyTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        assert [message['role'] for message in messages] == ['system', 'user']
        assert tokenize is True and add_generation_prompt is True
        return list(range(sum(len(message['content']) for message in messages) // 4))


def test_long_documentation_is_omitted_without_changing_original_bounds(tmp_path):
    text = 'class Target:\n    """' + 'Detailed original documentation.\n' * 16 + '"""\n    def run(self):\n        return 0\n'
    w = make_workspace(tmp_path, text, 'Target.run returns the wrong value')
    try:
        regions = select(w, SourceOnlyTokenizer())
        assert 'def run' in regions[0]['text']
        assert 'Detailed original documentation' not in regions[0]['text']
        assert regions[0]['reference']['start_line'] > 1
        w.restore_reference(regions[0])
        assert (w.registry.directory(w.case) / 'source/package/value.py').read_text() == text
        assert any('long documentation omitted' in item['reason'] for item in regions[0]['localization']['omissions'])
    finally:
        w.close()


def test_lower_priority_regions_are_dropped_whole_at_fixed_prompt_budget(tmp_path):
    text = '\n'.join('class Target' + str(i) + ':\n' + ''.join('    value_' + str(j) + ' = "a moderately sized constant"\n' for j in range(50)) for i in range(4))
    w = make_workspace(tmp_path, text, 'Target0 Target1 Target2 Target3 have incorrect behavior')
    try:
        regions = select(w, SourceOnlyTokenizer())
        info = regions[0]['localization']
        assert 0 < len(regions) < 4
        assert info['prompt_tokens'] <= 1536
        assert info['reserved_target_tokens'] == 512
        assert any('whole source region' in item['reason'] for item in info['omissions'])
        for region in regions:
            w.restore_reference(region)
    finally:
        w.close()


def test_oversized_issue_is_rejected_instead_of_truncating_json(tmp_path):
    w = make_workspace(tmp_path, 'class Target:\n    value = 1\n', 'Target ' + 'x' * 9000)
    try:
        with pytest.raises(ValueError, match='no JSON truncation'):
            select(w, SourceOnlyTokenizer())
    finally:
        w.close()


def test_packer_never_reads_reference_tests_or_entry_hints(tmp_path, monkeypatch):
    w = make_workspace(tmp_path, 'class Target:\n    value = 1\n', 'Target is wrong')
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        if path.name in {'reference.patch', 'test.patch', 'verify.py', 'hidden_answer.py'}:
            raise AssertionError('Hidden material was read')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    try:
        assert select(w, SourceOnlyTokenizer())
    finally:
        w.close()


def tokenizer_fixture(tmp_path):
    folder = tmp_path / 'tokenizer'
    folder.mkdir()
    files = {}
    for name in ['tokenizer.json', 'tokenizer_config.json']:
        p = folder / name
        p.write_text('{}')
        files[name] = {'sha256': sha_file(p), 'bytes': p.stat().st_size}
    receipt = folder / 'tokenizer-receipt.json'
    receipt.write_text(json.dumps({'version': 'coding-tokenizer-acquisition014-v1', 'model': 'unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit', 'revision': 'ecfc63c083900ce4f19daad695e711f38ab98fcf', 'files': files}))
    return folder, sha_file(receipt)


def test_only_bound_local_tokenizer_files_can_be_loaded(tmp_path, monkeypatch):
    folder, receipt_sha = tokenizer_fixture(tmp_path)
    calls = []
    class Tokenizer:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls.append((path, kwargs))
            return 'fixture-tokenizer'
    module = ModuleType('transformers')
    module.AutoTokenizer = Tokenizer
    monkeypatch.setitem(sys.modules, 'transformers', module)
    assert load_tokenizer(folder, receipt_sha) == 'fixture-tokenizer'
    assert calls == [(str(folder), {'local_files_only': True, 'trust_remote_code': False})]
    (folder / 'tokenizer.json').write_text('{"corrupt": true}')
    with pytest.raises(ValueError, match='bytes differ'):
        load_tokenizer(folder, receipt_sha)
    assert len(calls) == 1


def test_unexpected_weight_or_code_files_are_rejected_before_loading(tmp_path):
    folder, receipt_sha = tokenizer_fixture(tmp_path)
    (folder / 'unexpected.safetensors').write_bytes(b'fixture')
    with pytest.raises(ValueError, match='file set differs'):
        load_tokenizer(folder, receipt_sha)
