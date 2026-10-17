"""Bounded lexical/dense/hybrid retrieval over approved original Python source.

Only explicit source roots and prefixes participate. Issue-specific entry files,
reference patches, hidden verifiers, evaluation labels and candidate edits never
participate in indexing. Dense inference is supplied by an explicit encoder; no
random, hash-derived or lexical replacement is used when it is unavailable.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict, dataclass, field
import hashlib
import io
import importlib.util
import subprocess
import sys
import json
import errno
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Mapping, Protocol, Sequence

import numpy as np

VERSION = "original-source-retrieval011-v1"
TOKENIZER = "python-identifiers-and-subwords-v1"
MAX_QUERY_BYTES = 4096
PROTECTED_DIRECTORIES = {"tests", "test", "testing", "__pycache__", "node_modules", "venv"}
PROTECTED_FILES = {"conftest.py", "setup.py", "credentials.py", "secrets.py", "private_key.py",
                   "verify.py", "verification.py", "reference.py"}


class Encoder(Protocol):
    dimension: int
    identity: Mapping

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one real embedding per input, with shape (len(texts), dimension)."""

    def encode_queries(self, texts: Sequence[str]) -> np.ndarray:
        """Apply the model's query-only instruction, if its pretrained recipe needs one."""


@dataclass(frozen=True)
class Limits:
    max_files: int = 4000
    max_source_bytes: int = 32 * 1024 * 1024
    max_file_bytes: int = 250_000
    max_chunks: int = 8000
    max_chunk_lines: int = 80
    max_chunk_bytes: int = 8000
    max_index_bytes: int = 96 * 1024 * 1024
    max_embedding_dimension: int = 4096
    encode_batch_size: int = 32
    max_tree_entries: int = 40_000
    max_omissions: int = 6000

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("All retrieval limits must be positive integers")
        if any(getattr(self, name) > descriptor.default for name, descriptor in self.__dataclass_fields__.items()):
            raise ValueError("Retrieval limits may be lowered, never raised beyond the supported resource caps")
        if self.max_chunk_lines > 80 or self.max_chunk_bytes > 8000 or self.max_file_bytes > 250_000:
            raise ValueError("Chunk limits exceed existing original-source capture bounds")


@dataclass(frozen=True)
class SourceIndex:
    index_id: str
    revision: str
    approved_prefix: str
    source_snapshot_digest: str
    files: tuple
    chunks: tuple
    omissions: tuple
    limits: Limits
    encoder_identity: dict | None
    dimension: int
    exact_backend: str
    encoding_metadata: tuple
    vectors: np.ndarray | None = field(repr=False, compare=False)
    source_root: Path = field(repr=False, compare=False)
    directory: Path = field(repr=False, compare=False)
    manifest: dict = field(repr=False, compare=False)


@dataclass(frozen=True)
class RetrievalResult:
    index_id: str
    revision: str
    approved_prefix: str
    source_snapshot_digest: str
    selected: tuple
    audit: dict
    limits: Limits


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(_json(value))


