"""Software-only retrieval fixtures; synthetic vectors do not claim model quality."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.retrieval011 import (
    Limits, build_index, load_index, query, capture, chunks_from_source, assert_fresh,
)
from scripts.retrieval011 import core

REVISION = "a" * 40


class FixtureEncoder:
    """Explicit deterministic test vectors, never presented as semantic inference."""
    dimension = 3
    identity = {"kind": "software-fixture", "model": "hand-authored-routing-v1",
                "token_limit": 1024, "query_prefix": "QUERY ONLY: "}

    def __init__(self):
        self.documents = []
        self.queries = []
        self.last_metadata = {}

    def encode(self, texts):
        self.documents.extend(texts)
        self.last_metadata = {"truncations": [], "input_count": len(texts), "scope": "software fixture only"}
        vectors = []
        for text in texts:
            if "expiry" in text or "ttl" in text:
                vectors.append([1., 0., 0.])
            elif "invoice" in text:
                vectors.append([0., 1., 0.])
            else:
                vectors.append([0., 0., 1.])
        return np.asarray(vectors, dtype=np.float32)

    def encode_queries(self, texts):
        self.queries.extend("QUERY ONLY: " + text for text in texts)
        self.last_metadata = {"truncations": [], "input_count": len(texts), "query_prefix_applied": True}
        return np.asarray([[1., 0., 0.] for _ in texts], dtype=np.float32)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "registered/source"
    package = root / "package"; package.mkdir(parents=True)
    (package / "cache.py").write_text("VERSION = 1\n\ndef expiry(ttl):\n    return ttl < 1\n")
    (package / "billing.py").write_text("def invoice_total(amount):\n    return amount + 2\n")
    (package / "other.py").write_text("def greet(name):\n    return name.upper()\n")
    return root


def build(source, tmp_path, encoder=None, **settings):
    return build_index(source, "package/", REVISION, tmp_path / "indices", encoder, **settings)


def test_ast_chunks_are_complete_exact_revision_bound_regions(source):
    result = chunks_from_source(source, "package/", REVISION)
    function = next(item for item in result["chunks"] if item["symbol"] == "expiry")
    assert function["kind"] == "function" and (function["start_line"], function["end_line"]) == (3, 4)
    assert function["text"] == "def expiry(ttl):\n    return ttl < 1\n"
    assert function["text_sha256"] == hashlib.sha256(function["text"].encode()).hexdigest()
    assert function["revision"] == REVISION
    assert any(item["kind"] == "module_window" and "VERSION" in item["text"] for item in result["chunks"])
    assert result == chunks_from_source(source, "package/", REVISION)


def test_large_functions_split_only_at_whole_line_boundaries(source):
    text = "def large():\n" + "    value = 1\n" * 160 + "    return value\n"
    (source / "package/large.py").write_text(text)
    result = chunks_from_source(source, "package/", REVISION)
    chunks = [item for item in result["chunks"] if item["path"] == "package/large.py"]
    assert all(item["kind"] == "function_window" and item["end_line"] - item["start_line"] < 80 for item in chunks)
    assert "".join(item["text"] for item in chunks) == text


def test_nested_methods_decorators_and_syntax_fallback_remain_source_only(source):
    (source / "package/classes.py").write_text("class A:\n    @staticmethod\n    def method(x):\n        return x\n")
    (source / "package/legacy.py").write_text("def broken(:\n    return 1\n")
    result = chunks_from_source(source, "package/", REVISION)
    method = next(item for item in result["chunks"] if item["symbol"] == "A.method")
    assert method["start_line"] == 2 and method["text"].startswith("    @staticmethod")
    assert any(item["path"] == "package/legacy.py" and "AST parsing" in item["reason"] for item in result["omissions"])


def test_protected_tests_credentials_and_hidden_material_never_read(source, monkeypatch):
    names = ["tests/test_hidden.py", ".private/key.py", "credentials.py", "secrets.py", "verify.py", "test_logic.py", "reference.patch"]
    for name in names:
        path = source / "package" / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("DO NOT READ")
    original = core._read_source
    accessed = []
    def read(path, maximum):
        accessed.append(path.relative_to(source).as_posix())
        assert "DO NOT READ" not in path.name
        assert path.name not in {Path(name).name for name in names}
        return original(path, maximum)
    monkeypatch.setattr(core, "_read_source", read)
    result = chunks_from_source(source, "package/", REVISION)
    assert len(accessed) == 3
    assert all("DO NOT READ" not in chunk["text"] for chunk in result["chunks"])
    assert len(result["omissions"]) >= len(names) - 1


@pytest.mark.parametrize("prefix", ["../private/", "/absolute/", "package/../private/", "package\\private", "tests/"])
def test_source_scope_escapes_rejected(source, prefix):
    with pytest.raises(ValueError):
        chunks_from_source(source, prefix, REVISION)


def test_symlink_and_hardlink_source_refused(source, tmp_path):
    other = tmp_path / "private.py"; other.write_text("DO NOT READ")
    link = source / "package/escape.py"; link.symlink_to(other)
    with pytest.raises(ValueError, match="ordinary files"):
        chunks_from_source(source, "package/", REVISION)
    link.unlink(); link.hardlink_to(other)
    with pytest.raises(ValueError, match="ordinary files"):
        chunks_from_source(source, "package/", REVISION)


def test_index_round_trip_hashes_readonly_vectors_and_lexical_rank(source, tmp_path):
    encoder = FixtureEncoder()
    index = build(source, tmp_path, encoder)
    loaded = load_index(tmp_path / "indices", index.index_id, source, "package/", REVISION, encoder=encoder)
    assert loaded.index_id == index.index_id and not loaded.vectors.flags.writeable
    assert np.allclose(np.linalg.norm(loaded.vectors, axis=1), 1)
    result = query(loaded, "invoice_total", mode="lexical")
    assert result.selected[0]["chunk"]["path"] == "package/billing.py"
    assert result.audit["dense_backend"] is None
    assert build(source, tmp_path, FixtureEncoder()).index_id == index.index_id


def test_dense_queries_use_query_only_method_and_capture_token_metadata(source, tmp_path):
    encoder = FixtureEncoder()
    index = build(source, tmp_path, encoder)
    result = query(index, "stale entries", mode="dense", encoder=encoder)
    assert result.selected[0]["chunk"]["symbol"] == "expiry"
    assert encoder.queries == ["QUERY ONLY: stale entries"]
    assert all("QUERY ONLY:" not in text for text in encoder.documents)
    assert result.audit["query_encoding_metadata"]["method"] == "encode_queries"
    assert result.audit["query_encoding_metadata"]["metadata"]["query_prefix_applied"]
    assert result.audit["document_encoding_metadata"]


def test_hybrid_is_exact_reciprocal_rank_fusion_not_score_addition(source, tmp_path):
    encoder = FixtureEncoder(); index = build(source, tmp_path, encoder)
    result = query(index, "invoice_total", mode="hybrid", encoder=encoder, limit=20)
    for item in result.selected:
        expected = (1 / (60 + item["lexical_rank"]) if item["lexical_rank"] else 0)
        expected += 1 / (60 + item["dense_rank"])
        assert item["score"] == expected
    assert result.selected[0]["chunk"]["symbol"] == "invoice_total"
    assert result.audit["rrf_k"] == 60


def test_dense_and_hybrid_never_silently_use_lexical_fallback(source, tmp_path):
    index = build(source, tmp_path)
    for mode in ("dense", "hybrid"):
        with pytest.raises(ValueError, match="explicit indexed embedding"):
            query(index, "expiry", mode=mode)


@pytest.mark.parametrize("text", ["", "   ", "!!!", "bad\x00query", "a" * 4097])
def test_empty_or_oversized_query_refused(source, tmp_path, text):
    index = build(source, tmp_path)
    with pytest.raises(ValueError, match="nonempty bounded"):
        query(index, text, mode="lexical")


def test_source_change_invalidates_query_load_and_chunk_handles(source, tmp_path):
    encoder = FixtureEncoder(); old = build(source, tmp_path, encoder)
    (source / "package/cache.py").write_text("def expiry(ttl):\n    return ttl <= 0\n")
    with pytest.raises(ValueError, match="Original source changed"):
        query(old, "expiry", mode="lexical")
    with pytest.raises(ValueError, match="Original source changed"):
        load_index(tmp_path / "indices", old.index_id, source, "package/", REVISION)
    new_encoder = FixtureEncoder()
    new = build(source, tmp_path, new_encoder, previous=old)
    old_ids = {item["id"] for item in old.chunks if item["path"] == "package/cache.py"}
    new_ids = {item["id"] for item in new.chunks if item["path"] == "package/cache.py"}
    assert old_ids.isdisjoint(new_ids) and new.index_id != old.index_id
    assert len(new_encoder.documents) < len(new.chunks)
    assert new.encoding_metadata


@pytest.mark.parametrize("bad", ["shape", "nan", "zero", "integer"])
def test_invalid_encoder_results_fail_before_persistence(source, tmp_path, bad):
    class Broken(FixtureEncoder):
        def encode(self, texts):
            if bad == "shape": return np.ones((len(texts), 2), dtype=np.float32)
            if bad == "nan": return np.full((len(texts), 3), np.nan)
            if bad == "zero": return np.zeros((len(texts), 3), dtype=np.float32)
            return np.ones((len(texts), 3), dtype=np.int32)
    with pytest.raises(ValueError):
        build(source, tmp_path, Broken())
    assert not (tmp_path / "indices").exists()


def test_corrupt_index_bytes_refused_without_pickle_loading(source, tmp_path):
    index = build(source, tmp_path, FixtureEncoder())
    path = index.directory / "vectors.npy"; raw = path.read_bytes(); path.write_bytes(raw[:-4] + b"oops")
    with pytest.raises(ValueError, match="content hash"):
        load_index(tmp_path / "indices", index.index_id, source, "package/", REVISION)


def _repackage(index, vectors):
    raw = io.BytesIO(); np.save(raw, vectors, allow_pickle=False)
    files = {"index.json": (index.directory / "index.json").read_bytes(), "vectors.npy": raw.getvalue()}
    descriptors = {name: {"bytes": len(raw), "sha256": core._sha(raw)} for name, raw in files.items()}
    identifier = core._digest({"version": core.VERSION, "files": descriptors})
    directory = index.directory.parent / identifier; directory.mkdir()
    for name, raw in files.items(): (directory / name).write_bytes(raw)
    (directory / "manifest.json").write_bytes(core._json({"version": core.VERSION, "index_id": identifier, "files": descriptors}))
    return identifier


@pytest.mark.parametrize("bad", ["shape", "nan", "zero", "float64"])
def test_corrupt_but_rehashed_vector_package_still_refused(source, tmp_path, bad):
    index = build(source, tmp_path, FixtureEncoder())
    vectors = index.vectors.copy()
    if bad == "shape": vectors = vectors[:, :2]
    elif bad == "nan": vectors[0, 0] = np.nan
    elif bad == "zero": vectors[0] = 0
    elif bad == "float64": vectors = vectors.astype(np.float64)
    identifier = _repackage(index, vectors)
    with pytest.raises(ValueError, match="shape|dtype|non-finite|normalized"):
        load_index(tmp_path / "indices", identifier, source, "package/", REVISION)


def test_model_revision_and_source_revision_mismatches_refused(source, tmp_path):
    encoder = FixtureEncoder(); index = build(source, tmp_path, encoder)
    other = FixtureEncoder(); other.identity = {**other.identity, "revision": "different"}
    with pytest.raises(ValueError, match="Query encoder differs"):
        query(index, "expiry", encoder=other)
    with pytest.raises(ValueError, match="revision"):
        load_index(tmp_path / "indices", index.index_id, source, "package/", "b" * 40)


def test_resource_limits_and_index_source_overlap_fail_closed(source, tmp_path):
    with pytest.raises(ValueError, match="file or byte budget"):
        chunks_from_source(source, "package/", REVISION, Limits(max_files=1))
    with pytest.raises(ValueError, match="never raised"):
        Limits(max_files=4001)
    with pytest.raises(ValueError, match="separate from original source"):
        build_index(source, "package/", REVISION, source / "index")
    (source / "package/line.py").write_text("value = '" + "x" * 8000 + "'\n")
    with pytest.raises(ValueError, match="complete original source line"):
        chunks_from_source(source, "package/", REVISION)


class CapturingWorkspace:
    def __init__(self, source):
        self.source = source
        self.case = {"revision": REVISION, "approved_prefix": "package/"}
        self.registry = SimpleNamespace(directory=lambda case: source.parent)
        self.calls = []

    def read_original(self, path, start, end):
        self.calls.append((path, start, end))
        raw = (self.source / path).read_bytes()
        lines = raw.decode().splitlines(keepends=True)[start-1:end]
        reference = {"path": path, "source_digest": core._sha(raw), "start_line": start, "end_line": end,
                     "excerpt_id": "a" * 64}
        return {"reference": reference, "source": "original_snapshot",
                "text": "".join(f"{number}: {line}" for number, line in enumerate(lines, start))}


def test_capture_reuses_original_source_api_and_records_ranking_without_hints(source, tmp_path):
    index = build(source, tmp_path)
    result = query(index, "expiry", mode="lexical", limit=1)
    workspace = CapturingWorkspace(source)
    observations, audit = capture(workspace, result)
    assert len(workspace.calls) == 1 and len(observations) == 1
    assert observations[0]["result"]["source"] == "original_snapshot"
    assert audit["captured_references"][0]["reference"]["path"] == "package/cache.py"
    assert "no reference repairs" in audit["scope"]
    assert not any(key in audit for key in ("entry_files", "reference_patch", "hidden_tests"))


def test_capture_after_any_indexed_source_mutation_refuses_stale_authority(source, tmp_path):
    index = build(source, tmp_path)
    result = query(index, "expiry", mode="lexical", limit=1)
    (source / "package/other.py").write_text("changed = True\n")
    workspace = CapturingWorkspace(source)
    with pytest.raises(ValueError, match="Original source changed after retrieval"):
        capture(workspace, result)
    assert workspace.calls == []


def test_faiss_is_optional_explicit_and_never_silently_selected(source, tmp_path, monkeypatch):
    original = core.importlib.util.find_spec
    monkeypatch.setattr(core.importlib.util, "find_spec", lambda name: None if name == "faiss" else original(name))
    with pytest.raises(ValueError, match="not installed"):
        build(source, tmp_path, FixtureEncoder(), exact_backend="faiss")
