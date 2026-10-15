"""Isolated exact FAISS search, avoiding mixed PyTorch/OpenMP native runtimes."""
from pathlib import Path
import hashlib
import io
import sys

import numpy as np


def load_matrix(raw, shape):
    """Validate the NPY header and exact byte length before allocating an array."""
    stream = io.BytesIO(raw)
    if np.lib.format.read_magic(stream) != (1, 0):
        raise ValueError('Unsupported FAISS matrix serialization')
    actual_shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
    if actual_shape != shape or fortran or dtype != np.dtype('float32'):
        raise ValueError('Invalid FAISS matrix header')
    if len(raw) - stream.tell() != shape[0] * shape[1] * 4:
        raise ValueError('Invalid FAISS matrix byte length')
    return np.load(io.BytesIO(raw), allow_pickle=False)


def main():
    import faiss
    if len(sys.argv) != 5:
        raise ValueError('Expected frozen vector file, digest, row count and dimension')
    path, expected, rows, dimension = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    if (path.is_symlink() or not path.is_file() or not 1 <= rows <= 8000
            or not 1 <= dimension <= 4096 or path.stat().st_size > 96 * 1024**2):
        raise ValueError('Invalid bounded FAISS vector input')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Frozen vectors changed before FAISS search')
    vectors = load_matrix(raw, (rows, dimension))
    query_raw = sys.stdin.buffer.read(65537)
    if len(query_raw) > 65536:
        raise ValueError('FAISS query exceeds its byte limit')
    query = load_matrix(query_raw, (1, dimension))
    if (vectors.shape != (rows, dimension) or vectors.dtype != np.dtype('float32')
            or query.shape != (1, dimension) or query.dtype != np.dtype('float32')
            or not np.isfinite(vectors).all() or not np.isfinite(query).all()):
        raise ValueError('Invalid FAISS vector shapes, dtype or values')
    faiss.omp_set_num_threads(1)
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)
    values, positions = index.search(query, rows)
    scores = np.empty(rows, dtype='<f4')
    scores[positions[0]] = values[0]
    sys.stdout.buffer.write(scores.tobytes())


if __name__ == '__main__':
    main()
