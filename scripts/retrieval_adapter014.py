"""Train a small retrieval projection over reviewed, frozen CodeRank embeddings.

No encoder is loaded, changed or downloaded. The CLI admits only an independently
hash-bound preparation013 export whose original gate recomputes to ready.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib
import io
import json
import math
from pathlib import Path
import random
import tempfile
import zipfile

import torch
from torch import nn
from torch.nn import functional as F
from safetensors.torch import load as load_tensors, save_file

VERSION = "kairos-retrieval-adapter014-v1"
CACHE_VERSION = "kairos-frozen-embeddings014-v1"
PROTOCOL = {
    "seed": 14014, "rank": 16, "steps": 200, "batch_size": 16,
    "learning_rate": 0.003, "learning_rate_floor": 0.1,
    "temperature": 0.1, "weight_decay": 0.0, "betas": [0.9, 0.999],
    "epsilon": 1e-8, "max_grad_norm": 1.0, "evaluate_every": 20,
    "recall_k": [1, 5, 10], "threads": 2,
    "selection": "development MRR, then Recall@5, earliest step on ties",
    "loss": "softplus((cos(query, negative)-cos(query, positive))/temperature)",
    "schedule": "cosine over fixed global steps, with learning_rate_floor",
    "pair_weighting": "each issue family or source-function target has equal total pair weight",
}
ENCODER = {
    "model_id": "nomic-ai/CodeRankEmbed",
    "revision": "3c4b60807d71f79b43f3c4363786d9493691f8b1",
    "dimension": 768, "pooling": "cls", "normalize": True,
    "max_tokens": 512,
    "query_prefix": "Represent this query for searching relevant code: ",
}
APPROVED_PROFILE_SHA256 = "2aa1ac9712e4e22d3be04c46dd136245ad18f304999a244c308e699c158d99c0"
MAX_BYTES = 32 * 1024 * 1024
MEMBERS = {"train.jsonl", "development.jsonl", "rights.json", "manifest.json", "allowlist.json"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def is_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def require_frozen_encoder(encoder, message="unsupported frozen encoder"):
    """Require the exact approved encoder recipe, including its full profile."""
    require(type(encoder) is dict and set(encoder) == set(ENCODER) | {"profile_sha256"}
            and all(encoder[key] == value and type(encoder[key]) is type(value)
                    for key, value in ENCODER.items())
            and encoder["profile_sha256"] == APPROVED_PROFILE_SHA256, message)


def json_bytes(value):
    def pairs(items):
        result = {}
        for key, item in items:
            require(key not in result, "duplicate JSON key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "non-finite JSON number"))


def read_bytes(path, maximum=MAX_BYTES):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "input traverses symlink")
    require(path.is_file() and path.stat().st_size <= maximum, "missing or oversized input")
    return path.read_bytes()


@dataclass(frozen=True)
class ReviewedBundle:
    rows: dict
    identity: dict


def load_reviewed_bundle(archive, receipt, inventory, frozen, audit, expected_hashes):
    """Recompute the unchanged preparation013 gate and exact public member bytes.

    expected_hashes must come from the curator's separate trusted review record,
    not from the files being verified. They bind the five original file bytes.
    The private inventory/audit never enter the encoder or optimizer.
    """
    paths = dict(archive=archive, receipt=receipt, inventory=inventory, frozen=frozen, audit=audit)
    require(set(expected_hashes) == set(paths) and all(is_hash(v) for v in expected_hashes.values()),
            "all five externally trusted input hashes are required")
    raw = {name: read_bytes(path, 16 * 1024 * 1024) for name, path in paths.items()}
    require(all(sha(raw[name]) == expected_hashes[name] for name in paths), "trusted input hash mismatch")
    prep = importlib.import_module("scripts.training_bundle013")
    data, seal, export_receipt = (json_bytes(raw[name]) for name in ("inventory", "frozen", "receipt"))
    actual, _, _ = prep.freeze(data, raw["audit"])
    require(canonical(actual) == canonical(seal), "frozen inventory/protocol drift")
    require(seal["protocol"] == {"seed": "kairos-cloud013-v1\n", "floors": {"train": 40, "development": 8, "holdout": 16},
                                  "development_per_repository": 4, "holdout_per_repository": 8},
            "preparation013 gate changed")
    require(seal["training_data_ready"] is True and not seal["gate_shortfalls"], "training data is not ready")
    require(export_receipt == {"archive_sha256": sha(raw["archive"]), "archive_bytes": len(raw["archive"]),
                              "files": sorted(MEMBERS), "training_data_ready": True},
            "archive receipt mismatch or gate false")
    # Regenerate reviewed public content with the original exporter. This checks
    # labels, rows, weights, rights, manifests and allowlist without reimplementing
    # its schema. The archive's exact original bytes remain independently bound.
    with tempfile.TemporaryDirectory(prefix="kairos014-admission-", dir=Path(tempfile.gettempdir()).resolve()) as temporary:
        rebuilt = Path(temporary) / "rebuilt"
        prep.export(data, seal, rebuilt, raw["audit"])
        with zipfile.ZipFile(io.BytesIO(raw["archive"])) as bundle:
            names = bundle.namelist()
            require(len(names) == len(MEMBERS) and set(names) == MEMBERS, "archive allowlist mismatch")
            require(sum(info.file_size for info in bundle.infolist()) <= 16 * 1024 * 1024,
                    "archive exceeds preparation bound")
            public = {}
            for info in bundle.infolist():
                require((info.external_attr >> 16) & 0o170000 == 0o100000, "archive member is not regular")
                content = bundle.read(info)
                require(content == (rebuilt / "public" / info.filename).read_bytes(), "export member drift")
                public[info.filename] = content
    rows = {}
    for split in ("train", "development"):
        rows[split] = [json_bytes(line) for line in public[split + ".jsonl"].splitlines()]
        require(bool(rows[split]), "training and development both need rows")
        for row in rows[split]:
            require(row["kind"] == "retrieval" and row["schema_version"] == "kairos-retrieval-training-v1",
                    "adapter accepts retrieval labels only")
            require(row["split"] == split, "split mismatch")
            prep.model_input(row)
    return ReviewedBundle(rows, {"data_kind": "reviewed", "input_sha256": dict(expected_hashes),
                                "frozen_sha256": sha(canonical(seal)), "study_id": seal["study_id"],
                                "preparation_implementation_sha256": seal["implementation_sha256"]})


def load_source_bundle(data_directory, expected_frozen_sha256):
    """Separate source-only protocol; it cannot change the preparation013 gate."""
    try:
        source = importlib.import_module("scripts.build_functions014")
    except ModuleNotFoundError as error:
        if error.name != "scripts.build_functions014":
            raise
        source = importlib.import_module("build_functions014")
    train, development, identity = source.load_for_training014(data_directory, expected_frozen_sha256)
    require(identity["data_kind"] == "source-only-docstring-retrieval-pilot"
            and identity["source_only_training_data_ready"] is True
            and identity["original013_issue_family_training_data_ready"] is False,
            "source-only admission must preserve original issue-family boundary")
    return ReviewedBundle({"train": train, "development": development}, identity)


@dataclass(frozen=True)
class EmbeddingCache:
    vectors: dict
    dimension: int
    identity: dict


def load_embedding_cache(path, expected_sha256, bundle):
    """Load only exact model_input(row) hashes; targets never become inputs."""
    require(set(bundle.rows) == {"train", "development"}, "training cache cannot contain held-out splits")
    require(all(row.get("split") == split for split, rows in bundle.rows.items() for row in rows),
            "training cache row split mismatch")
    raw = read_bytes(path)
    require(is_hash(expected_sha256) and sha(raw) == expected_sha256, "embedding cache hash mismatch")
    cache = json_bytes(raw)
    require(set(cache) == {"schema_version", "frozen_sha256", "encoder", "rows"}, "cache fields mismatch")
    require(cache["schema_version"] == CACHE_VERSION and cache["frozen_sha256"] == bundle.identity["frozen_sha256"],
            "cache frozen identity mismatch")
    encoder = cache["encoder"]
    require_frozen_encoder(encoder)
    require(type(cache["rows"]) is list, "cache rows must be a list")
    original = {row["example_id"]: row for rows in bundle.rows.values() for row in rows}
    require(len(original) == sum(map(len, bundle.rows.values())), "duplicate exported example")
    vectors = {}
    prep = importlib.import_module("scripts.training_bundle013") if bundle.identity["data_kind"] == "reviewed" else None
    for row in cache["rows"]:
        require(type(row) is dict and set(row) == {"example_id", "query_sha256", "code_sha256", "query", "code"},
                "cache row fields mismatch")
        name = row["example_id"]
        require(name in original and name not in vectors, "unknown, duplicate or held-out cache row")
        inputs = prep.model_input(original[name]) if prep else {key: original[name][key] for key in ("query", "code")}
        require(row["query_sha256"] == sha(inputs["query"]) and row["code_sha256"] == sha(inputs["code"]),
                "cache does not bind exact model input")
        values = []
        for field in ("query", "code"):
            vector = row[field]
            require(type(vector) is list and len(vector) == encoder["dimension"]
                    and all(type(v) in (float, int) and math.isfinite(v) for v in vector), "invalid embedding vector")
            tensor = torch.tensor(vector, dtype=torch.float32)
            norm = float(torch.linalg.vector_norm(tensor))
            require(torch.isfinite(tensor).all().item() and math.isfinite(norm) and 0.99 <= norm <= 1.01,
                    "cache vector is not finite, nonzero and L2 normalized")
            values.append(F.normalize(tensor, dim=0))
        vectors[name] = tuple(values)
    require(set(vectors) == set(original), "cache must cover exactly exported rows")
    return EmbeddingCache(vectors, encoder["dimension"], {"cache_sha256": expected_sha256, "encoder": encoder,
                                                        "frozen_sha256": bundle.identity["frozen_sha256"]})


class ResidualProjection(nn.Module):
    """Shared low-rank residual: normalize(x + up(down(x)))."""

    def __init__(self, dimension, rank=16):
        super().__init__()
        self.dimension, self.rank = dimension, rank
        self.down = nn.Linear(dimension, rank, bias=False)
        self.up = nn.Linear(rank, dimension, bias=False)
        nn.init.normal_(self.down.weight, mean=0, std=0.02)
        nn.init.zeros_(self.up.weight)

    def forward(self, vectors):
        return F.normalize(vectors + self.up(self.down(vectors)), p=2, dim=-1)


def groups_for(rows, vectors):
    """No in-batch or cross-issue negatives. Every group needs both labels."""
    groups = defaultdict(list)
    for row in rows:
        require(row["split"] in {"train", "development"}, "held-out rows cannot enter trainer")
        require(type(row["relevance"]) is int and row["relevance"] in (0, 1), "unreviewed relevance")
        groups[(row["component_key"], row["issue_sha256"], row["source_commit"])].append(row)
    result = []
    for key, members in sorted(groups.items()):
        members.sort(key=lambda row: row["example_id"])
        require({row["relevance"] for row in members} == {0, 1}, "each issue/revision needs positive and negative labels")
        query = vectors[members[0]["example_id"]][0]
        require(all(torch.equal(query, vectors[row["example_id"]][0]) for row in members),
                "same query has inconsistent cached embeddings")
        result.append({"key": key, "rows": members, "query": query,
                       "codes": torch.stack([vectors[row["example_id"]][1] for row in members])})
    require(bool(result), "no paired issues")
    return result


def source_groups_for(rows, vectors):
    """Natural docstring target versus other functions in its own split/repo.

    Other functions are contrastive pseudo-negatives, not reviewed irrelevant.
    The target's own docstring was removed by the separately reviewed source
    preparation module. Every metric therefore measures source matching only.
    """
    require(all(row["split"] in ("train", "development") for row in rows), "held-out rows cannot enter trainer")
    require(len({row["example_id"] for row in rows}) == len(rows), "duplicate source row")
    result = []
    for target in sorted(rows, key=lambda row: row["example_id"]):
        members = sorted((row for row in rows if row["repository"] == target["repository"]),
                         key=lambda row: row["example_id"])
        require(len(members) >= 2, "source contrastive group needs two functions")
        result.append({"key": (target["example_id"], target["query_sha256"], target["source_commit"]),
                       "unit_kind": "source_function",
                       "rows": [{"example_id": row["example_id"], "relevance": int(row["example_id"] == target["example_id"])}
                                for row in members],
                       "query": vectors[target["example_id"]][0],
                       "codes": torch.stack([vectors[row["example_id"]][1] for row in members])})
    return result


def pair_table(groups):
    pairs = []
    for index, group in enumerate(groups):
        positives = [i for i, row in enumerate(group["rows"]) if row["relevance"] == 1]
        negatives = [i for i, row in enumerate(group["rows"]) if row["relevance"] == 0]
        pairs.extend((index, positive, negative) for positive in positives for negative in negatives)
    counts = Counter(groups[g]["key"][0] for g, _, _ in pairs)
    weights = [len(pairs) / (len(counts) * counts[groups[g]["key"][0]]) for g, _, _ in pairs]
    return pairs, weights


@torch.no_grad()
def paired_metrics(groups, model=None, device="cpu"):
    """Report base and adapter on identical labeled issue candidate sets.

    These are candidate-set metrics, not complete source-corpus recall. Ties use
    stable example_id order. Multiple revisions average within their component.
    """
    records = []
    for group in groups:
        query, codes = group["query"].to(device), group["codes"].to(device)
        base = codes @ query
        adapted = model(codes) @ model(query) if model is not None else base
        result = {"unit_id": group["key"][0], "source_commit": group["key"][2], "candidates": len(group["rows"]),
                  "positive_candidates": sum(row["relevance"] for row in group["rows"])}
        source_only = group.get("unit_kind") == "source_function"
        result.update({"example_id": group["key"][0], "query_sha256": group["key"][1]} if source_only
                      else {"component_key": group["key"][0], "issue_sha256": group["key"][1]})
        for name, scores in (("base", base), ("adapter", adapted)):
            order = sorted(range(len(group["rows"])), key=lambda i: (-float(scores[i]), group["rows"][i]["example_id"]))
            ranks = [rank + 1 for rank, i in enumerate(order) if group["rows"][i]["relevance"] == 1]
            result[name] = {"mrr": 1 / min(ranks), **{f"recall@{k}": sum(rank <= k for rank in ranks) / len(ranks)
                                                       for k in PROTOCOL["recall_k"]}}
        result["delta"] = {key: result["adapter"][key] - result["base"][key] for key in result["base"]}
        records.append(result)
    families = defaultdict(list)
    for row in records:
        families[row["unit_id"]].append(row)
    summary = {}
    for arm in ("base", "adapter", "delta"):
        summary[arm] = {key: sum(sum(row[arm][key] for row in members) / len(members)
                                 for members in families.values()) / len(families)
                        for key in records[0][arm]}
    source_only = groups[0].get("unit_kind") == "source_function"
    return {"scope": ("docstring-to-own-function targets; same-split repository candidates; other functions unjudged"
                      if source_only else "labeled within-issue candidate sets; family macro average"),
            "units": len(families), "unit_kind": "source_function" if source_only else "issue_family",
            "queries": len(records), "summary": summary, "paired": records}


class PairSampler:
    def __init__(self, size):
        self.size, self.order, self.cursor, self.epoch = size, [], 0, 0
        self.generator = torch.Generator(device="cpu").manual_seed(PROTOCOL["seed"] + 1)

    def take(self, count):
        result = []
        while len(result) < count:
            if self.cursor == len(self.order):
                self.order = torch.randperm(self.size, generator=self.generator).tolist()
                self.cursor, self.epoch = 0, self.epoch + 1
            available = min(count - len(result), len(self.order) - self.cursor)
            result.extend(self.order[self.cursor:self.cursor + available])
            self.cursor += available
        return result


def pack(value, tensors, prefix):
    """Encode optimizer/RNG containers as JSON with safe tensor references."""
    if isinstance(value, torch.Tensor):
        tensors[prefix] = value.detach().cpu().contiguous()
        return {"tensor": prefix}
    if isinstance(value, dict):
        return {"dict": [[pack(k, tensors, f"{prefix}.key{i}"), pack(v, tensors, f"{prefix}.value{i}")]
                         for i, (k, v) in enumerate(value.items())]}
    if isinstance(value, (tuple, list)):
        return {"tuple" if isinstance(value, tuple) else "list": [pack(v, tensors, f"{prefix}.{i}") for i, v in enumerate(value)]}
    require(value is None or type(value) in (str, int, float, bool), "unsupported state type")
    require(type(value) is not float or math.isfinite(value), "non-finite state")
    return value


def unpack(value, tensors):
    if not isinstance(value, dict):
        return value
    require(len(value) == 1, "invalid safe state container")
    kind, contents = next(iter(value.items()))
    if kind == "tensor":
        require(contents in tensors, "missing state tensor")
        return tensors[contents]
    if kind == "dict":
        return {unpack(k, tensors): unpack(v, tensors) for k, v in contents}
    require(kind in ("tuple", "list"), "invalid safe state tag")
    result = [unpack(v, tensors) for v in contents]
    return tuple(result) if kind == "tuple" else result


def configure(device):
    require(device in ("cpu", "cuda"), "device must be cpu or cuda")
    require(device != "cuda" or torch.cuda.is_available(), "CUDA is unavailable")
    if device == "cuda":
        import os
        require(os.environ.get("CUBLAS_WORKSPACE_CONFIG") in (":4096:8", ":16:8"),
                "set CUBLAS_WORKSPACE_CONFIG=:4096:8 before a CUDA run")
    torch.set_num_threads(PROTOCOL["threads"])
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    random.seed(PROTOCOL["seed"])
    torch.manual_seed(PROTOCOL["seed"])
    if device == "cuda":
        torch.cuda.manual_seed_all(PROTOCOL["seed"])
    return {"torch": torch.__version__, "device": device, "threads": torch.get_num_threads(),
            "cuda": torch.version.cuda if device == "cuda" else None,
            "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None}


class TrainingSession:
    """Training mechanics. Production callers must use fit's reviewed admission."""

    def __init__(self, rows, cache, identity, device="cpu"):
        self.runtime = configure(device)
        self.device, self.identity = device, identity
        grouper = source_groups_for if identity["data_kind"] == "source-only-docstring-retrieval-pilot" else groups_for
        self.groups = {split: grouper(rows[split], cache.vectors) for split in ("train", "development")}
        self.pairs, self.weights = pair_table(self.groups["train"])
        self.sampler = PairSampler(len(self.pairs))
        self.model = ResidualProjection(cache.dimension, PROTOCOL["rank"]).to(device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=PROTOCOL["learning_rate"],
                                          betas=tuple(PROTOCOL["betas"]), eps=PROTOCOL["epsilon"],
                                          weight_decay=PROTOCOL["weight_decay"], foreach=False, fused=False)
        self.step, self.loss_trace = 0, []
        initial = paired_metrics(self.groups["development"], self.model, device)
        self.history = [{"step": 0, "metrics": initial}]
        self.best_step, self.best_score = 0, self.score(initial)
        self.best_state = {key: value.detach().cpu().clone() for key, value in self.model.state_dict().items()}

    @staticmethod
    def score(metrics):
        return [metrics["summary"]["adapter"][key] for key in ("mrr", "recall@5")]

    def update(self):
        require(self.step < PROTOCOL["steps"], "fixed schedule already complete")
        selected = self.sampler.take(PROTOCOL["batch_size"])
        queries, positives, negatives = [], [], []
        for index in selected:
            g, p, n = self.pairs[index]
            group = self.groups["train"][g]
            queries.append(group["query"])
            positives.append(group["codes"][p])
            negatives.append(group["codes"][n])
        query, positive, negative = [self.model(torch.stack(values).to(self.device))
                                     for values in (queries, positives, negatives)]
        loss = F.softplus(((query * negative).sum(-1) - (query * positive).sum(-1)) / PROTOCOL["temperature"])
        loss = (loss * torch.tensor([self.weights[i] for i in selected], device=self.device)).mean()
        require(torch.isfinite(loss).item(), "non-finite loss")
        ratio = 0.5 * (1 + math.cos(math.pi * self.step / PROTOCOL["steps"]))
        learning_rate = PROTOCOL["learning_rate"] * (PROTOCOL["learning_rate_floor"] + (1 - PROTOCOL["learning_rate_floor"]) * ratio)
        for group in self.optimizer.param_groups:
            group["lr"] = learning_rate
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(self.model.parameters(), PROTOCOL["max_grad_norm"], error_if_nonfinite=True)
        self.optimizer.step()
        self.step += 1
        self.loss_trace.append(float(loss.detach()))
        if self.step % PROTOCOL["evaluate_every"] == 0 or self.step == PROTOCOL["steps"]:
            metrics = paired_metrics(self.groups["development"], self.model, self.device)
            self.history.append({"step": self.step, "metrics": metrics})
            if self.score(metrics) > self.best_score:
                self.best_step, self.best_score = self.step, self.score(metrics)
                self.best_state = {key: value.detach().cpu().clone() for key, value in self.model.state_dict().items()}
        return float(loss.detach())

    def save(self, directory):
        directory = Path(directory).absolute()
        require(not any(p.is_symlink() for p in (directory, *directory.parents)), "checkpoint output traverses symlink")
        directory.mkdir(parents=True, exist_ok=False)
        tensors = {"model." + key: value.detach().cpu().contiguous() for key, value in self.model.state_dict().items()}
        tensors.update({"best." + key: value.clone().contiguous() for key, value in self.best_state.items()})
        tensors["rng.torch_cpu"] = torch.get_rng_state()
        tensors["rng.sampler"] = self.sampler.generator.get_state()
        cuda_keys = []
        if self.device == "cuda":
            for i, state in enumerate(torch.cuda.get_rng_state_all()):
                name = f"rng.cuda.{i}"
                tensors[name] = state
                cuda_keys.append(name)
        metadata = {"schema_version": VERSION, "identity": self.identity, "protocol": PROTOCOL,
                    "runtime": self.runtime, "dimension": self.model.dimension,
                    "step": self.step, "best_step": self.best_step, "best_score": self.best_score,
                    "history": self.history, "loss_trace": self.loss_trace,
                    "optimizer": pack(self.optimizer.state_dict(), tensors, "optimizer"),
                    "python_rng": pack(random.getstate(), tensors, "rng.python"),
                    "cuda_rng_keys": cuda_keys,
                    "sampler": {"size": self.sampler.size, "order": self.sampler.order,
                                "cursor": self.sampler.cursor, "epoch": self.sampler.epoch}}
        save_file(tensors, str(directory / "state.safetensors"))
        metadata["tensors_sha256"] = sha(read_bytes(directory / "state.safetensors"))
        (directory / "manifest.json").write_bytes(canonical(metadata) + b"\n")
        return sha(read_bytes(directory / "manifest.json"))

    def restore(self, directory, expected_manifest_sha256):
        metadata, tensors = read_checkpoint(directory, expected_manifest_sha256)
        require(metadata["identity"] == self.identity and metadata["protocol"] == PROTOCOL,
                "checkpoint data, implementation or protocol changed")
        require(metadata["runtime"] == self.runtime and metadata["dimension"] == self.model.dimension,
                "exact resume requires unchanged device/runtime/dimension")
        self.model.load_state_dict({key: tensors["model." + key] for key in self.model.state_dict()}, strict=True)
        self.best_state = {key: tensors["best." + key].clone() for key in self.model.state_dict()}
        self.optimizer.load_state_dict(unpack(metadata["optimizer"], tensors))
        self.step, self.best_step, self.best_score = metadata["step"], metadata["best_step"], metadata["best_score"]
        require(type(self.step) is int and 0 <= self.step <= PROTOCOL["steps"], "invalid global step")
        self.history, self.loss_trace = metadata["history"], metadata["loss_trace"]
        require(len(self.loss_trace) == self.step, "incomplete loss history")
        sampler = metadata["sampler"]
        valid_order = sorted(sampler["order"]) == list(range(len(self.pairs))) or self.step == 0 and sampler["order"] == []
        require(sampler["size"] == len(self.pairs) and valid_order
                and 0 <= sampler["cursor"] <= len(self.pairs), "invalid sampler state")
        self.sampler.order, self.sampler.cursor, self.sampler.epoch = sampler["order"], sampler["cursor"], sampler["epoch"]
        self.sampler.generator.set_state(tensors["rng.sampler"])
        random.setstate(unpack(metadata["python_rng"], tensors))
        torch.set_rng_state(tensors["rng.torch_cpu"])
        if self.device == "cuda":
            require(len(metadata["cuda_rng_keys"]) == torch.cuda.device_count(), "CUDA device count changed")
            torch.cuda.set_rng_state_all([tensors[key] for key in metadata["cuda_rng_keys"]])


