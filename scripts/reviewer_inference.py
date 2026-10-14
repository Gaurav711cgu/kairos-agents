"""Explicit, pinned local inference for an owned reviewer full-stack session.

Preflight performs reads only. It neither downloads weights nor starts Docker.
The prepared case is an exposed development case, outside the locked study.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess

from scripts import study007_runtime
from scripts.reviewer_runtime import require_ports

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_CASE = "django__django-11066"


def storage_guard(runtime, cache, case_root):
    """Count the whole selected runtime and disjoint caches exactly once."""
    roots = sorted({Path(path).resolve() for path in (runtime, cache, case_root)},
                   key=lambda path: len(path.parts))
    unique = [path for index, path in enumerate(roots)
              if not any(path.is_relative_to(parent) for parent in roots[:index])]
    size = sum(path.stat().st_size for root in unique for path in root.rglob("*")
               if path.is_file() and not path.is_symlink())
    anchors = [root if root.exists() else root.parent for root in unique]
    free = min(shutil.disk_usage(root).free for root in anchors)
    if size > study007_runtime.CAPACITY or free < study007_runtime.RESERVE:
        raise ValueError("Reviewer execution exceeds 6GiB persistent budget or 4GiB free reserve")
    return {"owned_bytes": size, "free_bytes": free,
            "budget_bytes": study007_runtime.CAPACITY,
            "reserve_bytes": study007_runtime.RESERVE}


@dataclass(frozen=True)
class LiveInference:
    cache: Path
    case_root: Path
    state: Path
    profile: str
    manifest: Path
    case: dict
    session_seconds: int
    model_sha256: str
    manifest_sha256: str

    def paths(self):
        return {"cache": self.cache, "state": self.state}

    def environment(self):
        return {
            "KAIROS_INVESTIGATION_ROOT": str(self.case_root),
            "KAIROS_INVESTIGATION_MODEL_MANIFEST": str(self.manifest),
            "KAIROS_INVESTIGATION_MODEL_URL": "http://127.0.0.1:8130",
        }

    def receipt(self):
        # These resolved machine paths remain inside the private reviewer runtime.
        return {
            "version": "reviewer-local-inference-v1",
            "profile": self.profile,
            "model_sha256": self.model_sha256,
            "manifest_sha256": self.manifest_sha256,
            "model_cache": str(self.cache),
            "case_root": str(self.case_root),
            "prepared_development_case": self.case["id"],
            "session_seconds": self.session_seconds,
            "scope": "Interactive local execution; not a rerun of locked evaluation",
        }


def preflight(runtime, model_cache=None, case_root=None, profile="coder", session_seconds=900):
    """Reject missing, modified or incompatible resources before heavy services start."""
    from kairos_api.investigations.registry import CaseRegistry

    if not 60 <= session_seconds <= 3600:
        raise ValueError("Live session duration must be between 60 and 3600 seconds")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Pinned local inference requires macOS ARM64; no provider substitution")
    cache = Path(model_cache or ROOT / ".runtime/investigations").expanduser().resolve()
    cases = Path(case_root or cache).expanduser().resolve()
    if not cache.is_dir() or not cases.is_dir():
        raise ValueError("Prepared model cache and case root must exist; no automatic download")
    state = Path(runtime) / "inference"
    paths = {"cache": cache, "state": state}
    require_ports([8130])
    model = study007_runtime.verify_model(paths, profile)
    storage_guard(runtime, cache, cases)
    manifest = ROOT / f"evidence/build004/inference-{profile}-mac.json"
    # The adapter pins the same bytes as the API enqueue receipt and worker.
    if json.loads(manifest.read_text()) != model:
        raise ValueError("Model preflight and investigation manifest differ")
    registry = CaseRegistry(manifest=ROOT / "cases/investigations.json", runtime=cases)
    case = registry.get(DEVELOPMENT_CASE)
    if case.get("split") != "development":
        raise ValueError("The interactive preflight case must remain a development case")
    registry.verify(case)
    weight = next(item for item in model["files"] if item["path"].endswith(".gguf"))
    return LiveInference(cache, cases, state, profile, manifest, case, session_seconds,
                         weight["sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())


def verify_image(settings):
    """A live session uses an already prepared image, never an unreviewed pull."""
    image = settings.case["image"]
    result = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                            capture_output=True, text=True, timeout=15)
    if result.returncode or result.stdout.strip() != image:
        raise RuntimeError("Prepared verification image is missing; use the reviewed case recipe first")


def start(settings):
    # Provisioning and locked dependency installation can add files after the
    # first preflight. Recheck the complete selected runtime before inference.
    storage_guard(settings.state.parent, settings.cache, settings.case_root)
    return study007_runtime.start_model(settings.paths(), settings.profile)


def finish(process, log):
    study007_runtime.finish_model(process, log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["attest"])
    parser.parse_args()
    from kairos_api.investigations.model import LocalInvestigator
    # A child reads the explicitly supplied environment; shell credentials are
    # never inherited by the reviewer environment builder.
    value = LocalInvestigator().verify_profile("loop-v7")
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
