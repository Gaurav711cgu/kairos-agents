"""Array validation precedes allocation in the isolated native search worker."""
import io
import numpy as np
import pytest
from scripts.retrieval011.faiss_worker import load_matrix


def serialized(value):
    stream = io.BytesIO()
    np.save(stream, value, allow_pickle=False)
    return stream.getvalue()


def test_exact_float_matrix_retains_values():
    value = np.array([[1., 0.]], dtype=np.float32)
    assert np.array_equal(load_matrix(serialized(value), (1, 2)), value)


@pytest.mark.parametrize('bad', [np.ones((3, 4), dtype=np.float32),
                               np.ones((1, 2), dtype=np.float64)])
def test_wrong_shape_or_dtype_is_refused_before_numpy_load(bad, monkeypatch):
    raw = serialized(bad)
    monkeypatch.setattr(np, 'load', lambda *a, **k: pytest.fail('Array allocated before header validation'))
    with pytest.raises(ValueError, match='header'):
        load_matrix(raw, (1, 2))


def test_truncated_or_extended_data_is_refused_before_allocation(monkeypatch):
    raw = serialized(np.ones((1, 2), dtype=np.float32))
    monkeypatch.setattr(np, 'load', lambda *a, **k: pytest.fail('Unvalidated data allocated'))
    for bad in (raw[:-1], raw + b'extra'):
        with pytest.raises(ValueError, match='byte length'):
            load_matrix(bad, (1, 2))
