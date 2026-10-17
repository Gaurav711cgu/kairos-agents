"""Verify the real metadata freeze without revealing reference or test patches."""
from copy import deepcopy
from pathlib import Path
import pytest
from scripts.cohort013 import freeze
from scripts.retrieval_study011 import load

ROOT=Path(__file__).resolve().parents[1]/'evidence/evaluation013/cohort'


def inputs():
    return load(ROOT/'metadata.json'),load(ROOT/'prior-exposures.json')


def test_real_frozen_candidates_are_balanced_and_deterministic():
    metadata,history=inputs();cohort=freeze(metadata,history)
    assert cohort==load(ROOT/'cohort.json')
    assert len({row['instance_id'] for row in cohort['candidates']})==24
    for repo in ('django/django','pytest-dev/pytest'):
        assert sum(row['repository']==repo and row['split']=='development' for row in cohort['candidates'])==4
        assert sum(row['repository']==repo and row['split']=='holdout' for row in cohort['candidates'])==8
    reverse=deepcopy(metadata);reverse['records'].reverse()
    # Input hash changes with file ordering; selected identities do not.
    assert freeze(reverse,history)['candidates']==cohort['candidates']
    assert not cohort['qualification']['performed'] and cohort['model_calls']==0


@pytest.mark.parametrize('mutation',['reference','duplicate','revision','missing','empty_issue'])
def test_invalid_or_leaking_metadata_is_refused(mutation):
    metadata,history=inputs()
    if mutation=='reference':metadata['records'][0]['patch']='hidden material'
    elif mutation=='duplicate':metadata['records'][1]=deepcopy(metadata['records'][0])
    elif mutation=='revision':metadata['revision']='main'
    elif mutation=='missing':metadata['records'].pop()
    else:metadata['records'][0]['problem_statement']=' '
    with pytest.raises(ValueError):freeze(metadata,history)


def test_insufficient_unexposed_pool_fails_without_replacement():
    metadata,history=inputs()
    history['exposures'] += [{'instance_id':row['instance_id']} for row in metadata['records'] if row['repo']=='pytest-dev/pytest']
    with pytest.raises(ValueError,match='Insufficient'):freeze(metadata,history)