def _no_duplicates(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate index JSON field")
        value[key] = item
    return value


def _decode(raw):
    def constant(_):
        raise ValueError("Non-finite index JSON value")
    return json.loads(raw, object_pairs_hook=_no_duplicates, parse_constant=constant)


def _root(path):
    original = Path(path).absolute()
    for component in (original, *original.parents):
        if component.is_symlink():
            raise ValueError("Source/index roots must not traverse symlinks")
    resolved = original.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("Source/index root must be a directory")
    return resolved


def _relative(value):
    if not isinstance(value, str):
        raise ValueError("Source paths must be relative POSIX names")
    candidate = value.rstrip("/")
    path = PurePosixPath(candidate)
    if (not candidate or str(path) != candidate or path.is_absolute() or "\\" in candidate
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", candidate)
            or any(part in {".", ".."} or part.startswith(".") for part in path.parts)):
        raise ValueError("Source paths must be canonical relative POSIX names")
    return path


def _prefix(value):
    path = _relative(value)
    if any(part in PROTECTED_DIRECTORIES for part in path.parts):
        raise ValueError("Approved source prefix is protected")
    return path.as_posix() + "/"


def _eligible(name):
    path = PurePosixPath(name)
    return (all(not part.startswith(".") and part not in PROTECTED_DIRECTORIES for part in path.parts)
            and path.suffix == ".py" and path.name not in PROTECTED_FILES
            and not path.name.startswith("test_") and not path.name.endswith("_test.py")
            and not path.name.startswith(("credential", "secret_")))


def _revision(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", value):
        raise ValueError("A pinned hexadecimal source revision is required")
    return value


def _read_source(path, maximum):
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise ValueError("Source files must be ordinary files without links")
    if details.st_size > maximum:
        raise ValueError("Source file exceeds the bounded capture size")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if (not stat.S_ISREG(actual.st_mode) or actual.st_nlink != 1
                or (actual.st_dev, actual.st_ino) != (details.st_dev, details.st_ino)):
            raise ValueError("Source file changed while opening")
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Source file exceeds the bounded capture size")
    return raw


def _inventory(source_root, approved_prefix, limits):
    root = _root(source_root)
    prefix = _prefix(approved_prefix)
    directory = root.joinpath(*PurePosixPath(prefix).parts)
    for component in (directory, *directory.parents):
        if component == root:
            break
        if component.is_symlink():
            raise ValueError("Approved source prefix traverses a symlink")
    if not directory.is_dir():
        raise ValueError("Approved source prefix is unavailable")
    files, omissions, originals = [], [], {}
    total = entries = 0
    for current, directories, names in os.walk(directory, followlinks=False):
        entries += len(directories) + len(names)
        if entries > limits.max_tree_entries or len(omissions) > limits.max_omissions:
            raise ValueError("Source discovery exceeds its entry or omission budget")
        keep = []
        for name in sorted(directories):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if name.startswith(".") or name in PROTECTED_DIRECTORIES:
                omissions.append({"path": relative, "reason": "Protected or hidden directory excluded without reading"})
            elif path.is_symlink():
                raise ValueError("Source directories must not be symlinks")
            else:
                keep.append(name)
        directories[:] = keep
        for name in sorted(names):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            if not _eligible(relative):
                omissions.append({"path": relative, "reason": "Outside ordinary approved Python source; content not read"})
                continue
            _relative(relative)
            raw = _read_source(path, limits.max_file_bytes)
            total += len(raw)
            if len(files) >= limits.max_files or total > limits.max_source_bytes:
                raise ValueError("Source inventory exceeds its file or byte budget")
            try:
                text = raw.decode("utf-8")
            except UnicodeError:
                omissions.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw),
                                  "reason": "UTF-8 source required; file excluded without lossy decoding"})
                files.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw), "indexed": False})
                continue
            if "\x00" in text:
                raise ValueError("NUL bytes are not valid source evidence")
            files.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw), "indexed": True})
            originals[relative] = text
    files.sort(key=lambda item: item["path"])
    omissions.sort(key=lambda item: (item["path"], item["reason"]))
    if not originals:
        raise ValueError("No eligible original Python source is available")
    return root, prefix, files, omissions, originals


def _windows(lines, start, end, limits):
    cursor = start
    while cursor <= end:
        finish, size = cursor, 0
        while finish <= end and finish - cursor < limits.max_chunk_lines:
            line_size = len(lines[finish - 1].encode())
            if size + line_size > limits.max_chunk_bytes:
                break
            size += line_size
            finish += 1
        if finish == cursor:
            raise ValueError("A complete original source line exceeds the excerpt budget")
        yield cursor, finish - 1
        cursor = finish


