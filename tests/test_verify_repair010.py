"""The optional overlay preserves ancestry and rejects undeclared byte changes."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile

import pytest

from scripts.package_release007 import fingerprint
from scripts.verify_ci009 import PRESERVED as SHOWCASE_PRESERVED
from scripts.verify_repair010 import (CI_MANIFEST, MANIFEST, PARENT_COMMIT, PRESERVED,
                              allowed, verify, verify_source)


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, dict):
        path.write_text(json.dumps(value, indent=2) + "\n")
    else:
        path.write_text(value)
    return path


def read(root, name):
    return json.loads((root / name).read_text())


def archive(root, names, *, extra=False):
    target = root / "evidence/docs008/publication.tar.gz"
    with tarfile.open(target, "w:gz") as stream:
        for name in sorted(names):
            raw = (root / name).read_bytes()
            member = tarfile.TarInfo("kairos/" + name)
            member.size = len(raw)
            stream.addfile(member, io.BytesIO(raw))
        if extra:
            member = tarfile.TarInfo("kairos/unexpected.py")
            member.size = 1
            stream.addfile(member, io.BytesIO(b"x"))


def bind_parent(root):
    publication = {
        "passed": True,
        "archive": fingerprint(root / "evidence/docs008/publication.tar.gz"),
        "manifest": fingerprint(root / "evidence/docs008/manifest.json"),
        "source_receipt": fingerprint(root / "evidence/docs008/receipt.json"),
    }
    write(root, "evidence/docs008/publication-receipt.json", publication)
    correction = read(root, CI_MANIFEST)
    correction["preserved_showcase008"] = {
        name: fingerprint(root / name) for name in SHOWCASE_PRESERVED}
    write(root, CI_MANIFEST, correction)
    overlay = read(root, MANIFEST)
    overlay["preserved_parent"] = {
        name: fingerprint(root / name) for name in PRESERVED}
    write(root, MANIFEST, overlay)


@pytest.fixture
def sealed_chain(tmp_path):
    """Build real tiny archives and the same007 ->008 ->009 ->010 bindings."""
    root = tmp_path
    write(root, "app.py", "original = True\n")
    write(root, "README.md", "Original reviewer guide.\n")
    base = {"files": {"app.py": fingerprint(root / "app.py")}}
    write(root, "evidence/build007/manifest.json", base)
    for name in ("publication.tar.gz", "publication-index.json", "publication-receipt.json"):
        write(root, "evidence/build007/" + name, "preserved original " + name)
    base_names = ["evidence/build007/" + name for name in (
        "manifest.json", "publication.tar.gz", "publication-index.json", "publication-receipt.json")]
    showcase = {
        "files": {"README.md": fingerprint(root / "README.md")},
        "preserved_build007": {
            Path(name).name: fingerprint(root / name) for name in base_names},
    }
    write(root, "evidence/docs008/manifest.json", showcase)
    write(root, "evidence/docs008/receipt.json", {
        "passed": True, "manifest": fingerprint(root / "evidence/docs008/manifest.json")})
    members = {"app.py", "README.md", "evidence/docs008/manifest.json",
               "evidence/docs008/receipt.json", *base_names}
    archive(root, members)
    write(root, "evidence/docs008/publication-checks.json", {"passed": True})
    write(root, "BRAIN.md", "CI009 follow-up.\n")
    write(root, CI_MANIFEST, {
        "version": "ci-portability009-v1",
        "parent_commit": "075975120fa33e47d23635a334e8073356be635c",
        "files": {"BRAIN.md": fingerprint(root / "BRAIN.md")},
    })
    write(root, "scripts/study010.py", "# Optional workflow.\n")
    write(root, MANIFEST, {
        "version": "repair-workflow010-v1", "parent_commit": PARENT_COMMIT,
        "files": {"scripts/study010.py": fingerprint(root / "scripts/study010.py")},
    })
    bind_parent(root)
    return root, members


def test_complete_additive_chain_passes_without_rewriting_parent(sealed_chain):
    root, _ = sealed_chain
    original = {name: (root / name).read_bytes() for name in PRESERVED}
    result = verify(root)
    assert result["passed"] and result["ci009_manifest_unchanged"]
    assert result["declared_workflow_files"] == 1
    assert all((root / name).read_bytes() == raw for name, raw in original.items())


@pytest.mark.parametrize("name", ["scripts/study010.py", "app.py", "BRAIN.md"])
def test_declared_and_inherited_source_checksum_drift_fails(sealed_chain, name):
    root, _ = sealed_chain
    (root / name).write_text("unrecorded change\n")
    with pytest.raises(ValueError, match="source differs"):
        verify(root)


def test_unlisted_new_file_fails(sealed_chain):
    root, _ = sealed_chain
    write(root, "scripts/unlisted.py", "not declared\n")
    with pytest.raises(ValueError, match="source differs"):
        verify(root)


@pytest.mark.parametrize("name", [CI_MANIFEST, "evidence/docs008/receipt.json",
                                      "evidence/build007/publication.tar.gz"])
def test_preserved_parent_bytes_must_not_change(sealed_chain, name):
    root, _ = sealed_chain
    (root / name).write_text("changed historical bytes\n")
    with pytest.raises(ValueError, match="Preserved parent bytes"):
        verify(root)


def test_archive_members_are_verified_beyond_outer_fingerprint(sealed_chain):
    root, members = sealed_chain
    archive(root, members, extra=True)
    # Refresh outer bindings deliberately: an internally undeclared member must
    # still fail the original archive's independent exact-member verification.
    bind_parent(root)
    with pytest.raises(ValueError):
        verify(root)


@pytest.mark.parametrize("field,value", [("version", "unknown"), ("parent_commit", "0" * 40)])
def test_unknown_extension_identity_fails(sealed_chain, field, value):
    root, _ = sealed_chain
    overlay = read(root, MANIFEST)
    overlay[field] = value
    write(root, MANIFEST, overlay)
    with pytest.raises(ValueError, match="Unknown repair workflow"):
        verify(root)


def test_invalid_parent_identity_fails_even_if_outer_binding_is_refreshed(sealed_chain):
    root, _ = sealed_chain
    parent = read(root, CI_MANIFEST)
    parent["version"] = "substituted-parent"
    write(root, CI_MANIFEST, parent)
    overlay = read(root, MANIFEST)
    overlay["preserved_parent"][CI_MANIFEST] = fingerprint(root / CI_MANIFEST)
    write(root, MANIFEST, overlay)
    with pytest.raises(ValueError, match="Unknown preserved CI correction"):
        verify(root)


@pytest.mark.parametrize("name", ["kairos_api/investigations/model.py",
                                      "dashboard/app/workbench/page.tsx", MANIFEST])
def test_active_product_or_self_binding_cannot_be_declared_in_overlay(tmp_path, name):
    path = write(tmp_path, name, "not an optional extension\n")
    with pytest.raises(ValueError, match="Undeclared repair workflow"):
        verify_source(tmp_path, {}, {name: fingerprint(path)})


def test_traversal_is_rejected_before_allowed_prefix_matching(tmp_path):
    with pytest.raises(ValueError, match="publication path"):
        verify_source(tmp_path, {}, {
            "scripts/repair010/../../kairos_api/model.py": {"sha256": "0" * 64, "bytes": 0}})


def test_presentation_scope_accepts_only_declared_pages_and_public_evidence_types():
    assert allowed("dashboard/app/repair-workflow/page.tsx")
    assert allowed("dashboard/lib/repair010-downloads.json")
    assert allowed("dashboard/app/api/repair010/[...path]/route.ts")
    assert allowed("dashboard/e2e/repair-workflow.spec.ts")
    assert not allowed("dashboard/app/workbench/page.tsx")
    assert not allowed("dashboard/public/repair010/credentials.key")
    assert not allowed("dashboard/public/repair010/executable.js")
    assert not allowed("dashboard/public/repair010/reviewed-case/checks.json")
