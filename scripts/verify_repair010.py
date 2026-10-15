"""Verify the optional repair workflow without rewriting sealed release evidence.

These locally stored hashes establish byte consistency relative to the recorded
parent. They do not establish a signature, immutable history or repair quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.package_release007 import (fingerprint, inventory, read_json,
                                       validate_entries, verify_archive)
from scripts.verify_ci009 import PRESERVED as SHOWCASE_PRESERVED
from scripts.verify_showcase008 import METADATA as SHOWCASE_METADATA

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "evidence/repair010/manifest.json"
PARENT_COMMIT = "1c5153630804e2e057e91fc8e738824970f7a330"
CI_MANIFEST = "evidence/ci009/manifest.json"
PRESERVED = (CI_MANIFEST, *SHOWCASE_PRESERVED, *(
    "evidence/build007/" + name for name in (
        "manifest.json", "publication.tar.gz", "publication-index.json",
        "publication-receipt.json")))
ALLOWED = frozenset({
    ".github/workflows/regression-gate.yml", "BRAIN.md", "DECISIONS.md", "README.md",
    "docs/showcase/PROVENANCE.md", "docs/showcase/REPAIR_010.md",
    "docs/showcase/assets/repair010-desktop.png", "docs/showcase/assets/repair010-mobile.png",
    "scripts/acceptance007.py", "scripts/study010.py", "scripts/verify_repair010.py",
    "tests/test_feedback010.py", "tests/test_codex_context010.py",
    "tests/test_codex_transport010.py", "tests/test_unresolved_registry010.py",
    "tests/test_study010.py", "tests/test_verify_repair010.py",
    "tests/test_check_captured010.py",
    "tests/test_unresolved_integration010.py",
    "dashboard/app/page.tsx", "dashboard/app/advancement/page.tsx",
    "dashboard/app/how-it-works/page.tsx", "dashboard/app/docs/page.tsx",
    "dashboard/app/engineering/page.tsx", "dashboard/app/repair-workflow/page.tsx",
    "dashboard/lib/repair010-results.json", "dashboard/e2e/repair-workflow.spec.ts",
    "dashboard/playwright.recorded.config.ts",
    "dashboard/lib/repair010-downloads.ts", "dashboard/lib/repair010-downloads.test.mjs",
    "dashboard/lib/repair010-downloads.json", "dashboard/package.json",
    "dashboard/app/api/repair010/[...path]/route.ts",
})


def allowed(name: str) -> bool:
    """Limit the overlay to an optional CLI extension, its tests and evidence."""
    return (name in ALLOWED or
            (name.startswith("scripts/repair010/") and name.endswith(".py")) or
            (name.startswith("evidence/repair010/") and
             Path(name).suffix in {".json", ".md", ".patch"}))


def verify_source(root: Path, inherited: dict, changes: dict) -> None:
    changes = validate_entries(changes)
    if MANIFEST in changes or not all(allowed(name) for name in changes):
        raise ValueError("Undeclared repair workflow path")
    expected = {**inherited, **changes}
    excluded = {*SHOWCASE_METADATA, CI_MANIFEST, MANIFEST}
    actual = {name: value for name, value in inventory(root).items()
              if name not in excluded}
    if actual != expected:
        raise ValueError("Active source differs from the declared repair workflow")


def verify_parent(root: Path) -> dict:
    """Verify the unchanged CI009 ancestry and the original008 archive.

    CI009's source check intentionally applies to its own snapshot. Its exact
    source inventory is merged with this new overlay rather than weakening or
    rewriting that older verifier or manifest.
    """
    correction = read_json(root / CI_MANIFEST)
    if (correction.get("version") != "ci-portability009-v1" or
            correction.get("parent_commit") != "075975120fa33e47d23635a334e8073356be635c"):
        raise ValueError("Unknown preserved CI correction identity")
    if correction.get("preserved_showcase008") != {
            name: fingerprint(root / name) for name in SHOWCASE_PRESERVED}:
        raise ValueError("Preserved delivery008 bytes differ")
    showcase = read_json(root / "evidence/docs008/manifest.json")
    receipt = read_json(root / "evidence/docs008/receipt.json")
    publication = read_json(root / "evidence/docs008/publication-receipt.json")
    base = read_json(root / "evidence/build007/manifest.json")
    if (receipt.get("passed") is not True or publication.get("passed") is not True or
            receipt.get("manifest") != fingerprint(root / "evidence/docs008/manifest.json") or
            publication.get("archive") != fingerprint(root / "evidence/docs008/publication.tar.gz") or
            publication.get("manifest") != receipt["manifest"] or
            publication.get("source_receipt") != fingerprint(root / "evidence/docs008/receipt.json")):
        raise ValueError("Historical delivery bindings differ")
    for name, value in showcase["preserved_build007"].items():
        if fingerprint(root / ("evidence/build007/" + name)) != value:
            raise ValueError("Historical build007 bytes differ")
    inherited = {**validate_entries(base["files"]),
                 **validate_entries(showcase["files"])}
    archive_members = {**inherited, **{
        name: fingerprint(root / name) for name in SHOWCASE_METADATA}}
    archive_members.update({"evidence/build007/" + name: value
                           for name, value in showcase["preserved_build007"].items()})
    verify_archive(root / "evidence/docs008/publication.tar.gz", archive_members)
    return {**inherited, **validate_entries(correction["files"])}


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    overlay = read_json(root / MANIFEST)
    if (overlay.get("version") != "repair-workflow010-v1" or
            overlay.get("parent_commit") != PARENT_COMMIT):
        raise ValueError("Unknown repair workflow identity")
    if overlay.get("preserved_parent") != {
            name: fingerprint(root / name) for name in PRESERVED}:
        raise ValueError("Preserved parent bytes differ")
    inherited = verify_parent(root)
    verify_source(root, inherited, overlay["files"])
    return {
        "passed": True,
        "declared_workflow_files": len(overlay["files"]),
        "ci009_manifest_unchanged": True,
        "delivery008_archive_verified": True,
        "historical_receipts_unchanged": True,
        "scope": ("Optional repair workflow byte consistency; software acceptance, "
                  "development checks and fresh repair effectiveness have separate receipts"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(1, "Repair workflow verification failed: " + message + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