def read_checkpoint(directory, expected_manifest_sha256):
    directory = Path(directory)
    raw = read_bytes(directory / "manifest.json")
    require(is_hash(expected_manifest_sha256) and sha(raw) == expected_manifest_sha256, "checkpoint manifest hash mismatch")
    metadata = json_bytes(raw)
    require(metadata["schema_version"] == VERSION, "checkpoint schema mismatch")
    weights = read_bytes(directory / "state.safetensors")
    require(sha(weights) == metadata["tensors_sha256"], "checkpoint tensor hash mismatch")
    tensors = load_tensors(weights)
    require(all(torch.isfinite(tensor).all().item() for tensor in tensors.values()), "non-finite checkpoint tensor")
    return metadata, tensors


def load_projection(directory, expected_manifest_sha256, *, device="cpu"):
    """Load only development-selected adapter weights for a separate evaluator."""
    metadata, tensors = read_checkpoint(directory, expected_manifest_sha256)
    require(metadata["protocol"] == PROTOCOL, "projection protocol mismatch")
    model = ResidualProjection(metadata["dimension"], PROTOCOL["rank"]).to(device)
    model.load_state_dict({key: tensors["best." + key] for key in model.state_dict()}, strict=True)
    model.eval()
    return model, metadata


def export_projection(directory, expected_manifest_sha256, output):
    """Export the selected tiny head as JSON, without optimizer, RNG or data."""
    model, metadata = load_projection(directory, expected_manifest_sha256)
    require(model.dimension == ENCODER["dimension"], "inference shape mismatch")
    require_frozen_encoder(metadata["identity"].get("encoder"), "unsupported inference encoder")
    output = Path(output).absolute()
    require(not any(p.is_symlink() for p in (output, *output.parents)) and not output.exists(),
            "inference output must be a new directory without symlinks")
    artifact = {"schema_version": VERSION, "dimension": model.dimension, "rank": model.rank,
                "selected_step": metadata["best_step"], "encoder": metadata["identity"].get("encoder"),
                "transform": "L2 normalize(x + up(down(x))); shared query and code projection",
                "weights": {key: value.detach().cpu().tolist() for key, value in model.state_dict().items()}}
    encoded = canonical(artifact) + b"\n"
    manifest = {"schema_version": VERSION, "data_kind": metadata["identity"]["data_kind"],
                "frozen_sha256": metadata["identity"].get("frozen_sha256"),
                "source_checkpoint_manifest_sha256": expected_manifest_sha256,
                "files": {"adapter.json": {"sha256": sha(encoded), "bytes": len(encoded)}}}
    output.mkdir(parents=True)
    (output / "adapter.json").write_bytes(encoded)
    (output / "manifest.json").write_bytes(canonical(manifest) + b"\n")
    return sha(read_bytes(output / "manifest.json"))