def _function_regions(tree):
    result = []
    def visit(node, parents):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = ".".join((*parents, child.name))
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = min([child.lineno] + [item.lineno for item in child.decorator_list])
                    result.append((start, child.end_lineno, name))
                visit(child, (*parents, child.name))
            else:
                visit(child, parents)
    visit(tree, ())
    return sorted(result)


def _chunks(revision, files, originals, limits):
    chunks, omissions = [], []
    by_path = {item["path"]: item for item in files}
    for path, text in sorted(originals.items()):
        lines = text.splitlines(keepends=True)
        if not lines:
            continue
        try:
            functions = _function_regions(ast.parse(text, filename=path))
        except (SyntaxError, ValueError, RecursionError):
            functions = []
            omissions.append({"path": path, "reason": "AST parsing unavailable; exact whole-line file windows used"})
        regions = []
        covered = set()
        for start, end, symbol in functions:
            windows = list(_windows(lines, start, end, limits))
            kind = "function" if len(windows) == 1 else "function_window"
            regions.extend((a, b, kind, symbol) for a, b in windows)
            covered.update(range(start, end + 1))
        # Imports, constants, class declarations and other file-level source remain retrievable.
        number = 1
        while number <= len(lines):
            if number in covered:
                number += 1
                continue
            start = number
            while number <= len(lines) and number not in covered:
                number += 1
            regions.extend((a, b, "module_window", "") for a, b in _windows(lines, start, number - 1, limits))
        seen = set()
        for start, end, kind, symbol in sorted(regions):
            if (start, end) in seen:
                continue
            seen.add((start, end))
            raw = "".join(lines[start - 1:end])
            if not raw.strip():
                continue
            metadata = {"revision": revision, "path": path, "file_sha256": by_path[path]["sha256"],
                        "start_line": start, "end_line": end, "text_sha256": _sha(raw.encode())}
            chunks.append({"id": "C" + _digest(metadata)[:24], **metadata,
                           "kind": kind, "symbol": symbol, "text": raw})
            if len(chunks) > limits.max_chunks:
                raise ValueError("Source chunks exceed the index budget")
    if not chunks:
        raise ValueError("No nonempty original-source chunks are available")
    return chunks, omissions


def chunks_from_source(source_root, approved_prefix, revision, limits=None):
    limits = limits or Limits()
    revision = _revision(revision)
    root, prefix, files, omissions, originals = _inventory(source_root, approved_prefix, limits)
    chunks, excluded = _chunks(revision, files, originals, limits)
    omissions.extend(excluded)
    return {"source_root": root, "approved_prefix": prefix, "revision": revision,
            "files": files, "chunks": chunks, "omissions": omissions,
            "source_snapshot_digest": _digest(files)}


def _encoder(encoder, limits):
    dimension = getattr(encoder, "dimension", None)
    identity = getattr(encoder, "identity", None)
    if type(dimension) is not int or not 1 <= dimension <= limits.max_embedding_dimension:
        raise ValueError("Encoder dimension is missing or outside the index budget")
    if not isinstance(identity, Mapping) or not identity:
        raise ValueError("An explicit encoder identity is required")
    # Canonicalize to remove mutable caller state; no machine paths are necessary.
    identity = _decode(_json(dict(identity)))
    if len(_json(identity)) > 16_384:
        raise ValueError("Encoder identity exceeds its metadata budget")
    def no_machine_paths(value):
        if isinstance(value, str) and (value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value)):
            raise ValueError("Encoder identity must use logical model names and hashes, never machine paths")
        if isinstance(value, dict):
            for key, item in value.items():
                no_machine_paths(key); no_machine_paths(item)
        if isinstance(value, list):
            for item in value:
                no_machine_paths(item)
    no_machine_paths(identity)
    return dimension, identity


def _normalized(value, rows, dimension):
    vectors = np.asarray(value)
    if vectors.shape != (rows, dimension) or not np.issubdtype(vectors.dtype, np.floating):
        raise ValueError("Encoder returned an invalid embedding shape or dtype")
    vectors = vectors.astype(np.float32, copy=True)
    if not np.isfinite(vectors).all():
        raise ValueError("Encoder returned non-finite embeddings")
    norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
    if (norms <= 1e-12).any() or not np.isfinite(norms).all():
        raise ValueError("Encoder returned empty or invalid embeddings")
    vectors /= norms.astype(np.float32)[:, None]
    return vectors


