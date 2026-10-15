"""Bounded, offline, standard-library training-data preparation; never fits a model."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
import zipfile

VERSION = "kairos-training-preparation013-v1"
SEED = "kairos-cloud013-v1\n"
MAX_BYTES, MAX_ROWS = 16 * 1024 * 1024, 1000
FLOORS = {"train": 40, "development": 8, "holdout": 16}
HEX = re.compile(r"[0-9a-f]{64}\Z")
PIN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SECRET = re.compile(r"/Users/|/home/|/private/|[A-Za-z]:\\Users\\|"
                    r"-----BEGIN [^-]*PRIVATE KEY|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
                    r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_-]{20,}|"
                    r"(?i:(?:password|api_key|access_token|secret_key)\s*[:=]\s*['\"]?[^\s'\"]{6,})")
BASE = set("kind instance_id repository upstream_issue_id dataset_id dataset_revision source_commit acquired_at query issue_sha256 path source_text source_file_sha256 start_line end_line code chunk_sha256 rights_refs exposure_refs".split())
RETRIEVAL = set("relevance label_provenance negative_method".split())
REPAIR = set("target_patch target_patch_sha256 baseline_failure_receipt_sha256 verification_pass_receipt_sha256 verifier_revision outcome outcome_provenance target_use".split())
BINDING = "issue_sha256 repository source_commit path start_line end_line source_file_sha256".split()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(obj, expected, label):
    require(type(obj) is dict and set(obj) == set(expected), f"{label}: missing or unknown fields")


def strings(values, label, nonempty=True):
    require(type(values) is list and (bool(values) or not nonempty), f"{label}: expected list")
    require(all(type(v) is str and v.strip() for v in values), f"{label}: expected nonempty strings")
    require(len(values) == len(set(values)), f"{label}: duplicate entries")


def stamp(value):
    require(type(value) is str, "timestamp must be a string")
    try:
        require(datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None, "timestamp needs timezone")
    except (ValueError, TypeError):
        raise ValueError("invalid timezone-aware timestamp") from None


def public(value):
    if isinstance(value, dict):
        for key, item in value.items():
            public(key)
            public(item)
    elif isinstance(value, list):
        for item in value:
            public(item)
    elif isinstance(value, str):
        require(not SECRET.search(value), "secret or private runtime path in export")


def path_ok(value):
    require(type(value) is str and value and "\\" not in value, "invalid POSIX path")
    parts = value.split("/")
    require(not PurePosixPath(value).is_absolute() and all(p and p not in {".", ".."} and not p.startswith(".") for p in parts), "unsafe relative path")
    require(not set(parts) & {"runtime", "private", "secrets", "node_modules"}, "denied source path")


def load(path):
    path = Path(path)
    require(not path.is_symlink() and path.is_file() and path.stat().st_size <= MAX_BYTES, "unsafe or oversized input")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, "non-finite JSON number"))


def identity(row):
    return row["repository"] + "#" + row["upstream_issue_id"]


def assigned(component):
    bucket = int(sha(SEED + component), 16) % 100
    return "train" if bucket < 70 else "development" if bucket < 85 else "holdout"


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text.replace("\r\n", "\n")).split())


def audit_issue_sha(text):
    """Match retrieval011.issue_digest exactly; keep exact issue hashes separately."""
    return sha(" ".join(text.lower().split()))


def grams(text):
    tokens = re.findall(r"\w+", normalize(text).lower())
    return {tuple(tokens[i:i + 5]) for i in range(len(tokens) - 4)}


def validate(data):
    fields(data, "schema_version study_id examples families unresolved_families rights receipts exposures guard export_review".split(), "inventory")
    require(data["schema_version"] == VERSION and type(data["study_id"]) is str and data["study_id"], "invalid inventory version or study")
    require(type(data["examples"]) is list and len(data["examples"]) <= MAX_ROWS, "row bound exceeded")
    require(len({r.get("kind") for r in data["examples"] if type(r) is dict}) <= 1, "freeze retrieval and repair studies separately")
    require(len(canonical(data)) <= MAX_BYTES, "inventory byte bound exceeded")
    fields(data["guard"], "reviewer reviewed_at audit_sha256 identities issue_sha256 reserved_components locked_components".split(), "guard")
    guard = data["guard"]
    require(HEX.fullmatch(guard["audit_sha256"] or ""), "invalid audit hash")
    stamp(guard["reviewed_at"])
    require(type(guard["reviewer"]) is str and guard["reviewer"], "guard reviewer required")
    for key in ("identities", "issue_sha256", "reserved_components", "locked_components"):
        strings(guard[key], "guard." + key, False)
    require(all(HEX.fullmatch(v) for v in guard["issue_sha256"]), "invalid exposure digest")
    fields(data["export_review"], "reviewer reviewed_at approved inventory_content_sha256".split(), "export review")
    stamp(data["export_review"]["reviewed_at"])
    require(type(data["export_review"]["approved"]) is bool, "approval must be Boolean")
    require(type(data["export_review"]["reviewer"]) is str and data["export_review"]["reviewer"], "export reviewer required")
    content = {k: v for k, v in data.items() if k != "export_review"}
    require(data["export_review"]["inventory_content_sha256"] == sha(canonical(content)), "review does not bind inventory")
    require(type(data["families"]) is dict, "families must be an object")
    members = {}
    for key, aliases in data["families"].items():
        strings(aliases, "family aliases")
        require(key == min(aliases) and all(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[0-9]+", a) for a in aliases), "noncanonical family")
        for alias in aliases:
            require(alias not in members, "overlapping families; merge them before freezing")
            members[alias] = key
    strings(data["unresolved_families"], "unresolved families", False)
    require(set(data["unresolved_families"]) <= set(data["families"]), "unknown unresolved family")
    require(type(data["rights"]) is dict and type(data["receipts"]) is dict and type(data["exposures"]) is dict, "metadata maps required")
    for key, right in data["rights"].items():
        fields(right, "component_key kind origin revision license_or_terms evidence_sha256 notices reviewer reviewed_at training_allowed redistribution_allowed".split(), "rights")
        require(all(type(right[k]) is str and right[k] for k in set(right) - {"notices", "training_allowed", "redistribution_allowed"}), "invalid rights strings")
        require(right["kind"] in {"issue", "source", "label", "dataset", "patch"} and right["component_key"] in data["families"], "invalid rights scope")
        require(re.fullmatch(r"https://[A-Za-z0-9.-]+/[^\s?#@]*", right["origin"] or "") and PIN.fullmatch(right["revision"] or ""), "unpinned rights origin")
        require(HEX.fullmatch(right["evidence_sha256"] or "") and right["license_or_terms"] and right["reviewer"], "rights evidence required")
        require(type(right["training_allowed"]) is bool and type(right["redistribution_allowed"]) is bool, "rights decisions must be Boolean")
        strings(right["notices"], "notices", False)
        stamp(right["reviewed_at"])
        public(right)
    for key, receipt in data["receipts"].items():
        require(HEX.fullmatch(key) and sha(canonical(receipt)) == key, "receipt hash mismatch")
        require(type(receipt) is dict and receipt.get("kind") in {"relevance_review", "baseline_failure", "verification_pass"}, "unknown receipt kind")
        fields(receipt, set(BINDING) | set(("kind chunk_sha256 relevance method reviewer reviewed_at" if receipt["kind"] == "relevance_review" else "kind target_patch_sha256 verifier_revision tests_sha256 passed failed total independent outcome_provenance").split()), "receipt")
    for key, event in data["exposures"].items():
        fields(event, "component_key issue_sha256 kind reviewed_at".split(), "exposure")
        require(event["component_key"] in data["families"] and HEX.fullmatch(event["issue_sha256"] or "") and event["kind"] == "acquisition_review", "invalid current exposure")
        stamp(event["reviewed_at"])
    for row in data["examples"]:
        require(type(row) is dict and row.get("kind") in {"retrieval", "repair"}, "invalid example kind")
        fields(row, BASE | (RETRIEVAL if row["kind"] == "retrieval" else REPAIR), "example")
        require(all(type(row[k]) is str and row[k] for k in BASE - {"start_line", "end_line", "rights_refs", "exposure_refs"}), "invalid example strings")
        require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", row["repository"]) and re.fullmatch(r"[0-9]+", row["upstream_issue_id"]), "noncanonical issue")
        require(identity(row) in members, "issue needs explicit family membership")
        component = members[identity(row)]
        require(PIN.fullmatch(row["dataset_revision"]) and PIN.fullmatch(row["source_commit"]), "mutable revision")
        stamp(row["acquired_at"])
        require(len(row["query"]) <= 20000 and len(row["source_text"]) <= 1024 * 1024, "text bound exceeded")
        path_ok(row["path"])
        require(type(row["start_line"]) is int and type(row["end_line"]) is int and 1 <= row["start_line"] <= row["end_line"], "invalid line range")
        lines = row["source_text"].splitlines(keepends=True)
        require(row["end_line"] <= len(lines) and row["code"] == "".join(lines[row["start_line"] - 1:row["end_line"]]), "chunk differs from original source")
        for name, text in (("issue_sha256", row["query"]), ("source_file_sha256", row["source_text"]), ("chunk_sha256", row["code"])):
            require(row[name] == sha(text), "exact original hash mismatch: " + name)
        strings(row["rights_refs"], "rights refs")
        require(set(row["rights_refs"]) <= set(data["rights"]), "unknown rights reference")
        rights = [data["rights"][ref] for ref in row["rights_refs"]]
        require(all(r["component_key"] == component for r in rights), "cross-family rights")
        require({"issue", "source", "label", "dataset"} | ({"patch"} if row["kind"] == "repair" else set()) <= {r["kind"] for r in rights}, "missing rights category")
        strings(row["exposure_refs"], "exposure refs")
        require(all(ref in data["exposures"] and data["exposures"][ref]["component_key"] == component and data["exposures"][ref]["issue_sha256"] == row["issue_sha256"] for ref in row["exposure_refs"]), "exposure binding mismatch")
        if row["kind"] == "retrieval":
            fields(row["label_provenance"], "method reviewer reviewed_at receipt_sha256".split(), "label provenance")
            label = row["label_provenance"]
            require(all(type(v) is str and v for v in label.values()), "invalid label provenance strings")
            require(label["method"] in {"independent_review", "patch_proxy"} and type(row["relevance"]) is int and row["relevance"] in (0, 1), "unreviewed relevance")
            stamp(label["reviewed_at"])
            expected = {"kind": "relevance_review", **{k: row[k] for k in BINDING + ["chunk_sha256", "relevance"]}, **{k: label[k] for k in ("method", "reviewer", "reviewed_at")}}
            require(data["receipts"].get(label["receipt_sha256"]) == expected, "relevance receipt binding mismatch")
            if row["relevance"] == 1:
                require(row["negative_method"] is None, "positive cannot have negative mining metadata")
            else:
                fields(row["negative_method"], "method miner_revision component_key".split(), "negative method")
                require(row["negative_method"]["method"] and PIN.fullmatch(row["negative_method"]["miner_revision"] or "") and row["negative_method"]["component_key"] == component, "negative miner must remain within component/split")
        else:
            require(type(row["target_patch"]) is str and 0 < len(row["target_patch"]) <= 20000 and row["target_patch_sha256"] == sha(row["target_patch"]), "patch hash mismatch")
            require(row["outcome"] == "verified_repair" and row["outcome_provenance"] in {"original", "post_hoc"} and row["target_use"] == "supervised_loss_only", "repair outcome or target use invalid")
            require(PIN.fullmatch(row["verifier_revision"] or ""), "unpinned verifier")
            receipts = []
            for field, kind in (("baseline_failure_receipt_sha256", "baseline_failure"), ("verification_pass_receipt_sha256", "verification_pass")):
                receipt = data["receipts"].get(row[field])
                fields(receipt, set(BINDING) | set("kind target_patch_sha256 verifier_revision tests_sha256 passed failed total independent outcome_provenance".split()), "verification receipt")
                require(receipt["kind"] == kind and receipt["independent"] is True and all(receipt[k] == row[k] for k in BINDING + ["target_patch_sha256", "verifier_revision", "outcome_provenance"]), "verification receipt binding mismatch")
                require(HEX.fullmatch(receipt["tests_sha256"] or "") and all(type(receipt[k]) is int and receipt[k] >= 0 for k in ("passed", "failed", "total")) and receipt["total"] > 0 and receipt["passed"] + receipt["failed"] == receipt["total"], "invalid verifier test counts")
                require(receipt["failed"] > 0 if kind == "baseline_failure" else receipt["failed"] == 0, "baseline must fail and candidate must pass")
                receipts.append(receipt)
            require(receipts[0]["tests_sha256"] == receipts[1]["tests_sha256"] and receipts[0]["total"] == receipts[1]["total"], "verifier suite changed")
        revisions = {"issue": row["issue_sha256"], "source": row["source_commit"], "dataset": row["dataset_revision"], "label": row["label_provenance"]["receipt_sha256"] if row["kind"] == "retrieval" else row["verification_pass_receipt_sha256"], "patch": row.get("target_patch_sha256")}
        require(all(r["revision"] == revisions[r["kind"]] for r in rights), "rights revision does not bind content")
        public({k: v for k, v in row.items() if k != "source_text"})
    return members


def audit_guard(audit_bytes):
    """Preserve raw exposure IDs and map only the documented SWE-bench/-scope aliases."""
    audit = json.loads(audit_bytes)
    identities = set()
    for entry in audit["exposures"]:
        name = entry["instance_id"]
        identities.add(name)
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)__([A-Za-z0-9_.-]+)-([0-9]+)(?:-scope)?", name)
        if match:
            identities.add(f"{match[1]}/{match[2]}#{match[3]}")
    return {"audit_sha256": sha(audit_bytes), "identities": sorted(identities), "issue_sha256": sorted(audit["exposed_issue_digests"])}


def freeze(data, audit_bytes):
    members = validate(data)
    blocked, reasons = set(data["unresolved_families"]), {}
    guard = data["guard"]
    audited = audit_guard(audit_bytes)
    require(guard["audit_sha256"] == audited["audit_sha256"] and set(audited["identities"]) <= set(guard["identities"]) and set(audited["issue_sha256"]) <= set(guard["issue_sha256"]), "audit guard missing exposures or hash drift")
    for row in data["examples"]:
        key = members[identity(row)]
        aliases = set(data["families"][key]) | {row["instance_id"]}
        if aliases & set(guard["identities"]) or {row["issue_sha256"], audit_issue_sha(row["query"])} & set(guard["issue_sha256"]) or aliases & set(guard["reserved_components"] + guard["locked_components"]):
            blocked.add(key)
            reasons.setdefault(key, []).append("locked, reserved, or historically exposed")
        if not all(data["rights"][r]["training_allowed"] and data["rights"][r]["redistribution_allowed"] for r in row["rights_refs"]):
            blocked.add(key)
            reasons.setdefault(key, []).append("rights not approved for training and redistribution")
    unique, duplicates = {}, []
    for row in sorted(data["examples"], key=lambda r: sha(canonical(r))):
        # Exact repeated target/query/chunk rows collapse across dataset packaging copies.
        signature = (members[identity(row)], row["source_commit"], row["source_file_sha256"], row["kind"], row["issue_sha256"], row["chunk_sha256"], row.get("target_patch_sha256"), row.get("relevance"))
        if signature not in unique:
            unique[signature] = row
        else:
            duplicates.append({"kept_sha256": sha(canonical(unique[signature])), "removed_sha256": sha(canonical(row))})
    rows = list(unique.values())
    fingerprints = {(i, field): (normalize(row[field]), grams(row[field])) for i, row in enumerate(rows) for field in ("query", "target_patch") if field in row}
    # Cross-family exact/normalized/near content is unresolved, so quarantine both families.
    for i, a in enumerate(rows):
        for j, b in enumerate(rows[i + 1:], i + 1):
            left, right = members[identity(a)], members[identity(b)]
            if left == right:
                if a["kind"] == "retrieval" and a["issue_sha256"] == b["issue_sha256"] and a["chunk_sha256"] == b["chunk_sha256"] and a["relevance"] != b["relevance"]:
                    blocked.add(left)
                    reasons.setdefault(left, []).append("conflicting relevance labels")
                continue
            for field in ("query", "target_patch"):
                if field not in a or field not in b:
                    continue
                normalized_a, x = fingerprints[i, field]
                normalized_b, y = fingerprints[j, field]
                trigger = normalized_a == normalized_b or not x or not y or len(x & y) / len(x | y) >= .80
                if trigger:
                    blocked.update((left, right))
                    for key in (left, right):
                        reasons.setdefault(key, []).append("unresolved normalized/near/short " + field + " duplicate")
    assignments = {key: assigned(key) for key in sorted(data["families"]) if key not in blocked and any(members[identity(r)] == key for r in rows)}
    counts = {split: dict(sorted(Counter(key.split("#")[0] for key in assignments if assignments[key] == split).items())) for split in FLOORS}
    totals = {split: sum(counts[split].values()) for split in FLOORS}
    positive_keys = {members[identity(r)] for r in rows if r["kind"] == "repair" or r["relevance"] == 1}
    positive_counts = {split: sum(key in positive_keys and assigned_split == split for key, assigned_split in assignments.items()) for split in FLOORS}
    repositories = set().union(*(set(c) for c in counts.values()))
    shortfalls = [f"{split} positive issue families: {positive_counts[split]} < {floor}" for split, floor in FLOORS.items() if positive_counts[split] < floor]
    if len(repositories) < 2:
        shortfalls.append("fewer than two repositories")
    for repo in sorted(repositories):
        for split, minimum in (("development", 4), ("holdout", 8)):
            eligible_positive = sum(key in positive_keys and key.split("#")[0] == repo and assigned_split == split for key, assigned_split in assignments.items())
            if eligible_positive < minimum:
                shortfalls.append(f"{repo} {split} positive issue families: {eligible_positive} < {minimum}")
    return {"schema_version": VERSION, "study_id": data["study_id"], "inventory_sha256": sha(canonical(data)), "implementation_sha256": sha(Path(__file__).read_bytes()),
            "protocol": {"seed": SEED, "floors": FLOORS, "development_per_repository": 4, "holdout_per_repository": 8},
            "metadata_sha256": {k: sha(canonical(data[k])) for k in ("guard", "rights", "receipts", "exposures", "families")},
            "assignments": assignments, "quarantine": {k: sorted(set(reasons.get(k, ["unresolved family"]))) for k in sorted(blocked)},
            "raw_rows": len(data["examples"]), "deduplicated_rows": len(rows), "duplicates": duplicates,
            "normalized_sha256": {sha(canonical(row)): {field: sha(fingerprints[i, field][0]) for field in ("query", "target_patch") if field in row} for i, row in enumerate(rows)},
            "distinct_issue_counts": totals, "positive_issue_counts": positive_counts,
            "repository_counts": counts, "training_data_ready": not shortfalls, "gate_shortfalls": shortfalls}, rows, members


def export(data, frozen, destination, audit_bytes):
    actual, rows, members = freeze(data, audit_bytes)
    require(canonical(actual) == canonical(frozen), "frozen inventory/protocol drift")
    require(data["export_review"]["approved"] is True and data["export_review"]["reviewer"], "manual export review required")
    destination = Path(destination)
    require(not destination.exists(), "output must be a new directory")
    parent = destination.absolute().parent
    require(not any(p.is_symlink() for p in [parent, *parent.parents]), "output parent contains symlink")
    assignments = frozen["assignments"]
    selected = [r for r in rows if assignments.get(members[identity(r)]) in {"train", "development"}]
    weights = Counter(members[identity(r)] for r in selected)
    bundles = {"train": [], "development": []}
    for row in selected:
        component = members[identity(row)]
        split = assignments[component]
        out = {k: v for k, v in row.items() if k != "source_text"}
        out.update(schema_version="kairos-retrieval-training-v1" if row["kind"] == "retrieval" else "kairos-repair-training-v1", split=split, component_key=component, issue_weight=1 / weights[component])
        if row["kind"] == "repair":
            out["original_context"] = {k: out[k] for k in ("path", "start_line", "end_line", "code")}
        out["example_id"] = sha(canonical(out))
        bundles[split].append(out)
    rights_refs = {ref for row in selected for ref in row["rights_refs"]}
    files = {f"{split}.jsonl": b"".join(canonical(r) + b"\n" for r in sorted(values, key=lambda r: r["example_id"])) for split, values in bundles.items()}
    files["rights.json"] = canonical({k: data["rights"][k] for k in sorted(rights_refs)}) + b"\n"
    files["manifest.json"] = canonical({"schema_version": VERSION, "study_id": data["study_id"], "frozen_sha256": sha(canonical(frozen)), "inventory_sha256": frozen["inventory_sha256"], "implementation_sha256": frozen["implementation_sha256"], "metadata_sha256": frozen["metadata_sha256"], "training_data_ready": frozen["training_data_ready"], "gate_shortfalls": frozen["gate_shortfalls"], "distinct_issue_counts": frozen["distinct_issue_counts"], "positive_issue_counts": frozen["positive_issue_counts"], "repository_counts": {s: frozen["repository_counts"][s] for s in ("train", "development")}, "source_exclusions": ["full source snapshots", "private/runtime data", "hidden verifier and receipts", "held-out examples", "unreviewed reference repairs"], "quarantined_components": len(frozen["quarantine"]), "export_review": data["export_review"], "files": {k: {"sha256": sha(v), "bytes": len(v)} for k, v in files.items()}}) + b"\n"
    files["allowlist.json"] = canonical({"schema_version": VERSION, "files": {k: {"sha256": sha(v), "bytes": len(v)} for k, v in files.items()}}) + b"\n"
    require(sum(map(len, files.values())) <= MAX_BYTES, "export bound exceeded")
    for name, value in files.items():
        if name.endswith(".jsonl"):
            for line in value.splitlines():
                public(json.loads(line))
        else:
            public(json.loads(value))
    destination.mkdir()
    public_dir = destination / "public"
    public_dir.mkdir()
    for name, contents in files.items():
        (public_dir / name).write_bytes(contents)
    private_holdout = {"schema_version": VERSION, "frozen_sha256": sha(canonical(frozen)), "components": {k: data["families"][k] for k, split in assignments.items() if split == "holdout"}, "note": "Private identifiers only. Query, target, label and verifier material must remain in a separate sealed evaluator store."}
    (destination / "holdout-manifest.private.json").write_bytes(canonical(private_holdout) + b"\n")
    archive = destination / "training-bundle.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, contents in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, contents)
    with zipfile.ZipFile(archive) as bundle:
        require(set(bundle.namelist()) == set(files) and len(bundle.namelist()) == len(files), "archive allowlist mismatch")
        for info in bundle.infolist():
            path_ok(info.filename)
            require(info.file_size <= MAX_BYTES and (info.external_attr >> 16) & 0o170000 == 0o100000 and bundle.read(info) == files[info.filename], "archive member validation failed")
    receipt = {"archive_sha256": sha(archive.read_bytes()), "archive_bytes": archive.stat().st_size, "files": sorted(files), "training_data_ready": frozen["training_data_ready"]}
    (destination / "export-receipt.private.json").write_bytes(canonical(receipt) + b"\n")
    return receipt


def model_input(row):
    """The only fields to pass to an encoder or repair model as input."""
    require(row.get("split") in {"train", "development"}, "held-out rows cannot enter the training loader")
    require(row.get("example_id") == sha(canonical({k: v for k, v in row.items() if k != "example_id"})), "exported example hash mismatch")
    return {"query": row["query"], "code": row["code"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "export"):
        task = sub.add_parser(command)
        task.add_argument("inventory", type=Path)
        task.add_argument("frozen", type=Path)
        task.add_argument("--audit", type=Path, required=True)
        if command == "export":
            task.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        data = load(args.inventory)
        require(not args.audit.is_symlink() and args.audit.stat().st_size <= MAX_BYTES, "unsafe audit file")
        audit_bytes = args.audit.read_bytes()
        if args.command == "freeze":
            frozen, _, _ = freeze(data, audit_bytes)
            require(not args.frozen.exists() and not args.frozen.is_symlink(), "frozen manifest already exists")
            args.frozen.write_bytes(canonical(frozen) + b"\n")
            print(json.dumps({"training_data_ready": frozen["training_data_ready"], "distinct_issue_counts": frozen["distinct_issue_counts"], "gate_shortfalls": frozen["gate_shortfalls"]}, sort_keys=True))
        else:
            print(json.dumps(export(data, load(args.frozen), args.destination, audit_bytes), sort_keys=True))
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f"Rejected: {error}\n")


if __name__ == "__main__":
    main()
