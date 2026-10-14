"""An additive CI correction must still reject unrecorded source changes."""
import pytest

from scripts.package_release007 import fingerprint
from scripts.verify_ci009 import verify_source


def test_declared_correction_accepts_exact_bytes(tmp_path):
    (tmp_path / "app.py").write_text("original\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    path = tests / "test_ingest_contracts.py"
    path.write_text("portable test\n")
    original = {"app.py": fingerprint(tmp_path / "app.py")}
    changes = {"tests/test_ingest_contracts.py": fingerprint(path)}
    verify_source(tmp_path, original, changes)
    path.write_text("changed test\n")
    with pytest.raises(ValueError, match="differs"):
        verify_source(tmp_path, original, changes)


def test_unexpected_files_and_changes_outside_ci_scope_are_rejected(tmp_path):
    (tmp_path / "app.py").write_text("original\n")
    changes = {"README.md": {"sha256": "0" * 64, "bytes": 0}}
    inherited = {"app.py": fingerprint(tmp_path / "app.py")}
    (tmp_path / "README.md").write_text("")
    changes["README.md"] = fingerprint(tmp_path / "README.md")
    verify_source(tmp_path, inherited, changes)
    (tmp_path / "unexpected.py").write_text("not declared\n")
    with pytest.raises(ValueError, match="differs"):
        verify_source(tmp_path, inherited, changes)
    with pytest.raises(ValueError, match="Undeclared"):
        verify_source(tmp_path, inherited, {"app.py": inherited["app.py"]})