def _document(chunk):
    return chunk["path"] + "\n" + chunk["symbol"] + "\n" + chunk["text"]


def _encoding_metadata(encoder):
    value = getattr(encoder, "last_metadata", None)
    if value is None:
        return {"available": False, "scope": "Encoder did not expose per-input tokenization metadata"}
    if not isinstance(value, Mapping) or len(_json(dict(value))) > 64 * 1024:
        raise ValueError("Encoder tokenization metadata is invalid or exceeds its budget")
    return _decode(_json(dict(value)))


def _ensure_index_root(index_root, source_root):
    original = Path(index_root).absolute()
    for component in (original, *original.parents):
        if component.is_symlink():
            raise ValueError("Index storage must not traverse symlinks")
    path = original.resolve(strict=False)
    if path.is_relative_to(source_root) or source_root.is_relative_to(path):
        raise ValueError("Index storage must be separate from original source")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return _root(path)


def build_index(source_root, approved_prefix, revision, index_root, encoder=None, *,
                limits=None, exact_backend="numpy", previous=None):
    """Build and atomically save one content-addressed original-source index.

    Unchanged chunks may reuse previous embeddings only under the same encoder
    identity. Any changed file receives new chunk IDs and source handles.
    """
    limits = limits or Limits()
    if exact_backend not in {"numpy", "faiss"}:
        raise ValueError("Unknown exact dense-search backend")
    if exact_backend == "faiss":
        if importlib.util.find_spec("faiss") is None:
            raise ValueError("FAISS was explicitly requested but is not installed")
    snapshot = chunks_from_source(source_root, approved_prefix, revision, limits)
    dimension, identity = (0, None) if encoder is None else _encoder(encoder, limits)
    chunks = snapshot["chunks"]
    vectors, encoded_rows, reused_rows, encoding_metadata = None, 0, 0, []
    if encoder is not None:
        if len(chunks) * dimension * 4 > limits.max_index_bytes:
            raise ValueError("Embedding matrix exceeds the serialized index budget")
        vectors = np.empty((len(chunks), dimension), dtype=np.float32)
        reusable = {}
        if (previous is not None and previous.encoder_identity == identity and previous.dimension == dimension
                and previous.vectors is not None):
            reusable = {item["id"]: previous.vectors[index] for index, item in enumerate(previous.chunks)}
        pending = []
        for index, chunk in enumerate(chunks):
            if chunk["id"] in reusable:
                vectors[index] = reusable[chunk["id"]]
                reused_rows += 1
            else:
                pending.append(index)
        if previous is not None and reused_rows:
            reused_ids = {chunk["id"] for chunk in chunks if chunk["id"] in reusable}
            for captured in previous.encoding_metadata:
                ids = [identifier for identifier in captured.get("chunk_ids", []) if identifier in reused_ids]
                if ids:
                    encoding_metadata.append({"chunk_ids": ids, "original_batch_chunk_ids": captured["chunk_ids"],
                                              "metadata": captured["metadata"],
                                              "scope": "Captured encoder metadata reused with unchanged chunk embeddings"})
        for start in range(0, len(pending), limits.encode_batch_size):
            positions = pending[start:start + limits.encode_batch_size]
            encoded = _normalized(encoder.encode([_document(chunks[index]) for index in positions]), len(positions), dimension)
            encoding_metadata.append({"chunk_ids": [chunks[index]["id"] for index in positions],
                                      "metadata": _encoding_metadata(encoder)})
            vectors[positions] = encoded
            encoded_rows += len(positions)
    payload = {"version": VERSION, "revision": snapshot["revision"], "approved_prefix": snapshot["approved_prefix"],
               "source_snapshot_digest": snapshot["source_snapshot_digest"], "files": snapshot["files"],
               "chunks": chunks, "omissions": snapshot["omissions"], "limits": asdict(limits),
               "tokenizer": TOKENIZER, "encoder_identity": identity, "dimension": dimension,
               "exact_backend": exact_backend, "lexical": {"algorithm": "BM25", "k1": 1.2, "b": 0.75},
               "embedding_scope": "Explicit encoder tokenization/truncation settings belong to its identity; original chunks remain exact",
               "encoding_metadata": encoding_metadata,
               "embedding_input_bytes": sum(len(_document(chunk).encode()) for chunk in chunks) if encoder else 0}
    files = {"index.json": _json(payload)}
    if vectors is not None:
        buffer = io.BytesIO(); np.save(buffer, vectors, allow_pickle=False)
        files["vectors.npy"] = buffer.getvalue()
    if sum(map(len, files.values())) > limits.max_index_bytes:
        raise ValueError("Serialized index exceeds its byte budget")
    descriptors = {name: {"bytes": len(raw), "sha256": _sha(raw)} for name, raw in sorted(files.items())}
    index_id = _digest({"version": VERSION, "files": descriptors})
    manifest = {"version": VERSION, "index_id": index_id, "files": descriptors}
    root = _ensure_index_root(index_root, snapshot["source_root"])
    target = root / index_id
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix=".index011-", dir=root) as temporary:
            staging = Path(temporary)
            for name, raw in {**files, "manifest.json": _json(manifest)}.items():
                with (staging / name).open("xb") as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            try:
                os.rename(staging, target)
            except OSError as error:
                if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
    index = load_index(root, index_id, snapshot["source_root"], approved_prefix, revision, encoder=encoder)
    return index


