"""Seal and verify a sanitized build006 source and evidence publication.

The inventory does not depend on Git. Hashes establish byte consistency relative
to these local manifests; they do not establish signed or immutable provenance.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import tempfile
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT
ORIGINAL_ARCHIVE = ORIGINAL / "evidence/build005/publication.tar.gz"
REVIEWER_RUNTIME = ROOT / ".runtime/reviewer005"
OUTPUT_RELATIVE = "evidence/build006"
MAX_MEMBER_BYTES = 100 * 1024**2
CHUNK_BYTES = 1024 * 1024
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
GENERATED = {"manifest.json", "publication.tar.gz", "publication-index.json", "publication-receipt.json"}
PRIVATE_DIRECTORIES = {
    ".git", ".runtime", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".playwright", ".auth", "test-results", "playwright-report", "sessions", "credentials",
    ".aws", ".ssh", ".vercel", ".idea", ".vscode", "htmlcov", "coverage", ".yarn", "bin",
}
PRIVATE_SUFFIXES = {
    ".pyc", ".pyo", ".pyd", ".pem", ".key", ".db", ".sqlite", ".sqlite3", ".gguf",
    ".safetensors", ".pt", ".pth", ".tsbuildinfo", ".swp", ".prof",
}
PRIVATE_NAMES = {".DS_Store", ".coverage", "kairos-ingest", "npm-debug.log", "yarn-debug.log", "yarn-error.log"}


def _fail(message: str) -> None:
    raise ValueError(message)


def safe_name(name: str) -> str:
    """Require one unambiguous relative POSIX path without traversal."""
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        _fail("Invalid publication path")
    parts = name.split("/")
    if name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        _fail("Invalid publication path")
    if PurePosixPath(name).as_posix() != name or ":" in parts[0]:
        _fail("Invalid publication path")
    return name


def excluded(name: str, *, directory: bool = False) -> bool:
    parts = PurePosixPath(name).parts
    if any(part in PRIVATE_DIRECTORIES or part.startswith((".next", ".playwright-results")) for part in parts):
        return True
    if parts and parts[0] in {"dist", "build", "out"}:
        return True
    if name.startswith("dashboard/out/"):
        return True
    leaf = parts[-1]
    if leaf.startswith(".env") and leaf != ".env.example":
        return True
    if leaf in PRIVATE_NAMES or Path(leaf).suffix in PRIVATE_SUFFIXES or leaf.endswith("~"):
        return True
    if name.startswith("evidence/") and leaf.startswith("publication"):
        return True
    if name.startswith(OUTPUT_RELATIVE + "/"):
        if leaf in GENERATED or leaf.startswith(".publication-"):
            return True
        # New nested archives cannot bypass the raw-byte credential scan.
        if leaf.endswith((".tar", ".tar.gz", ".tgz", ".zip")):
            return True
    return False


def _resolved_file(root: Path, name: str) -> Path:
    name = safe_name(name)
    path = root / name
    try:
        relative = path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        _fail("Missing or escaped publication member: " + name)
    if relative.as_posix() != name or path.is_symlink() or not path.is_file():
        _fail("Symlink or non-file publication member: " + name)
    return path


def fingerprint(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        _fail("Fingerprint requires a regular file")
    with path.open("rb") as stream:
        value = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": value, "bytes": path.stat().st_size}


def inventory(root: Path) -> dict[str, dict]:
    """Inventory publishable regular files, refusing included symbolic links."""
    root = root.resolve(strict=True)
    raw_index = root / "evidence/build005/historical-raw-index.json"
    raw_members = read_json(raw_index).get("members", {}) if raw_index.exists() else {}
    entries = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        directory_names = []
        for leaf in sorted(directories):
            path = Path(parent) / leaf
            name = path.relative_to(root).as_posix()
            if excluded(name, directory=True):
                continue
            safe_name(name)
            if path.is_symlink():
                _fail("Symlink publication directory: " + name)
            directory_names.append(leaf)
        directories[:] = directory_names
        for leaf in sorted(files):
            path = Path(parent) / leaf
            name = path.relative_to(root).as_posix()
            if excluded(name):
                continue
            path = _resolved_file(root, name)
            # The original installation keeps raw measurements; clean publication
            # carries their verified lossless archive. Never delete or silently skip
            # a changed raw file when verifying that installation.
            historical_raw = name.startswith("evidence/build004/") and (
                path.suffix == ".jsonl" or path.name in {"capacity-pooled-run.txt", "capacity-run.txt"})
            if historical_raw and name in raw_members:
                if fingerprint(path) != raw_members[name]:
                    _fail("Preserved raw measurement differs from lossless index: " + name)
                continue
            if path.stat().st_size >= MAX_MEMBER_BYTES:
                _fail("Publication member reaches the 100 MiB limit: " + name)
            if not stat.S_ISREG(path.stat().st_mode):
                _fail("Non-regular publication member: " + name)
            if name in entries:
                _fail("Duplicate publication member")
            entries[name] = fingerprint(path)
    return dict(sorted(entries.items()))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("Duplicate JSON object key")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("Unreadable publication metadata: " + path.name)
    if not isinstance(data, dict):
        _fail("Publication metadata must be an object")
    return data


def _valid_fingerprint(value: object) -> bool:
    return isinstance(value, dict) and set(value) == {"sha256", "bytes"} and \
        isinstance(value["sha256"], str) and bool(SHA_PATTERN.fullmatch(value["sha256"])) and \
        type(value["bytes"]) is int and 0 <= value["bytes"] < MAX_MEMBER_BYTES


def validate_entries(entries: object) -> dict[str, dict]:
    if not isinstance(entries, dict) or not entries:
        _fail("Missing publication byte inventory")
    for name, expected in entries.items():
        safe_name(name)
        if not _valid_fingerprint(expected):
            _fail("Missing or invalid publication hash: " + name)
    return entries


def _sensitive_key(key: str) -> bool:
    key = key.upper()
    return any(part in key for part in ("PASSWORD", "SECRET", "TOKEN", "DATABASE_URL", "PRIVATE_KEY"))


def private_values(paths: list[Path]) -> set[bytes]:
    """Read known private state without returning or printing its values."""
    values = set()

    def remember(key, value):
        if not isinstance(value, str) or not _sensitive_key(str(key)):
            return
        value = value.strip().strip("\"'")
        if len(value) >= 8:
            values.add(value.encode())
        if "DATABASE_URL" in str(key).upper():
            if value.startswith(("postgres://", "postgresql://")):
                password = urlsplit(value).password
                if password and len(unquote(password)) >= 8:
                    values.add(unquote(password).encode())
            else:
                match = re.search(r"(?:^|\s)password=(?:'([^']*)'|\"([^\"]*)\"|([^\s]+))", value)
                if match:
                    password = next(part for part in match.groups() if part is not None)
                    if len(password) >= 8:
                        values.add(password.encode())

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                remember(key, child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for path in paths:
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            _fail("Private-value source must be a regular file")
        try:
            if path.suffix == ".json":
                walk(read_json(path))
            else:
                for line in path.read_text().splitlines():
                    if "=" in line and not line.lstrip().startswith("#"):
                        remember(*line.split("=", 1))
        except (OSError, UnicodeError, ValueError):
            _fail("Unable to read a known private-value source")
    return values


def default_private_files(root: Path, extra_runtimes: list[Path]) -> list[Path]:
    paths = [ORIGINAL / ".env.kairos.local", ORIGINAL / ".runtime/identity.env",
             ORIGINAL / ".runtime/identity.local.json", root / ".runtime/study006/environment.json"]
    for runtime in [REVIEWER_RUNTIME, root / ".runtime/reviewer005", *extra_runtimes]:
        paths.extend(runtime / name for name in ("application.env", "postgres.env", "keycloak.env", "identity.local.json"))
    return paths


def scan_private_values(root: Path, entries: dict, sensitive: set[bytes]) -> None:
    """Scan every included raw file, retaining overlap at chunk boundaries."""
    if not sensitive:
        return
    overlap = max(map(len, sensitive)) - 1
    for name in entries:
        tail = b""
        with _resolved_file(root, name).open("rb") as stream:
            while chunk := stream.read(CHUNK_BYTES):
                window = tail + chunk
                if any(value in window for value in sensitive):
                    _fail("Known private value found in publication member: " + name)
                tail = window[-overlap:] if overlap else b""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def acceptance_receipt(root: Path, name: str) -> dict:
    path = _resolved_file(root, name)
    receipt = read_json(path)
    if receipt.get("release") != "build006" or receipt.get("passed") is not True:
        _fail("Build006 final acceptance has not passed")
    checks = receipt.get("checks")
    if not isinstance(checks, dict) or not checks:
        _fail("Final acceptance requires individual check outcomes")
    for check in checks.values():
        if not isinstance(check, dict) or check.get("passed") is not True:
            _fail("Final acceptance contains an incomplete or failed check")
        if "returncode" in check and check["returncode"] != 0:
            _fail("Final acceptance contains a failed command")
    return {"path": name, **fingerprint(path)}


def verify_archive(archive: Path, entries: dict[str, dict]) -> None:
    """Compare an archive without extracting any paths onto the filesystem."""
    validate_entries(entries)
    seen = set()
    try:
        with tarfile.open(archive, "r:gz") as package:
            for member in package:
                name = safe_name(member.name)
                if not name.startswith("kairos/"):
                    _fail("Unexpected archive root")
                relative = safe_name(name.removeprefix("kairos/"))
                if relative in seen:
                    _fail("Duplicate archive member")
                if not member.isfile() or member.issym() or member.islnk():
                    _fail("Archive contains a non-regular member")
                if relative not in entries:
                    _fail("Unexpected archive member: " + relative)
                expected = entries[relative]
                if member.size != expected["bytes"] or member.size >= MAX_MEMBER_BYTES:
                    _fail("Archive member size differs: " + relative)
                stream = package.extractfile(member)
                if stream is None:
                    _fail("Missing archive member body")
                with stream:
                    value = hashlib.file_digest(stream, "sha256").hexdigest()
                if value != expected["sha256"]:
                    _fail("Archive member hash differs: " + relative)
                seen.add(relative)
    except (tarfile.TarError, OSError, EOFError):
        _fail("Unreadable publication archive")
    if seen != set(entries):
        _fail("Publication archive is missing indexed members")


def _write_archive(root: Path, archive: Path, entries: dict[str, dict]) -> None:
    with archive.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as package:
                for name, expected in sorted(entries.items()):
                    path = _resolved_file(root, name)
                    if fingerprint(path) != expected:
                        _fail("Source changed while preparing publication: " + name)
                    member = tarfile.TarInfo("kairos/" + name)
                    member.size = expected["bytes"]
                    member.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                    member.uid = member.gid = member.mtime = 0
                    member.uname = member.gname = ""
                    with path.open("rb") as stream:
                        package.addfile(member, stream)


@contextmanager
def _seal_lock(out: Path):
    lock = out / ".publication-lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _fail("Another publication seal holds the lock")
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


def seal(root: Path, *, acceptance: str = "evidence/build006/final-checks.json",
         original_archive: Path = ORIGINAL_ARCHIVE, private_files: list[Path] | None = None) -> dict:
    root = root.resolve(strict=True)
    out = root / OUTPUT_RELATIVE
    out.mkdir(parents=True, exist_ok=True)
    with _seal_lock(out):
        if any((out / name).exists() or (out / name).is_symlink() for name in GENERATED):
            _fail("Build006 seal already exists; verify it instead of overwriting")
        accepted = acceptance_receipt(root, safe_name(acceptance))
        historical = fingerprint(original_archive)
        entries = inventory(root)
        sensitive = private_values(private_files if private_files is not None else default_private_files(root, []))
        scan_private_values(root, entries, sensitive)
        manifest = {
            "version": "delivery-manifest-v2", "release": "build006",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files": entries, "source_inventory_sha256": hashlib.sha256(canonical(entries)).hexdigest(),
            "acceptance": accepted,
            "historical_build005": {"path": "evidence/build005/publication.tar.gz", **historical,
                                    "included": False},
            "limits": [
                "Hashes establish byte consistency relative to this trusted local manifest, not signed or immutable history.",
                "The original build005 publication archive is fingerprint-bound separately and is not nested in this archive.",
                "Known private values are scanned in included raw bytes; private runtime, sessions, dependencies and model weights are excluded.",
                "Historical compressed evidence is preserved without rewriting its bytes.",
                "Acceptance describes the listed checks and skips; model repair outcomes remain separate.",
                "No external publication or hosting was performed by this packaging command.",
            ],
        }
        created = []
        try:
            manifest_path = out / "manifest.json"
            manifest_path.write_bytes(json_bytes(manifest))
            created.append(manifest_path)
            archive_entries = {**entries, OUTPUT_RELATIVE + "/manifest.json": fingerprint(manifest_path)}
            with tempfile.TemporaryDirectory(prefix="kairos-publication006-") as temporary:
                pending = Path(temporary) / "publication.tar.gz"
                _write_archive(root, pending, archive_entries)
                verify_archive(pending, archive_entries)
                if inventory(root) != entries:
                    _fail("Source changed while sealing publication")
                archive_path = out / "publication.tar.gz"
                pending.replace(archive_path)
                created.append(archive_path)
            index = {
                "version": "publication-index-v2", "release": "build006",
                "files": archive_entries, "archive": fingerprint(archive_path),
                "manifest": fingerprint(manifest_path), "acceptance": accepted,
                "historical_build005": manifest["historical_build005"],
                "source_inventory_sha256": manifest["source_inventory_sha256"],
                "total_source_bytes": sum(item["bytes"] for item in entries.values()),
            }
            index_path = out / "publication-index.json"
            index_path.write_bytes(json_bytes(index))
            created.append(index_path)
            receipt = {
                "version": "publication-receipt-v2", "release": "build006", "passed": True,
                "archive": fingerprint(archive_path), "index": fingerprint(index_path),
                "manifest": fingerprint(manifest_path), "source_files": len(entries),
                "archive_members": len(archive_entries), "source_inventory_sha256": manifest["source_inventory_sha256"],
                "acceptance": accepted, "historical_build005": manifest["historical_build005"],
                "known_private_values_found": False, "private_sources_checked": len(private_files if private_files is not None else default_private_files(root, [])),
                "external_publication_performed": False,
            }
            receipt_path = out / "publication-receipt.json"
            receipt_path.write_bytes(json_bytes(receipt))
            created.append(receipt_path)
            verify(root, original_archive=original_archive, private_files=private_files)
            return receipt
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise


def verify(root: Path, *, original_archive: Path | None = None, source_only: bool = False,
           private_files: list[Path] | None = None) -> dict:
    root = root.resolve(strict=True)
    out = root / OUTPUT_RELATIVE
    manifest_path = _resolved_file(root, OUTPUT_RELATIVE + "/manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("version") != "delivery-manifest-v2" or manifest.get("release") != "build006":
        _fail("Unexpected build006 source manifest")
    entries = validate_entries(manifest.get("files"))
    digest = hashlib.sha256(canonical(entries)).hexdigest()
    if manifest.get("source_inventory_sha256") != digest:
        _fail("Source inventory digest differs")
    if inventory(root) != entries:
        _fail("Current source differs from the sealed inventory")
    accepted = manifest.get("acceptance")
    if not isinstance(accepted, dict) or accepted != acceptance_receipt(root, safe_name(accepted.get("path"))):
        _fail("Acceptance receipt differs from the source manifest")
    historical = manifest.get("historical_build005")
    if not isinstance(historical, dict) or historical.get("included") is not False or \
            historical.get("path") != "evidence/build005/publication.tar.gz" or \
            not _valid_fingerprint({key: historical.get(key) for key in ("sha256", "bytes")}):
        _fail("Missing original build005 archive binding")
    original_checked = False
    if original_archive is not None:
        if fingerprint(original_archive) != {key: historical[key] for key in ("sha256", "bytes")}:
            _fail("Original build005 archive differs")
        original_checked = True
    sensitive = private_values(private_files if private_files is not None else default_private_files(root, []))
    scan_private_values(root, entries, sensitive)
    archive_checked = False
    if not source_only:
        index_path = _resolved_file(root, OUTPUT_RELATIVE + "/publication-index.json")
        receipt_path = _resolved_file(root, OUTPUT_RELATIVE + "/publication-receipt.json")
        archive_path = _resolved_file(root, OUTPUT_RELATIVE + "/publication.tar.gz")
        index, receipt = read_json(index_path), read_json(receipt_path)
        archive_entries = {**entries, OUTPUT_RELATIVE + "/manifest.json": fingerprint(manifest_path)}
        if index.get("version") != "publication-index-v2" or index.get("release") != "build006" or \
                validate_entries(index.get("files")) != archive_entries:
            _fail("Publication index differs from the source manifest")
        if receipt.get("version") != "publication-receipt-v2" or receipt.get("release") != "build006" or receipt.get("passed") is not True:
            _fail("Publication receipt has not passed")
        for key, actual in (("archive", fingerprint(archive_path)), ("manifest", fingerprint(manifest_path))):
            if index.get(key) != actual or receipt.get(key) != actual:
                _fail("Publication " + key + " fingerprint differs")
        if receipt.get("index") != fingerprint(index_path):
            _fail("Publication index fingerprint differs")
        for metadata in (index, receipt):
            if metadata.get("acceptance") != accepted or metadata.get("historical_build005") != historical or \
                    metadata.get("source_inventory_sha256") != digest:
                _fail("Publication receipt bindings differ")
        verify_archive(archive_path, archive_entries)
        archive_checked = True
    return {"passed": True, "source_files": len(entries), "source_inventory_sha256": digest,
            "archive_checked": archive_checked, "original_build005_archive_checked": original_checked,
            "known_private_values_found": False,
            "limits": ([] if original_checked else ["Original build005 archive bytes were unavailable; its trusted manifest binding was validated."]) +
                      (["Source-only verification does not check the downloadable archive or its external index."] if source_only else [])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--seal", action="store_true", help="Seal only after explicit build006 final acceptance passes")
    action.add_argument("--verify", action="store_true", help="Verify existing source, archive and receipt bytes")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--acceptance", default="evidence/build006/final-checks.json")
    parser.add_argument("--original-build005", type=Path, help="Original build005 publication archive; never copied into build006")
    parser.add_argument("--private-runtime", type=Path, action="append", default=[], help="Additional private state to scan without printing values")
    parser.add_argument("--source-only", action="store_true", help="Verify an extracted source package using its embedded manifest")
    args = parser.parse_args()
    if args.seal and args.source_only:
        parser.error("--source-only applies only to --verify")
    private_files = default_private_files(args.root, args.private_runtime)
    try:
        if args.seal:
            result = seal(args.root, acceptance=args.acceptance,
                          original_archive=args.original_build005 or ORIGINAL_ARCHIVE, private_files=private_files)
            result = {key: result[key] for key in ("passed", "source_files", "archive_members", "archive", "manifest")}
        else:
            original = args.original_build005
            if original is None and ORIGINAL_ARCHIVE.exists():
                original = ORIGINAL_ARCHIVE
            result = verify(args.root, original_archive=original, source_only=args.source_only, private_files=private_files)
    except (ValueError, OSError) as error:
        # No environment values or exception traces are emitted.
        parser.exit(1, "Publication verification failed: " + (str(error) if isinstance(error, ValueError) else "filesystem operation failed") + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
