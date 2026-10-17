"""Mechanical mining tests; no model-quality result is asserted."""
import pytest
torch = pytest.importorskip('torch')
from scripts.source_variants014 import hard_pairs


def test_mining_uses_only_training_similarity_and_stable_ties():
    group = {'unit_kind': 'source_function', 'key': ('a',), 'query': torch.tensor([1., 0.]),
        'codes': torch.tensor([[1., 0.], [.8, .6], [.8, .6], [-1., 0.]]),
        'rows': [{'example_id': name, 'relevance': int(i == 0)} for i, name in enumerate(('target', 'z', 'a', 'last'))]}
    pairs, weights = hard_pairs([group])
    assert pairs == [(0, 0, 2), (0, 0, 1), (0, 0, 3)]
    assert weights == [1., 1., 1.]


def test_issue_protocol_cannot_enter_source_miner():
    with pytest.raises(ValueError, match='Source-only'):
        hard_pairs([{'unit_kind': 'reviewed_issue'}])
