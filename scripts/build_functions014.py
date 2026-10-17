"""Prepare a source-only retrieval pilot from pinned, licensed Python functions.

This protocol is deliberately separate from issue-family training_bundle013.
Docstring/function association is a structural positive. Other functions are only
contrastive candidates and never receive asserted semantic-negative labels.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import textwrap
import unicodedata

VERSION = "kairos-licensed-functions014-v1"
MAX_BYTES = 12 * 1024 * 1024
FLOORS = {"train": 40, "development": 8, "holdout": 16}
DERIVATION = "ast_docstring_first_paragraph_to_function_remove_own_docstring_v1"
REVIEWER = "Codex source-curation014 structural review"
HISTORICAL_AUDIT_SHA256 = "c856081562e65b97206b4a1067d88d140d156fc44b0a9cfaeca621b8e7e9f3dd"
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
SECRET = re.compile(r"/Users/|/home/|/private/|-----BEGIN [^-]*PRIVATE KEY|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_-]{20,}")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def normalize(value):
    return " ".join(unicodedata.normalize("NFC", value).split())


def grams(value):
    words = re.findall(r"\w+", normalize(value).lower())
    return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}


def similar(left, right):
    if normalize(left) == normalize(right):
        return True
    a, b = grams(left), grams(right)
    return bool(a and b) and len(a & b) / len(a | b) >= 0.8


def load(path):
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Unsafe or oversized input")
    return json.loads(path.read_text())


def declarations(tree, parent=""):
    # Do not treat nested functions as independent positives.
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            yield from declarations(node, parent + node.name + ".")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield parent + node.name, node


def derive(source, node):
    """Bind an exact original AST range and document the transformed model input."""
    docstring = ast.get_docstring(node, clean=True)
    if not docstring or not node.body or not isinstance(node.body[0], ast.Expr):
        return None
    docnode = node.body[0]
    if docnode.lineno <= node.lineno or docnode.end_lineno >= node.end_lineno:
        return None
    paragraph = re.split(r"\n\s*\n", docstring, maxsplit=1)[0]
    query = " ".join(paragraph.split())
    if not 40 <= len(query) <= 600 or len(re.findall(r"\w+", query)) < 8:
        return None
    lines = source.splitlines(keepends=True)
    original = "".join(lines[node.lineno - 1:node.end_lineno])
    before = lines[node.lineno - 1:docnode.lineno - 1]
    after = lines[docnode.end_lineno:node.end_lineno]
    code = textwrap.dedent("".join(before + after))
    if not 3 <= len(code.splitlines()) <= 150 or not 50 <= len(code) <= 20000:
        return None
    if SECRET.search(query + "\n" + code) or normalize(query).lower() in normalize(code).lower():
        return None
    # Parse transformed code only. Never import or execute acquired source.
    ast.parse(code)
    return query, code, original, docnode.lineno, docnode.end_lineno


def check_acquisition(raw):
    acquisition = load(raw / "acquisition.json")
    if acquisition["schema_version"] != "kairos-function-acquisition014-v1":
        raise ValueError("Unknown acquisition schema")
    size = 0
    git_trees = {}
    for repo, receipt in acquisition["trees"].items():
        path = raw / (repo.replace("/", "__") + ".tree.json")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing pinned Git tree evidence")
        data = path.read_bytes()
        tree = json.loads(data)
        config = acquisition["repositories"][repo]
        if sha(data) != receipt["sha256"] or len(data) != receipt["bytes"] or tree.get("truncated") or tree["sha"] != receipt["tree_sha"] or receipt["url"] != f"https://api.github.com/repos/{repo}/git/trees/{config['revision']}?recursive=1":
            raise ValueError("Pinned Git tree evidence mismatch")
        git_trees[repo] = {entry["path"]: entry["sha"] for entry in tree["tree"] if entry["type"] == "blob"}
        size += len(data)
    for key, item in acquisition["objects"].items():
        path = raw / item["local_path"]
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or unsafe source blob")
        data = path.read_bytes()
        if len(data) != item["bytes"] or sha(data) != item["sha256"]:
            raise ValueError("Source acquisition hash mismatch")
        git_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if git_blob != item["git_blob_sha1"] or git_trees[item["repository"]].get(item["path"]) != git_blob:
            raise ValueError("Pinned source Git blob mismatch")
        config = acquisition["repositories"][item["repository"]]
        expected = f"https://raw.githubusercontent.com/{item['repository']}/{config['revision']}/{item['path']}"
        if item["revision"] != config["revision"] or not HEX40.fullmatch(item["revision"]) or item["origin"] != expected:
            raise ValueError("Unpinned source origin")
        size += len(data)
    if size > MAX_BYTES:
        raise ValueError("Source acquisition exceeds byte bound")
    return acquisition


def make_rows(raw, acquisition):
    rows, rejected = [], []
    for key, item in sorted(acquisition["objects"].items()):
        if not item["path"].endswith(".py"):
            continue
        source = (raw / item["local_path"]).read_bytes().decode("utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            rejected.append({"source_ref": key, "reason": "Source parser does not support pinned syntax"})
            continue
        config = acquisition["repositories"][item["repository"]]
        for qualname, node in declarations(tree):
            if node.name.startswith("_"):
                continue
            result = derive(source, node)
            if result is None:
                continue
            query, code, original, doc_start, doc_end = result
            row = {"schema_version": VERSION, "repository": item["repository"], "source_commit": item["revision"], "path": item["path"], "qualname": qualname, "start_line": node.lineno, "end_line": node.end_lineno, "query": query, "code": code, "query_sha256": sha(query), "code_sha256": sha(code), "original_code_sha256": sha(original), "source_file_sha256": item["sha256"], "source_ref": key, "license_ref": item["repository"] + ":" + config["license_path"], "split": config["split"], "derivation": DERIVATION, "removed_docstring_range": [doc_start, doc_end], "positive_provenance": "Structural association: the original function's own maintained docstring describes that function. This is not an issue relevance judgment or repair outcome."}
            row["example_id"] = sha(canonical(row))
            rows.append(row)
    return rows, rejected


def deduplicate(rows):
    """Drop all cross-repository collisions; keep one deterministic within-repo copy."""
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    edges = []
    for i, left in enumerate(rows):
        for j in range(i + 1, len(rows)):
            right = rows[j]
            fields = [key for key in ("query", "code") if similar(left[key], right[key])]
            if fields:
                parent[root(j)] = root(i)
                edges.append({"left": left["example_id"], "right": right["example_id"], "fields": fields})
    groups = {}
    for i in range(len(rows)):
        groups.setdefault(root(i), []).append(rows[i])
    retained, removals = [], []
    for group in groups.values():
        group.sort(key=lambda r: r["example_id"])
        if len({row["repository"] for row in group}) > 1:
            removals.extend({"example_id": row["example_id"], "reason": "Cross-repository exact or near duplicate query/code"} for row in group)
        else:
            retained.append(group[0])
            removals.extend({"example_id": row["example_id"], "reason": "Within-repository duplicate", "retained_example_id": group[0]["example_id"]} for row in group[1:])
    return sorted(retained, key=lambda r: r["example_id"]), {"algorithm": "NFC whitespace normalization; Unicode word-token five-gram Jaccard >=0.80 on query OR transformed code; exact normalized strings also match. All transitive cross-repository groups removed.", "threshold": 0.8, "edges": edges, "removed": removals}


def review_rights(raw, acquisition):
    rights = {}
    for repo, config in acquisition["repositories"].items():
        item = acquisition["objects"][repo + ":" + config["license_path"]]
        notice = (raw / item["local_path"]).read_text()
        if config["license"] == "Apache-2.0":
            if "Apache License" not in notice or "Version 2.0, January 2004" not in notice:
                raise ValueError("Apache license evidence mismatch")
        elif "Redistribution and use in source and binary forms" not in notice or "Neither the name" not in notice:
            raise ValueError("BSD license evidence mismatch")
        rights[repo] = {"repository": repo, "revision": config["revision"], "spdx": config["license"], "evidence_origin": item["origin"], "evidence_sha256": item["sha256"], "notice": notice, "reviewer": REVIEWER, "reviewed_at": acquisition["acquired_at"], "decision": "Permissive source license permits use, modification and redistribution subject to retained notices and stated conditions. This source-only protocol does not rely on licensing of GitHub issue text or SWE-bench packaging.", "training_allowed": True, "redistribution_allowed": True}
    return rights


def verify_rows(rows, raw, acquisition):
    generated, _ = make_rows(raw, acquisition)
    by_id = {row["example_id"]: row for row in generated}
    for row in rows:
        if row != by_id.get(row["example_id"]):
            raise ValueError("Row differs from exact source-derived content")
        content = {k: v for k, v in row.items() if k != "example_id"}
        if sha(canonical(content)) != row["example_id"]:
            raise ValueError("Example hash mismatch")
    if len({r["example_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate example ID")
    repositories = {split: {r["repository"] for r in rows if r["split"] == split} for split in FLOORS}
    for split, repos in repositories.items():
        if any(repos & other for key, other in repositories.items() if key != split):
            raise ValueError("Repository split contamination")


def build(raw, output, audit_path):
    raw, output = Path(raw), Path(output)
    if output.exists():
        raise ValueError("Preparation output must be new")
    acquisition = check_acquisition(raw)
    audit_bytes = Path(audit_path).read_bytes()
    if sha(audit_bytes) != HISTORICAL_AUDIT_SHA256:
        raise ValueError("Historical audit drift or substitute audit")
    audit = json.loads(audit_bytes)
    reserved_repos = set()
    local_fixture_ids = {"kairos-body-limit", "kairos-clock-lease"}
    for exposure in audit["exposures"]:
        match = re.fullmatch(r"([^/]+)__([^/]+)-\d+(?:-scope)?", exposure["instance_id"])
        if not match:
            if exposure["instance_id"] in local_fixture_ids:
                continue
            raise ValueError("Unknown exposure identity format; explicit review required")
        reserved_repos.add(match[1] + "/" + match[2])
    if reserved_repos & set(acquisition["repositories"]):
        raise ValueError("Source repository overlaps a reserved or exposed issue repository")
    candidates, rejections = make_rows(raw, acquisition)
    rows, dedup = deduplicate(candidates)
    verify_rows(rows, raw, acquisition)
    rights = review_rights(raw, acquisition)
    counts = dict(Counter(row["split"] for row in rows))
    shortfalls = [f"{split} functions: {counts.get(split, 0)} < {floor}" for split, floor in FLOORS.items() if counts.get(split, 0) < floor]
    if len(acquisition["repositories"]) != 3:
        shortfalls.append("Exactly three disjoint repositories required")
    output.mkdir(parents=True)
    (output / "public").mkdir()
    (output / "evaluation-private").mkdir()
    for split in FLOORS:
        destination = output / ("evaluation-private" if split == "holdout" else "public") / (split + ".jsonl")
        destination.write_bytes(b"".join(canonical(row) + b"\n" for row in rows if row["split"] == split))
    (output / "public" / "rights.json").write_bytes(canonical({repo: right for repo, right in rights.items() if acquisition["repositories"][repo]["split"] != "holdout"}) + b"\n")
    (output / "rights.private.json").write_bytes(canonical(rights) + b"\n")
    (output / "deduplication.private.json").write_bytes(canonical(dedup) + b"\n")
    (output / "acquisition-exposure.private.json").write_bytes(canonical({"schema_version": VERSION, "prior_audit_sha256": sha(audit_bytes), "kind": "source_function_acquisition", "repositories": acquisition["repositories"], "example_ids_by_split": {split: [r["example_id"] for r in rows if r["split"] == split] for split in FLOORS}, "note": "Append-only current exposure record. This does not modify the preserved013 historical audit."}) + b"\n")
    manifest = {"schema_version": VERSION, "study_id": "licensed-docstring-function-retrieval014-v1", "protocol": "Source-only maintained docstring-to-function retrieval; repository-disjoint splits fixed before extraction. No issue-family or repair claims.", "derivation": DERIVATION, "acquisition_sha256": sha((raw / "acquisition.json").read_bytes()), "implementation_sha256": sha(Path(__file__).read_bytes()), "historical_audit_sha256": sha(audit_bytes), "excluded_historical_repositories": sorted(reserved_repos), "reserved_exposed_identity_count": len(audit["exposures"]), "repositories": {repo: {k: config[k] for k in ("revision", "split", "license")} for repo, config in acquisition["repositories"].items()}, "candidate_functions": len(candidates), "retained_functions": len(rows), "function_counts": counts, "function_floors": FLOORS, "source_only_training_data_ready": not shortfalls, "gate_shortfalls": shortfalls, "original013_issue_family_training_data_ready": False, "label_policy": "The maintained docstring's association with its own function is a structural positive. Other functions may be in-batch contrastive candidates; they are unjudged pseudo-negatives with false-negative risk, never independent semantic-negative labels.", "deduplication_sha256": sha((output / "deduplication.private.json").read_bytes()), "parser_rejections": rejections, "limitations": ["Function counts are not independent issue families or repaired tasks.", "One repository per split confounds language style, library domain and repository identity; this is a small transfer pilot.", "Public source may have been seen during pretrained encoder training; base-model contamination is unknown.", "No repair model training, test execution, official benchmark score or cloud upload is established.", "Licensing review is bound to exact acquired repository license notices; no GitHub issue or dataset rights are inferred."], "export_review": {"reviewer": REVIEWER, "reviewed_at": acquisition["acquired_at"], "decision": "Structural derivation, exact source/Git blob hashes, retained notices, repository split separation, exposure repository exclusion and deterministic exact/near deduplication checked. Source-only training protocol approved; original issue-family protocol remains unready."}}
    manifest["files"] = {str(p.relative_to(output)): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "manifest.private.json").write_bytes(canonical(manifest) + b"\n")
    public_manifest = {k: manifest[k] for k in ("schema_version", "study_id", "protocol", "derivation", "historical_audit_sha256", "source_only_training_data_ready", "gate_shortfalls", "original013_issue_family_training_data_ready", "label_policy", "limitations")}
    public_manifest["function_counts"] = {split: counts.get(split, 0) for split in ("train", "development")}
    public_manifest["files"] = {k.removeprefix("public/"): v for k, v in manifest["files"].items() if k.startswith("public/")}
    (output / "public" / "manifest.json").write_bytes(canonical(public_manifest) + b"\n")
    frozen = {"schema_version": VERSION, "study_id": manifest["study_id"], "data_kind": "source-only-docstring-retrieval-pilot", "derivation": DERIVATION, "repositories": manifest["repositories"], "historical_audit_sha256": manifest["historical_audit_sha256"], "excluded_historical_repositories": manifest["excluded_historical_repositories"], "function_counts": counts, "function_floors": FLOORS, "source_only_training_data_ready": not shortfalls, "gate_shortfalls": shortfalls, "original013_issue_family_training_data_ready": False, "private_manifest_sha256": sha(canonical(manifest)), "deduplication_sha256": manifest["deduplication_sha256"], "public_allowlist": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted((output / "public").iterdir())}}
    frozen["review"] = {"reviewer": REVIEWER, "reviewed_at": acquisition["acquired_at"], "approved": not shortfalls, "content_sha256": sha(canonical(frozen))}
    (output / "frozen.json").write_bytes(canonical(frozen) + b"\n")
    print(json.dumps({"candidate_functions": len(candidates), "function_counts": counts, "dedup_removed": len(dedup["removed"]), "source_only_training_data_ready": not shortfalls, "original013_issue_family_training_data_ready": False, "gate_shortfalls": shortfalls, "frozen_sha256": sha(canonical(frozen))}))


def verify(raw, output):
    raw, output = Path(raw), Path(output)
    acquisition = check_acquisition(raw)
    manifest = load(output / "manifest.private.json")
    if sha((raw / "acquisition.json").read_bytes()) != manifest["acquisition_sha256"]:
        raise ValueError("Acquisition manifest drift")
    for name, expected in manifest["files"].items():
        data = (output / name).read_bytes()
        if sha(data) != expected["sha256"] or len(data) != expected["bytes"]:
            raise ValueError("Prepared file hash mismatch")
    rows = []
    for split in FLOORS:
        path = output / ("evaluation-private" if split == "holdout" else "public") / (split + ".jsonl")
        rows += [json.loads(line) for line in path.read_text().splitlines()]
    verify_rows(rows, raw, acquisition)
    actual, report = deduplicate(make_rows(raw, acquisition)[0])
    if canonical(actual) != canonical(sorted(rows, key=lambda r: r["example_id"])):
        raise ValueError("Deduplication replay mismatch")
    if sha(canonical(report) + b"\n") != manifest["deduplication_sha256"]:
        raise ValueError("Deduplication receipt mismatch")
    print(json.dumps({"verified_rows": len(rows), "source_only_training_data_ready": manifest["source_only_training_data_ready"]}))


def load_for_training014(data_dir, expected_frozen_sha256):
    """Admit only frozen public train/development data; never read holdout files.

    expected_frozen_sha256 is SHA-256 of canonical JSON of frozen.json, without
    its terminating newline. Obtain this trusted value from the curator receipt.
    Full original source and heldout deduplication were checked before freezing;
    the loader checks that trusted frozen review and all admitted public bytes.
    """
    data_dir = Path(data_dir)
    if data_dir.is_symlink() or any(p.is_symlink() for p in data_dir.absolute().parents):
        raise ValueError("Training root cannot traverse symlinks")
    frozen = load(data_dir / "frozen.json")
    actual_frozen = sha(canonical(frozen))
    if actual_frozen != expected_frozen_sha256:
        raise ValueError("Trusted frozen hash mismatch")
    if frozen["schema_version"] != VERSION or frozen["data_kind"] != "source-only-docstring-retrieval-pilot" or frozen["derivation"] != DERIVATION:
        raise ValueError("Unrecognized source-only protocol")
    review = frozen["review"]
    content = {k: v for k, v in frozen.items() if k != "review"}
    if review["approved"] is not True or not review["reviewer"] or review["content_sha256"] != sha(canonical(content)):
        raise ValueError("Frozen source review missing or unbound")
    if frozen["source_only_training_data_ready"] is not True or frozen["gate_shortfalls"] or frozen["original013_issue_family_training_data_ready"] is not False:
        raise ValueError("Source-only gate is not ready or issue-family boundary changed")
    if frozen["function_floors"] != FLOORS or any(frozen["function_counts"].get(split, 0) < floor for split, floor in FLOORS.items()):
        raise ValueError("Source-only protocol floor changed or missed")
    expected_repos = {"pallets/jinja": ("train", "5ef70112a1ff19c05324ff889dd30405b1002044"), "pallets/flask": ("development", "d086db856be187255b8ec61ef409357393020f32"), "pallets/click": ("holdout", "2247b35ea1c47c727d7a06e51fa280e12a863ff6")}
    if set(frozen["repositories"]) != set(expected_repos):
        raise ValueError("Source repository set drift")
    for repo, (split, revision) in expected_repos.items():
        config = frozen["repositories"][repo]
        if (config["split"], config["revision"], config["license"]) != (split, revision, "BSD-3-Clause"):
            raise ValueError("Repository split, revision, or license drift")
    if frozen["historical_audit_sha256"] != HISTORICAL_AUDIT_SHA256:
        raise ValueError("Historical audit binding drift")
    if set(expected_repos) & set(frozen["excluded_historical_repositories"]):
        raise ValueError("Historically exposed source repository")
    allowlist = frozen["public_allowlist"]
    if set(allowlist) != {"train.jsonl", "development.jsonl", "rights.json", "manifest.json"}:
        raise ValueError("Unexpected training public allowlist")
    public = data_dir / "public"
    if public.is_symlink() or {p.name for p in public.iterdir()} != set(allowlist):
        raise ValueError("Training public directory has extra or missing files")
    blobs = {}
    for name, expected in allowlist.items():
        path = public / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError("Unsafe training public file")
        value = path.read_bytes()
        if len(value) != expected["bytes"] or sha(value) != expected["sha256"]:
            raise ValueError("Training public hash mismatch")
        blobs[name] = value
    rights = json.loads(blobs["rights.json"])
    if set(rights) != {"pallets/jinja", "pallets/flask"}:
        raise ValueError("Training rights scope changed")
    for repo, right in rights.items():
        if right["spdx"] != "BSD-3-Clause" or not right["training_allowed"] or not right["redistribution_allowed"] or sha(right["notice"]) != right["evidence_sha256"] or right["revision"] != expected_repos[repo][1]:
            raise ValueError("Training license evidence invalid")
    all_rows, splits = [], {}
    for split in ("train", "development"):
        rows = [json.loads(line) for line in blobs[split + ".jsonl"].splitlines()]
        if len(rows) != frozen["function_counts"][split]:
            raise ValueError("Frozen public count mismatch")
        for row in rows:
            config = frozen["repositories"].get(row["repository"])
            if row["split"] != split or not config or config["split"] != split or row["source_commit"] != config["revision"] or row["schema_version"] != VERSION or row["derivation"] != DERIVATION:
                raise ValueError("Unadmitted source row or heldout boundary violation")
            if sha(canonical({k: v for k, v in row.items() if k != "example_id"})) != row["example_id"] or sha(row["query"]) != row["query_sha256"] or sha(row["code"]) != row["code_sha256"]:
                raise ValueError("Source row content hash mismatch")
            if SECRET.search(row["query"] + row["code"]):
                raise ValueError("Private path or credential pattern in model input")
            ast.parse(row["code"])
        all_rows.extend(rows)
        splits[split] = rows
    if len({row["example_id"] for row in all_rows}) != len(all_rows):
        raise ValueError("Duplicate admitted source row")
    if deduplicate(all_rows)[1]["removed"]:
        raise ValueError("Admitted source queries or code contain unresolved near duplicates")
    identity = {"data_kind": frozen["data_kind"], "frozen_sha256": actual_frozen, "historical_audit_sha256": frozen["historical_audit_sha256"], "public_allowlist_sha256": sha(canonical(allowlist)), "source_only_training_data_ready": True, "original013_issue_family_training_data_ready": False, "pseudo_negative_policy": "Other functions in the same admitted split and repository are unjudged contrastive candidates. They may be semantically relevant; no independent negative label is asserted."}
    return splits["train"], splits["development"], identity


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        if not args.audit:
            parser.error("build requires --audit")
        build(args.raw, args.output, args.audit)
    else:
        verify(args.raw, args.output)