def load_inference_projection(directory, expected_manifest_sha256, *, device="cpu"):
    """Load a hash-bound JSON head; no pickle, optimizer or training data."""
    directory = Path(directory)
    raw = read_bytes(directory / "manifest.json")
    require(is_hash(expected_manifest_sha256) and sha(raw) == expected_manifest_sha256, "inference manifest hash mismatch")
    manifest = json_bytes(raw)
    require(manifest["schema_version"] == VERSION and set(manifest["files"]) == {"adapter.json"}, "inference allowlist mismatch")
    require({path.name for path in directory.iterdir()} == {"adapter.json", "manifest.json"}, "unexpected inference export files")
    contents = read_bytes(directory / "adapter.json")
    require(manifest["files"]["adapter.json"] == {"sha256": sha(contents), "bytes": len(contents)}, "inference tensor hash mismatch")
    artifact = json_bytes(contents)
    dimension = artifact["dimension"]
    require(artifact["schema_version"] == VERSION and type(dimension) is int and dimension == ENCODER["dimension"]
            and artifact["rank"] == PROTOCOL["rank"], "inference shape mismatch")
    require_frozen_encoder(artifact.get("encoder"), "unsupported inference encoder")
    shapes = {"down.weight": (PROTOCOL["rank"], dimension), "up.weight": (dimension, PROTOCOL["rank"])}
    require(set(artifact["weights"]) == set(shapes), "inference weight inventory mismatch")
    state = {}
    for name, (height, width) in shapes.items():
        values = artifact["weights"][name]
        require(type(values) is list and len(values) == height and all(type(row) is list and len(row) == width
                and all(type(v) in (int, float) and math.isfinite(v) for v in row) for row in values), "invalid inference weights")
        state[name] = torch.tensor(values, dtype=torch.float32)
        require(torch.isfinite(state[name]).all().item(), "non-finite inference weight")
    model = ResidualProjection(dimension, PROTOCOL["rank"]).to(device)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model, {"manifest": manifest, "config": {key: value for key, value in artifact.items() if key != "weights"}}


