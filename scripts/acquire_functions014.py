"""Acquire only pinned public Python source and exact license evidence; no models run."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

REPOSITORIES = {
    "pallets/jinja": {"revision": "5ef70112a1ff19c05324ff889dd30405b1002044", "split": "train", "prefix": "src/jinja2/", "license_path": "LICENSE.txt", "license": "BSD-3-Clause"},
    "pallets/flask": {"revision": "d086db856be187255b8ec61ef409357393020f32", "split": "development", "prefix": "src/flask/", "license_path": "LICENSE.txt", "license": "BSD-3-Clause"},
    "pallets/click": {"revision": "2247b35ea1c47c727d7a06e51fa280e12a863ff6", "split": "holdout", "prefix": "src/click/", "license_path": "LICENSE.txt", "license": "BSD-3-Clause"},
}
MAX_FILE_BYTES = 1024 * 1024
MAX_ACQUIRED_BYTES = 12 * 1024 * 1024

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()

def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()

def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "kairos-licensed-retrieval014", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Public source exceeded per-file byte bound")
        return data, {k.lower(): v for k, v in response.headers.items() if k.lower() in {"etag", "content-type", "content-length"}}

def acquire(destination):
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Acquisition destination must be empty; preserve existing receipts")
    destination.mkdir(parents=True, exist_ok=True)
    acquired_at = datetime.now(timezone.utc).isoformat()
    objects, trees, jobs = {}, {}, []
    total = 0
    for repo, config in REPOSITORIES.items():
        url = f"https://api.github.com/repos/{repo}/git/trees/{config['revision']}?recursive=1"
        data, headers = get(url)
        tree = json.loads(data)
        if tree.get("truncated") or tree.get("sha") != config["revision"]:
            raise ValueError("Git tree is incomplete or revision drifted")
        trees[repo] = {"url": url, "sha256": sha(data), "bytes": len(data), "tree_sha": tree["sha"]}
        (destination / (repo.replace("/", "__") + ".tree.json")).write_bytes(data)
        total += len(data)
        for entry in tree["tree"]:
            path = entry["path"]
            if entry["type"] == "blob" and (path == config["license_path"] or path.startswith(config["prefix"]) and path.endswith(".py")):
                if entry.get("size", MAX_FILE_BYTES + 1) > MAX_FILE_BYTES:
                    raise ValueError("Source tree advertises oversized source")
                jobs.append((repo, config, path, entry["sha"]))
    def download(job):
        repo, config, path, blob_sha = job
        url = f"https://raw.githubusercontent.com/{repo}/{config['revision']}/{path}"
        data, headers = get(url)
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual_blob != blob_sha:
            raise ValueError("Downloaded source differs from pinned Git blob")
        return repo, path, data, {"repository": repo, "revision": config["revision"], "path": path, "origin": url, "git_blob_sha1": blob_sha, "sha256": sha(data), "bytes": len(data), "headers": headers}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for repo, path, data, receipt in executor.map(download, jobs):
            total += len(data)
            if total > MAX_ACQUIRED_BYTES:
                raise ValueError("Acquisition exceeded total byte bound")
            local = "blobs/" + receipt["sha256"]
            target = destination / local
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                target.write_bytes(data)
            receipt["local_path"] = local
            objects[repo + ":" + path] = receipt
    manifest = {"schema_version": "kairos-function-acquisition014-v1", "acquired_at": acquired_at, "repositories": REPOSITORIES, "trees": trees, "objects": objects, "acquired_bytes": total, "max_acquired_bytes": MAX_ACQUIRED_BYTES, "notes": "Only pinned source modules, repository licenses, and Git tree metadata were acquired. No tests or source were executed. No model or account action occurred."}
    (destination / "acquisition.json").write_bytes(canonical(manifest) + b"\n")
    print(json.dumps({"objects": len(objects), "acquired_bytes": total}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    acquire(args.destination)
