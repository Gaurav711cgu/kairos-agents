"""Verify the CI portability correction without rewriting the sealed delivery008."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.package_release007 import fingerprint, inventory, read_json, validate_entries, verify_archive
from scripts.verify_showcase008 import METADATA as SHOWCASE_METADATA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "evidence/ci009/manifest.json"
PARENT_COMMIT = "075975120fa33e47d23635a334e8073356be635c"
PRESERVED = (
    "evidence/docs008/manifest.json", "evidence/docs008/receipt.json",
    "evidence/docs008/publication.tar.gz", "evidence/docs008/publication-receipt.json",
    "evidence/docs008/publication-checks.json",
)
ALLOWED = {
    ".github/workflows/regression-gate.yml", "BRAIN.md", "DECISIONS.md", "README.md",
    "docs/showcase/PROVENANCE.md", "docs/showcase/CI_009.md",
    "scripts/ci_diagnostics009.py", "scripts/verify_ci009.py",
    "tests/test_ci_diagnostics009.py", "tests/test_ci_release009.py",
    "tests/test_ingest_contracts.py", "tests/test_investigations_advancement.py",
    "evidence/ci009/local-checks.json",
}


def verify_source(root: Path, inherited: dict, changes: dict) -> None:
    changes = validate_entries(changes)
    if not set(changes).issubset(ALLOWED):
        raise ValueError("Undeclared CI correction path")
    expected = {**inherited, **changes}
    actual = {name: value for name, value in inventory(root).items()
              if name not in SHOWCASE_METADATA and name != MANIFEST}
    if actual != expected:
        raise ValueError("Active source differs from the declared CI correction")


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    correction = read_json(root / MANIFEST)
    if correction.get("version") != "ci-portability009-v1" or correction.get("parent_commit") != PARENT_COMMIT:
        raise ValueError("Unknown CI correction identity")
    if correction.get("preserved_showcase008") != {name: fingerprint(root / name) for name in PRESERVED}:
        raise ValueError("Preserved delivery008 bytes differ")
    showcase = read_json(root / "evidence/docs008/manifest.json")
    receipt = read_json(root / "evidence/docs008/receipt.json")
    publication = read_json(root / "evidence/docs008/publication-receipt.json")
    base = read_json(root / "evidence/build007/manifest.json")
    if (receipt.get("passed") is not True or publication.get("passed") is not True
            or receipt.get("manifest") != fingerprint(root / "evidence/docs008/manifest.json")
            or publication.get("archive") != fingerprint(root / "evidence/docs008/publication.tar.gz")
            or publication.get("manifest") != receipt["manifest"]
            or publication.get("source_receipt") != fingerprint(root / "evidence/docs008/receipt.json")):
        raise ValueError("Historical delivery bindings differ")
    for name, value in showcase["preserved_build007"].items():
        if fingerprint(root / ("evidence/build007/" + name)) != value:
            raise ValueError("Historical build007 bytes differ")
    inherited = {**base["files"], **showcase["files"]}
    archive_members = {**inherited, **{name: fingerprint(root / name) for name in SHOWCASE_METADATA}}
    archive_members.update({"evidence/build007/" + name: value
                           for name, value in showcase["preserved_build007"].items()})
    verify_archive(root / "evidence/docs008/publication.tar.gz", archive_members)
    verify_source(root, inherited, correction["files"])
    return {"passed": True, "declared_correction_files": len(correction["files"]),
            "delivery008_archive_verified": True, "historical_receipts_unchanged": True,
            "scope": "Declared CI portability changes and byte consistency; hosted checks have separate GitHub run records"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "CI correction verification failed: " + (str(error) if isinstance(error, ValueError) else type(error).__name__) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
