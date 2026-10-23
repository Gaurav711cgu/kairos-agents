"""Docker Desktop can list an image yet fail to resolve its tag for a while after waking; the ID check stays strict."""
import subprocess
from types import SimpleNamespace

import pytest

import scripts.qualify014 as q

GOOD = q.IMAGES['django/django']['id']


def docker(*outputs):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        code, out = outputs[min(len(calls), len(outputs)) - 1]
        return SimpleNamespace(returncode=code, stdout=out)
    run.calls = calls
    return run


def test_tag_that_resolves_after_wake_up_is_accepted(monkeypatch):
    run = docker((1, ''), (1, ''), (0, GOOD + '\n'))
    monkeypatch.setattr(subprocess, 'run', run)
    assert q.inspect_images({'django/django'}, sleep=lambda s: None)['images']['django/django']['id'] == GOOD
    assert len(run.calls) == 3


def test_a_different_image_id_fails_at_once(monkeypatch):
    run = docker((0, 'sha256:' + 'f' * 64))
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='ID changed'):
        q.inspect_images({'django/django'}, sleep=lambda s: None)
    assert len(run.calls) == 1


def test_an_image_that_never_resolves_fails_after_the_deadline(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', docker((1, '')))
    clock = iter(range(0, 10000, 30))
    with pytest.raises(RuntimeError, match='unavailable'):
        q.inspect_images({'django/django'}, sleep=lambda s: None, now=lambda: next(clock))
