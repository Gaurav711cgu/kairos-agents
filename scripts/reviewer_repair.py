"""Prepare the one earned historical repair in a separate reviewer workspace."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

from kairos_api.investigations.registry import tree_hash
from scripts.reviewer_evidence import validate_package
from scripts.reviewer_runtime import private_json

ROOT = Path(__file__).resolve().parents[1]
TASK = "django__django-10914"
IMAGE = "kairos-investigation-django:build007-reviewer"


def extract_source(archive, destination):
    """Only one archive root and data-safe member paths are allowed."""
    with tarfile.open(archive) as source:
        members = source.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members if member.name}
        if len(roots) != 1: raise ValueError("Pinned source archive must contain one root")
        prefix = next(iter(roots))
        if sum(member.size for member in members) > 250 * 1024**2:
            raise ValueError("Source archive exceeds extraction budget")
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != prefix:
                raise ValueError("Unsafe source archive path")
            member.name = str(PurePosixPath(*path.parts[1:])) if len(path.parts) > 1 else ""
            if member.name: source.extract(member, destination, filter="data")


def prepare(runtime, evidence):
    records, _ = validate_package(evidence)
    candidates = [record for record in records.values() if record["task_id"] == TASK
                  and record["configuration"] == "baseline-v3" and record["outcome"] == "verified_repair"]
    if len(candidates) != 1: raise ValueError("Recorded original single-call repair unavailable or ambiguous")
    record = candidates[0]; case = record["task_snapshot"]
    provenance = json.loads((ROOT / "cases/provenance.json").read_text())
    rows = [row for row in provenance["records"] if row["instance_id"] == TASK]
    if len(rows) != 1 or rows[0]["base_commit"] != case["revision"]:
        raise ValueError("Frozen source provenance mismatch")
    row = rows[0]; investigation_root = runtime / "investigations"
    directory = investigation_root / "cases" / TASK; directory.mkdir(parents=True, exist_ok=True)
    for filename, key, expected in (("reference.patch", "patch", case["reference_digest"]),
                                    ("test.patch", "test_patch", case["verification_digest"])):
        raw = row[key].encode()
        if hashlib.sha256(raw).hexdigest() != expected: raise ValueError("Frozen verification material mismatch")
        path = directory / filename
        if path.exists() and path.read_bytes() != raw: raise ValueError("Reviewer verification material was changed")
        path.write_bytes(raw)
    source = directory / "source"; archive = directory / "source.tar.gz"
    if not source.exists():
        temporary = archive.with_suffix(".pending")
        url = "https://codeload.github.com/django/django/tar.gz/" + case["revision"]
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            total = 0
            while chunk := response.read(1024**2):
                total += len(chunk)
                if total > 60 * 1024**2: raise ValueError("Pinned source archive exceeds download budget")
                if shutil.disk_usage(runtime).free < 4 * 1024**3: raise ValueError("Free storage below 4GiB reserve")
                output.write(chunk)
        os.replace(temporary, archive)
        with tempfile.TemporaryDirectory(prefix="reviewer-source-", dir=directory) as temporary:
            extracted = Path(temporary) / "source"; extracted.mkdir(); extract_source(archive, extracted)
            if tree_hash(extracted) != case["source_digest"]: raise ValueError("Pinned source tree digest mismatch")
            os.replace(extracted, source)
    if tree_hash(source) != case["source_digest"]: raise ValueError("Existing reviewer source tree digest mismatch")
    log = runtime / "repair-build.log"
    with log.open("w") as output:
        log.chmod(0o600)
        subprocess.run(["docker", "build", "-f", "Dockerfile.investigation-django", "-t", IMAGE, "."], cwd=ROOT,
                       stdout=output, stderr=subprocess.STDOUT, check=True, timeout=600)
    record_path = directory / "record.json"; private_json(record_path, record)
    output = runtime / "repair-reproduction.json"
    env = os.environ.copy(); env.update(KAIROS_INVESTIGATION_ROOT=str(investigation_root), PYTHONPATH=str(ROOT))
    with (runtime / "repair-checks.log").open("w") as log:
        (runtime / "repair-checks.log").chmod(0o600)
        result = subprocess.run([os.sys.executable, "-m", "scripts.reproduce_investigation", "--record", str(record_path),
            "--image", IMAGE, "--output", str(output)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    if not output.exists(): raise RuntimeError("Repair reproduction produced no receipt; inspect private repair log")
    receipt = json.loads(output.read_text())
    receipt.update(source_revision=case["revision"], archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else None,
        environment_policy="Reviewed recipe rebuilt under a new build007 tag; immutable image difference is reported explicitly.")
    private_json(output, receipt)
    if result.returncode or not receipt["outcome_reproduced"]: raise RuntimeError("Recorded repair did not reproduce; inspect actual receipt")
    print("Recorded repair reproduced. Source, patch and rebuilt image provenance saved in reviewer runtime.", flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--runtime", required=True); parser.add_argument("--evidence", required=True)
    args = parser.parse_args(); prepare(Path(args.runtime).resolve(), Path(args.evidence).resolve())


if __name__ == "__main__": main()