def fit(bundle, cache, output, *, device="cpu", resume=None, resume_sha256=None, stop_after=None):
    """Run only admitted reviewed data. Fixtures use TrainingSession directly."""
    require(bundle.identity.get("data_kind") in ("reviewed", "source-only-docstring-retrieval-pilot"),
            "production fit requires reviewed data")
    require(cache.identity.get("frozen_sha256") == bundle.identity["frozen_sha256"], "cache and bundle identities differ")
    output = Path(output).absolute()
    require(not any(p.is_symlink() for p in (output, *output.parents)), "output traverses symlink")
    require(not output.exists(), "output must be new; resume into a new directory")
    identity = {**bundle.identity, **cache.identity, "trainer_implementation_sha256": sha(Path(__file__).read_bytes())}
    session = TrainingSession(bundle.rows, cache, identity, device)
    if resume is not None:
        session.restore(resume, resume_sha256)
    require(stop_after is None or type(stop_after) is int and session.step < stop_after <= PROTOCOL["steps"],
            "stop_after must be a later global step within the fixed schedule")
    output.mkdir(parents=True)
    checkpoint = output / f"checkpoint-{session.step:06d}"
    checkpoint_sha256 = session.save(checkpoint)
    stop = stop_after if stop_after is not None else PROTOCOL["steps"]
    while session.step < stop:
        session.update()
        if session.step % PROTOCOL["evaluate_every"] == 0 or session.step == stop:
            checkpoint = output / f"checkpoint-{session.step:06d}"
            checkpoint_sha256 = session.save(checkpoint)
    selected, _ = load_projection(checkpoint, checkpoint_sha256, device=device)
    report = {"schema_version": VERSION, "identity": identity, "protocol": PROTOCOL, "runtime": session.runtime,
              "status": "completed" if session.step == PROTOCOL["steps"] else "interrupted",
              "global_step": session.step, "selected_step": session.best_step,
              "parameters": sum(p.numel() for p in session.model.parameters()),
              "checkpoint": checkpoint.name, "checkpoint_manifest_sha256": checkpoint_sha256,
              "development": paired_metrics(session.groups["development"], selected, device),
              "training": paired_metrics(session.groups["train"], selected, device),
              "loss_trace": session.loss_trace, "selection_history": session.history,
              "heldout": "not loaded; evaluation must use a separate evaluator-owned store",
              "metric_limitation": "Rank and recall cover labeled within-issue candidates only; no full-corpus or repair claim."}
    (output / "training-report.json").write_bytes(canonical(report) + b"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="protocol", required=True)
    issue = sub.add_parser("issue013", help="Original issue/relevance protocol; unchanged gate")
    for name in ("archive", "receipt", "inventory", "frozen", "audit"):
        issue.add_argument("--" + name, type=Path, required=True)
        issue.add_argument("--" + name + "-sha256", required=True)
    source = sub.add_parser("source014", help="Separate natural docstring source-matching pilot")
    source.add_argument("--source-data", type=Path, required=True)
    source.add_argument("--source-frozen-sha256", required=True)
    for command in (issue, source):
        command.add_argument("--cache", type=Path, required=True)
        command.add_argument("--cache-sha256", required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
        command.add_argument("--resume", type=Path)
        command.add_argument("--resume-sha256")
        command.add_argument("--stop-after", type=int)
    args = parser.parse_args()
    try:
        if args.protocol == "issue013":
            expected = {key: getattr(args, key + "_sha256") for key in ("archive", "receipt", "inventory", "frozen", "audit")}
            bundle = load_reviewed_bundle(args.archive, args.receipt, args.inventory, args.frozen, args.audit, expected)
        else:
            bundle = load_source_bundle(args.source_data, args.source_frozen_sha256)
        cache = load_embedding_cache(args.cache, args.cache_sha256, bundle)
        report = fit(bundle, cache, args.output, device=args.device, resume=args.resume,
                     resume_sha256=args.resume_sha256, stop_after=args.stop_after)
        print(json.dumps({key: report[key] for key in ("status", "global_step", "selected_step", "checkpoint", "checkpoint_manifest_sha256")}, sort_keys=True))
    except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile) as error:
        parser.exit(2, f"Rejected: {error}\n")


if __name__ == "__main__":
    main()