def _bounded_file(path, maximum):
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1 or details.st_size > maximum:
        raise ValueError("Index member is not an ordinary bounded file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Index member exceeds its byte budget")
    return raw


def load_index(index_root, index_id, source_root, approved_prefix, revision, *, encoder=None):
    """Validate content hashes, vector shape and current source before querying."""
    if not isinstance(index_id, str) or not re.fullmatch(r"[a-f0-9]{64}", index_id):
        raise ValueError("Invalid content-addressed index identifier")
    root = _root(index_root)
    directory = root / index_id
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Content-addressed index is unavailable")
    manifest = _decode(_bounded_file(directory / "manifest.json", 64 * 1024))
    if (set(manifest) != {"version", "index_id", "files"} or manifest["version"] != VERSION
            or manifest["index_id"] != index_id or not isinstance(manifest["files"], dict)
            or set(manifest["files"]) not in ({"index.json"}, {"index.json", "vectors.npy"})
            or _digest({"version": VERSION, "files": manifest["files"]}) != index_id):
        raise ValueError("Index manifest is inconsistent")
    maximum = Limits().max_index_bytes
    members = {}
    for name, descriptor in manifest["files"].items():
        if (not isinstance(descriptor, dict) or set(descriptor) != {"bytes", "sha256"}
                or type(descriptor["bytes"]) is not int or not 0 < descriptor["bytes"] <= maximum):
            raise ValueError("Invalid index member descriptor")
        raw = _bounded_file(directory / name, maximum)
        if len(raw) != descriptor["bytes"] or _sha(raw) != descriptor["sha256"]:
            raise ValueError("Index member content hash mismatch")
        members[name] = raw
    if sum(map(len, members.values())) > maximum:
        raise ValueError("Index package exceeds its byte budget")
    payload = _decode(members["index.json"])
    if payload.get("version") != VERSION or payload.get("tokenizer") != TOKENIZER:
        raise ValueError("Unsupported source index version")
    limits = Limits(**payload["limits"])
    if limits.max_index_bytes > maximum or len(payload["chunks"]) > limits.max_chunks:
        raise ValueError("Index limits exceed the supported load budget")
    if payload["revision"] != _revision(revision) or payload["approved_prefix"] != _prefix(approved_prefix):
        raise ValueError("Source revision or approved prefix differs from the index")
    dimension = payload["dimension"]
    if type(dimension) is not int or not 0 <= dimension <= limits.max_embedding_dimension:
        raise ValueError("Invalid stored embedding dimension")
    vectors = None
    if dimension:
        if "vectors.npy" not in members or not isinstance(payload["encoder_identity"], dict):
            raise ValueError("Dense index is missing its explicit encoder identity or vectors")
        # Inspect the header before allocation. Object/pickle arrays are forbidden.
        stream = io.BytesIO(members["vectors.npy"])
        version = np.lib.format.read_magic(stream)
        if version != (1, 0):
            raise ValueError("Unsupported embedding serialization version")
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream)
        expected_shape = (len(payload["chunks"]), dimension)
        if shape != expected_shape or fortran or dtype != np.dtype("float32"):
            raise ValueError("Stored embedding shape or dtype is invalid")
        expected_bytes = shape[0] * shape[1] * dtype.itemsize
        if len(members["vectors.npy"]) - stream.tell() != expected_bytes:
            raise ValueError("Stored embedding byte length is invalid")
        vectors = np.load(io.BytesIO(members["vectors.npy"]), allow_pickle=False)
        if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
            raise ValueError("Stored embeddings are non-finite, empty or not normalized")
        vectors.flags.writeable = False
    elif "vectors.npy" in members or payload["encoder_identity"] is not None:
        raise ValueError("Lexical-only index cannot contain dense model state")
    if encoder is not None and _encoder(encoder, limits) != (dimension, payload["encoder_identity"]):
        raise ValueError("Encoder differs from the stored semantic index")
    index = SourceIndex(index_id=index_id, revision=payload["revision"], approved_prefix=payload["approved_prefix"],
        source_snapshot_digest=payload["source_snapshot_digest"], files=tuple(payload["files"]),
        chunks=tuple(payload["chunks"]), omissions=tuple(payload["omissions"]), limits=limits,
        encoder_identity=payload["encoder_identity"], dimension=dimension, exact_backend=payload["exact_backend"],
        encoding_metadata=tuple(payload.get("encoding_metadata", [])),
        vectors=vectors, source_root=_root(source_root), directory=directory, manifest=manifest)
    assert_fresh(index)
    return index


