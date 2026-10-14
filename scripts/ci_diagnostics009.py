"""Print bounded, redacted reviewer failures instead of hiding their private logs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.package_release007 import default_private_files, private_values

ROOT = Path(__file__).resolve().parents[1]


def redact(text: str, sensitive: set[bytes]) -> str:
    for value in sorted(sensitive, key=len, reverse=True):
        text = text.replace(value.decode("utf-8", errors="replace"), "[redacted]")
    text = re.sub(r"(postgres(?:ql)?://)[^\s'\"]+", r"\1[redacted]", text)
    text = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted token]", text)
    text = re.sub(r"(?i)([?&](?:code|access_token|refresh_token)=)[^&\s'\"]+", r"\1[redacted]", text)
    text = re.sub(r"(?i)(authorization:\s*(?:bearer|basic)\s+)[^\s'\"]+", r"\1[redacted]", text)
    return text


def summarize(runtime: Path, root: Path = ROOT) -> dict:
    root = root.resolve(strict=True)
    runtime = runtime.resolve()
    if not runtime.is_relative_to(root / ".runtime"):
        raise ValueError("Diagnostics require an isolated checkout runtime")
    sensitive = private_values(default_private_files(root, [runtime]))
    result = {"runtime": runtime.relative_to(root).as_posix(), "failed_checks": [], "logs": []}
    logs = []
    for receipt in sorted((runtime / "checks").glob("*.receipt.json")):
        if receipt.is_symlink() or not receipt.resolve().is_relative_to(runtime):
            continue
        value = json.loads(receipt.read_text())
        if value.get("returncode"):
            result["failed_checks"].append({key: value.get(key) for key in ("name", "returncode", "timed_out", "elapsed_seconds")})
            logs.append(receipt.with_name(receipt.name.replace(".receipt.json", ".log")))
    logs.extend([runtime / "error.log", runtime / "demo-supervisor.log", runtime / "fullstack-supervisor.log"])
    for path in logs[:20]:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(runtime):
            continue
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 1024 * 1024))
            text = stream.read().decode("utf-8", errors="replace")
        tail = "\n".join(text.splitlines()[-120:])
        result["logs"].append({"name": path.relative_to(runtime).as_posix(), "tail": redact(tail, sensitive)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.runtime), indent=2))


if __name__ == "__main__":
    main()
