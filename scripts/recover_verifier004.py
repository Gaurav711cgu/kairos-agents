"""Recover the exact historical pytest OCI image from retained local BuildKit blobs.
No rebuild, registry download, model call or evaluation-record change is allowed.
The index and every executable linux/arm64 blob must match their recorded SHA-256 digest.
A missing optional provenance layer is disclosed; no signed provenance is claimed.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DIGEST = 'sha256:5db01d3fa0f7880ccc2a69ee40b15e7635c6aa72bc2bfa2fda967efd18fd3c96'
BUILD_REF = 'pjmfdczmy4ls3gn7acqc12u73'
TAG = 'docker.io/library/kairos-investigation-study:build004-pytest'


def main():
    out = ROOT / 'evidence/build004'
    destination = ROOT / '.runtime/investigations/images/pytest004'
    destination.mkdir(parents=True, exist_ok=True)
    inspected = subprocess.run(['docker', 'image', 'inspect', DIGEST, '--format', '{{.Id}}'], capture_output=True, text=True)
    recovered = inspected.returncode == 0
    blobs = {}
    if not recovered:
        assert shutil.disk_usage(ROOT).free > 4 * 1024**3 + 512 * 1024**2, 'Free-space reserve'
        layout = destination / 'oci'
        (layout / 'blobs/sha256').mkdir(parents=True, exist_ok=True)
        pending = [{'digest': DIGEST}]
        total = 0
        while pending:
            descriptor = pending.pop()
            digest = descriptor['digest']
            assert digest.startswith('sha256:') and len(digest) == 71
            hexadecimal = digest.split(':')[1]
            assert all(char in '0123456789abcdef' for char in hexadecimal)
            if digest in blobs:
                continue
            assert len(blobs) < 32, 'Unexpected OCI graph size'
            path = layout / 'blobs/sha256' / hexadecimal
            with path.open('wb') as stream:
                subprocess.run(['docker', 'buildx', 'history', 'inspect', 'attachment', BUILD_REF, digest], stdout=stream, check=True, timeout=90)
            size = path.stat().st_size
            total += size
            assert total < 512 * 1024**2, 'Unexpected image recovery size'
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert actual == hexadecimal, 'BuildKit blob digest mismatch'
            if 'size' in descriptor:
                assert size == descriptor['size'], 'OCI descriptor size mismatch'
            blobs[digest] = size
            if digest == DIGEST or 'manifest' in descriptor.get('mediaType', '') or 'index' in descriptor.get('mediaType', ''):
                document = json.loads(path.read_bytes())
                pending.extend(item for item in document.get('manifests', []) if item.get('platform', {}).get('os') == 'linux' and item.get('platform', {}).get('architecture') == 'arm64')
                pending.extend(document.get('layers', []))
                if document.get('config'):
                    pending.append(document['config'])
        (layout / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
        (layout / 'index.json').write_text(json.dumps({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json', 'manifests': [{'mediaType': 'application/vnd.oci.image.index.v1+json', 'digest': DIGEST, 'size': blobs[DIGEST], 'annotations': {'org.opencontainers.image.ref.name': TAG}}]}))
        archive = destination / 'exact-image.oci.tar'
        with tarfile.open(archive, 'w') as package:
            for path in sorted(layout.rglob('*')):
                if path.is_file():
                    package.add(path, arcname=str(path.relative_to(layout)), recursive=False)
        subprocess.run(['docker', 'load', '--platform', 'linux/arm64', '--input', str(archive)], check=True, timeout=120)
        subprocess.run(['docker', 'image', 'inspect', DIGEST], check=True, stdout=subprocess.DEVNULL)
        shutil.rmtree(layout)
    subprocess.run(['docker', 'tag', DIGEST, TAG], check=True)
    actual = subprocess.check_output(['docker', 'image', 'inspect', TAG, '--format', '{{.Id}}'], text=True).strip()
    assert actual == DIGEST, 'Recovered image identity changed'
    archive = destination / 'exact-image.oci.tar'
    receipt = {'passed': True, 'image': DIGEST, 'tag': TAG, 'build_record': BUILD_REF, 'source': 'Exact retained executable linux/arm64 BuildKit OCI blobs; no rebuild or substitution', 'missing_optional_attestation':'Historical in-toto layer unavailable. Platform-filtered import excludes attestation; no signed-provenance claim.', 'already_present': recovered, 'verified_blobs': blobs, 'archive_bytes': archive.stat().st_size if archive.exists() else None, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else None, 'evaluation_records_changed': False, 'model_dispatches': 0, 'recorded_at': datetime.now(timezone.utc).isoformat(), 'reference': 'https://github.com/docker/buildx/blob/master/commands/history/inspect_attachment.go'}
    (out / 'verifier-image-recovery.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