def assert_fresh(index, source_root=None):
    snapshot = chunks_from_source(source_root or index.source_root, index.approved_prefix, index.revision, index.limits)
    if (snapshot["source_snapshot_digest"] != index.source_snapshot_digest
            or snapshot["files"] != list(index.files) or snapshot["chunks"] != list(index.chunks)):
        raise ValueError("Original source changed; rebuild the revision-bound index before retrieval")
    return snapshot


def _tokens(text):
    result = []
    for identifier in re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\d+", text):
        whole = identifier.lower()
        result.append(whole)
        parts = [part.lower() for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", identifier)]
        if parts != [whole]:
            result.extend(parts)
    return result


def _lexical(index, text):
    documents = [Counter(_tokens(_document(chunk))) for chunk in index.chunks]
    lengths = [sum(document.values()) for document in documents]
    average = sum(lengths) / len(lengths)
    query_terms = Counter(_tokens(text))
    frequencies = {word: sum(word in document for document in documents) for word in query_terms}
    scores = []
    for document, length in zip(documents, lengths):
        score = 0.0
        for word, weight in query_terms.items():
            tf = document[word]
            if tf:
                idf = math.log(1 + (len(documents) - frequencies[word] + 0.5) / (frequencies[word] + 0.5))
                score += weight * idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / max(average, 1)))
        scores.append(score)
    return sorted((position for position, score in enumerate(scores) if score > 0),
                  key=lambda position: (-scores[position], index.chunks[position]["id"])), scores


