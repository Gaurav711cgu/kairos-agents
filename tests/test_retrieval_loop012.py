"""Versioned context and admission controls; no model or credential access."""
import json
from types import SimpleNamespace
import numpy as np
import pytest

from scripts.repair010.codex_context010 import build_context010
from scripts.repair010.codex_transport010 import CodexInvestigator010
from scripts.repair012.retrieval_loop012 import (RuntimePolicy012, VERSION,
    QueryEncoder012, ReportedTokenBudget012, TokenBoundCLI012)
from test_codex_context010 import region, CASE


def test_v8_keeps_six_regions_while_v7_keeps_four():
    sources = [region(f'package/file{i}.py') for i in range(7)]
    budgets = {'calls_remaining': 6, 'patches_remaining': 2, 'checks_remaining': 2}
    _, old = build_context010(CASE, 'loop-v7', sources, budgets)
    _, new = build_context010(CASE, 'loop-v8', sources, budgets)
    assert len(old['reference_bindings']) == 4
    assert len(new['reference_bindings']) == 6
    assert new['selection']['budgets']['retrievals_remaining'] == 6


def test_v8_source_tools_stop_at_six_without_extending_v7():
    sources = [region()]
    searches = [{'action': 'search', 'result': {'matches': []}} for _ in range(3)]
    budgets = {'calls_remaining': 7, 'patches_remaining': 4, 'checks_remaining': 4}
    _, old = build_context010(CASE, 'loop-v7', sources + searches, budgets)
    _, new = build_context010(CASE, 'loop-v8', sources + searches, budgets)
    assert 'search' not in old['allowed_actions'] and 'search' in new['allowed_actions']
    _, exhausted = build_context010(CASE, 'loop-v8', sources + searches * 2, budgets)
    assert 'search' not in exhausted['allowed_actions']


@pytest.mark.parametrize('usage', [None, {}, {'prompt_tokens': True, 'completion_tokens': 2},
                                 {'prompt_tokens': -1, 'completion_tokens': 3}])
def test_unknown_or_invalid_captured_usage_stops_before_provider_prepare(usage, monkeypatch):
    provider = object.__new__(TokenBoundCLI012)
    provider.captured_usage012 = [usage]
    monkeypatch.setattr(CodexInvestigator010, 'prepare', lambda *a, **k: pytest.fail('Unexpected model preparation'))
    with pytest.raises(ReportedTokenBudget012, match='unavailable'):
        provider.prepare({}, 'loop-v8', [], {})


@pytest.mark.parametrize('usage', [{'prompt_tokens': 64000, 'completion_tokens': 1},
                                 {'prompt_tokens': 2, 'completion_tokens': 8192}])
def test_reported_token_allowance_stops_subsequent_calls(usage, monkeypatch):
    provider = object.__new__(TokenBoundCLI012)
    provider.captured_usage012 = [usage]
    monkeypatch.setattr(CodexInvestigator010, 'prepare', lambda *a, **k: pytest.fail('Unexpected model preparation'))
    with pytest.raises(ReportedTokenBudget012, match='allowance'):
        provider.prepare({}, 'loop-v8', [], {})


def test_remaining_reported_tokens_are_captured_with_limit_scope(monkeypatch):
    provider = object.__new__(TokenBoundCLI012)
    provider.captured_usage012 = [{'prompt_tokens': 100, 'completion_tokens': 20}]
    def prepare(self, case, configuration, observations, budgets):
        return {}, {'selection': {'budgets': budgets}}
    monkeypatch.setattr(CodexInvestigator010, 'prepare', prepare)
    _, context = provider.prepare({}, 'loop-v8', [], {'calls_remaining': 9})
    assert context['selection']['budgets']['reported_prompt_tokens_remaining'] == 63900
    assert 'may overshoot' in context['token_policy012']['scope']


def test_query_child_receives_no_api_credentials(monkeypatch, tmp_path):
    encoder = object.__new__(QueryEncoder012)
    encoder.directory, encoder.profile_path = tmp_path, tmp_path / 'profile.json'
    encoder.identity = {'software_fixture': True}
    monkeypatch.setenv('OPENAI_API_KEY', 'software-test-only')
    def run(argv, **settings):
        assert 'OPENAI_API_KEY' not in settings['env']
        assert settings['env']['HF_HUB_OFFLINE'] == '1'
        assert settings['timeout'] == 45 and settings['input'] == b'example'
        return SimpleNamespace(returncode=0, stderr=b'', stdout=json.dumps({
            'identity': encoder.identity, 'vectors': [[1.] * 768], 'metadata': {'fixture_only': True}}).encode())
    monkeypatch.setattr('scripts.repair012.retrieval_loop012.subprocess.run', run)
    assert encoder.encode_queries(['example']).shape == (1, 768)


def test_failed_query_child_does_not_substitute_vectors(monkeypatch, tmp_path):
    encoder = object.__new__(QueryEncoder012)
    encoder.directory, encoder.profile_path = tmp_path, tmp_path / 'profile.json'
    encoder.identity = {'software_fixture': True}
    monkeypatch.setattr('scripts.repair012.retrieval_loop012.subprocess.run',
                        lambda *a, **k: SimpleNamespace(returncode=1, stdout=b'', stderr=b'fixture failure'))
    with pytest.raises(ValueError, match='no retrieval/provider fallback'):
        encoder.encode_queries(['example'])


def test_runtime_policy_rejects_unversioned_configuration():
    with pytest.raises(ValueError, match='Unsupported'):
        RuntimePolicy012(VERSION, 'loop-v7', {}, {}, ())
