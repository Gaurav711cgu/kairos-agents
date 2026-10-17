"""Phase 3 seals must reject private paths and unrelated source changes."""
import pytest
from scripts.verify_evaluation013 import MANIFEST, verify_delta


def descriptor(value):
    return {'sha256': value * 64, 'bytes': 1}


def test_evaluation_overlay_accepts_only_exact_declared_changes():
    old = {'kairos_api/investigations/worker.py': descriptor('a')}
    new = {'scripts/study010.py': descriptor('b')}
    verify_delta({**old, **new}, old, new)
    with pytest.raises(ValueError, match='source'):
        verify_delta(old, old, new)


@pytest.mark.parametrize('name', ['kairos_api/app.py', '.runtime/auth.json', '.env.local',
                                 '../outside.py', MANIFEST, 'evidence/retrieval011/manifest.json'])
def test_private_and_historical_overlay_paths_are_refused(name):
    with pytest.raises(ValueError):
        verify_delta({name: descriptor('b')}, {}, {name: descriptor('b')})


def test_missing_inherited_file_is_refused():
    old = {'kairos_api/app.py': descriptor('a')}
    new = {'scripts/pilot013.py': descriptor('b')}
    with pytest.raises(ValueError, match='source'):
        verify_delta(new, old, new)