def _dense(index, text, encoder):
    if encoder is None or index.vectors is None:
        raise ValueError("Dense/hybrid retrieval requires the explicit indexed embedding model")
    if _encoder(encoder, index.limits) != (index.dimension, index.encoder_identity):
        raise ValueError("Query encoder differs from the indexed semantic model")
    encode_query = getattr(encoder, "encode_queries", None)
    method = "encode_queries" if callable(encode_query) else "encode"
    vector = _normalized((encode_query if callable(encode_query) else encoder.encode)([text]), 1, index.dimension)
    metadata = {"method": method, "metadata": _encoding_metadata(encoder)}
    if index.exact_backend == "faiss":
        buffer = io.BytesIO()
        np.save(buffer, vector.astype(np.float32), allow_pickle=False)
        environment = {"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1",
                       "PYTHONPATH": os.pathsep.join(p for p in sys.path if p and Path(p).is_dir()),
                       "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("faiss_worker.py")),
                str(index.directory / "vectors.npy"), index.manifest["files"]["vectors.npy"]["sha256"],
                str(len(index.chunks)), str(index.dimension)], input=buffer.getvalue(),
                capture_output=True, timeout=30, env=environment, check=False)
        except subprocess.TimeoutExpired:
            raise ValueError("Isolated FAISS search exceeded its deadline") from None
        if result.returncode or len(result.stdout) != len(index.chunks) * 4:
            raise ValueError("Isolated FAISS backend failed; no search fallback was used")
        values = np.frombuffer(result.stdout, dtype="<f4")
        if not np.isfinite(values).all():
            raise ValueError("FAISS returned non-finite scores")
        scores = [float(value) for value in values]
        metadata["exact_search_execution"] = "Fresh isolated FAISS process; no PyTorch/OpenMP runtime sharing"
    elif index.exact_backend == "numpy":
        scores = [float(value) for value in (index.vectors @ vector[0])]
    else:
        raise ValueError("Unknown stored exact-search backend")
    positions = sorted(range(len(scores)), key=lambda position: (-scores[position], index.chunks[position]["id"]))
    return positions, scores, metadata


def query(index, text, *, mode="hybrid", limit=4, encoder=None, source_root=None, rrf_k=60):
    """Rank exact captured original regions; hybrid uses reciprocal-rank fusion."""
    if (not isinstance(text, str) or not text.strip() or len(text.encode()) > MAX_QUERY_BYTES
            or "\x00" in text or not _tokens(text)):
        raise ValueError("A nonempty bounded source query is required")
    if mode not in {"lexical", "dense", "hybrid"}:
        raise ValueError("Unknown retrieval mode")
    if type(limit) is not int or not 1 <= limit <= 20 or type(rrf_k) is not int or rrf_k <= 0:
        raise ValueError("Invalid retrieval limit or fusion constant")
    assert_fresh(index, source_root)
    lexical_order, lexical_scores = _lexical(index, text) if mode != "dense" else ([], [])
    dense_order, dense_scores, query_encoding_metadata = _dense(index, text, encoder) if mode != "lexical" else ([], [], None)
    lexical_rank = {position: rank for rank, position in enumerate(lexical_order, 1)}
    dense_rank = {position: rank for rank, position in enumerate(dense_order, 1)}
    if mode == "lexical":
        order, scores = lexical_order, {position: lexical_scores[position] for position in lexical_order}
    elif mode == "dense":
        order, scores = dense_order, {position: dense_scores[position] for position in dense_order}
    else:
        scores = {position: (1 / (rrf_k + lexical_rank[position]) if position in lexical_rank else 0)
                  + (1 / (rrf_k + dense_rank[position]) if position in dense_rank else 0)
                  for position in set(lexical_order) | set(dense_order)}
        order = sorted(scores, key=lambda position: (-scores[position], index.chunks[position]["id"]))
    selected = tuple({"chunk": dict(index.chunks[position]), "score": scores[position],
                      "lexical_rank": lexical_rank.get(position), "dense_rank": dense_rank.get(position),
                      "lexical_score": lexical_scores[position] if lexical_scores else None,
                      "dense_cosine": dense_scores[position] if dense_scores else None}
                     for position in order[:limit])
    audit = {"version": VERSION, "mode": mode, "index_id": index.index_id,
             "revision": index.revision, "source_snapshot_digest": index.source_snapshot_digest,
             "query_sha256": _sha(text.encode()), "query_bytes": len(text.encode()),
             "corpus_chunks": len(index.chunks), "returned": len(selected), "requested": limit,
             "dense_backend": index.exact_backend if mode != "lexical" else None,
             "encoder_identity": index.encoder_identity if mode != "lexical" else None,
             "query_encoding_metadata": query_encoding_metadata,
             "document_encoding_metadata": [batch for batch in index.encoding_metadata
                 if any(item["chunk"]["id"] in batch.get("chunk_ids", []) for item in selected)] if mode != "lexical" else [],
             "rrf_k": rrf_k if mode == "hybrid" else None,
             "ranking": [{"chunk_id": item["chunk"]["id"], **{key: value for key, value in item.items() if key != "chunk"}}
                         for item in selected],
             "omissions": [{"reason": "Lower-ranked chunks outside requested retrieval limit",
                            "count": max(0, len(order) - limit)}],
             "source_omissions": {"count": len(index.omissions), "sha256": _digest(list(index.omissions)),
                                  "location": "content-addressed index.json/omissions"},
             "scope": "Issue query and original source only; no reference repairs, evaluation labels or entry-file hints"}
    return RetrievalResult(index.index_id, index.revision, index.approved_prefix,
                           index.source_snapshot_digest, selected, audit, index.limits)


