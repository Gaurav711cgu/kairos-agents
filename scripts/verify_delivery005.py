"""Check the delivery inventory and lossless archives without executing services."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/build005"


def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def check_files(root, entries):
    for name, expected in entries.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Missing or unsafe delivery file: " + name)
        with path.open("rb") as stream:
            actual = digest(stream)
        if actual != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise ValueError("Delivery bytes differ: " + name)


def check_archive(path, entries, prefix=""):
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        expected_names = {prefix + name for name in entries}
        if len(members) != len(expected_names) or {m.name for m in members} != expected_names:
            raise ValueError("Archive membership differs: " + path.name)
        for member in members:
            if not member.isfile():
                raise ValueError("Archive contains a non-file member: " + member.name)
            expected = entries[member.name[len(prefix):]]
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("Archive member unavailable: " + member.name)
            with stream:
                actual = digest(stream)
            if member.size != expected["bytes"] or actual != expected["sha256"]:
                raise ValueError("Archive bytes differ: " + member.name)


def verify(bundle=False):
    manifest = json.loads((OUT / "manifest.json").read_text())
    check_files(ROOT, manifest["files"])
    historical = json.loads((ROOT / "evidence/build004/manifest.json").read_text())
    check_archive(OUT / "build004-source.tar.gz", historical["sources"])
    raw = json.loads((OUT / "historical-raw-index.json").read_text())
    check_archive(OUT / "historical-raw.tar.gz", raw["members"])
    if bundle:
        receipt = json.loads((OUT / "publication-receipt.json").read_text())
        check_files(ROOT, {"evidence/build005/publication.tar.gz": receipt["archive"],
                           "evidence/build005/publication-index.json": receipt["index"],
                           "evidence/build005/manifest.json": receipt["manifest"]})
        index = json.loads((OUT / "publication-index.json").read_text())
        check_archive(OUT / "publication.tar.gz", index["files"], "kairos/")
    return {"passed": True, "delivery_files": len(manifest["files"]),
            "historical_source_files": len(historical["sources"]),
            "raw_measurement_files": len(raw["members"]), "publication_bundle_checked": bundle,
            "scope": "Byte integrity and inventory checks; hashes do not prove immutable or independently signed history."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", action="store_true", help="Also verify the separately sealed publication archive")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.bundle)))
    except (OSError, KeyError, ValueError, tarfile.TarError) as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
