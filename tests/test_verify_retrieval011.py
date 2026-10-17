"""An additive source seal cannot conceal unrelated implementation changes."""
import pytest
from scripts.verify_retrieval011 import MANIFEST, verify_delta


def descriptor(value):
    return {'sha256': value * 64, 'bytes': 1}


def test_exact_additive_inventory_accepted():
    old = {'kairos_api/app.py': descriptor('a')}
    new = {'scripts/retrieval011/core.py': descriptor('b')}
    verify_delta({**old, **new}, old, new)


@pytest.mark.parametrize('name', ['kairos_api/app.py', '.env.local', '.runtime/auth.json',
    '../outside.py', MANIFEST])
def test_unrelated_or_private_delta_refused(name):
    with pytest.raises(ValueError):
        verify_delta({name: descriptor('b')}, {}, {name: descriptor('b')})


def test_changed_or_deleted_inherited_file_refused():
    old = {'kairos_api/app.py': descriptor('a')}
    added = {'scripts/retrieval011/core.py': descriptor('c')}
    for current in (added, {**added, 'kairos_api/app.py': descriptor('b')}):
        with pytest.raises(ValueError, match='source'):
            verify_delta(current, old, added)