def capture(workspace, result):
    """Re-read ranked regions through existing original-source capture authority."""
    if workspace.case["revision"] != result.revision or _prefix(workspace.case["approved_prefix"]) != result.approved_prefix:
        raise ValueError("Workspace source revision or scope differs from retrieval")
    source_root = workspace.registry.directory(workspace.case) / "source"
    _, _, files, _, _ = _inventory(source_root, result.approved_prefix, result.limits)
    if _digest(files) != result.source_snapshot_digest:
        raise ValueError("Original source changed after retrieval; captured authority is stale")
    observations, references = [], []
    for item in result.selected:
        chunk = item["chunk"]
        captured = workspace.read_original(chunk["path"], chunk["start_line"], chunk["end_line"])
        reference = captured.get("reference", {})
        if (reference.get("path") != chunk["path"] or reference.get("source_digest") != chunk["file_sha256"]
                or reference.get("start_line") != chunk["start_line"] or reference.get("end_line") != chunk["end_line"]):
            raise ValueError("Captured original source differs from the ranked revision-bound chunk")
        expected = "".join(f"{number}: {line}" for number, line in enumerate(chunk["text"].splitlines(keepends=True), chunk["start_line"]))
        if captured.get("text") != expected:
            raise ValueError("Captured original source bytes differ from the index")
        captured["selection_reason"] = "Revision-bound " + result.audit["mode"] + " retrieval; rank " + str(len(observations) + 1)
        captured["retrieval011"] = {"index_id": result.index_id, "chunk_id": chunk["id"],
                                  "score": item["score"], "lexical_rank": item["lexical_rank"], "dense_rank": item["dense_rank"]}
        observations.append({"action": "retrieved_source011", "result": captured})
        references.append({"chunk_id": chunk["id"], "reference": reference})
    return observations, {**result.audit, "captured_references": references,
                          "capture_scope": "Existing Workspace.read_original handles; no candidate source or verification material"}


def search_codebase(workspace, index, text, *, encoder, limit=5, mode="hybrid"):
    """Return semantic source evidence through existing captured-source authority."""
    result = query(index, text, mode=mode, limit=limit, encoder=encoder)
    return capture(workspace, result)
