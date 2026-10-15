"""Prepare or verify the pinned local code encoder; no Docker or account access."""
from pathlib import Path
import argparse
import base64
import hashlib
import io
import json
import struct
import urllib.request

from scripts.retrieval011.__main__ import storage_guard
from scripts.retrieval011.encoder import MODEL, REVISION, verify_profile

ROOT = Path(__file__).resolve().parents[1]


def prepare(directory, profile, header, budget_roots, check_only=False):
    directory = Path(directory).absolute()
    if not any(directory.is_relative_to(Path(p).absolute()) for p in budget_roots):
        raise ValueError("Encoder directory must belong to a declared owned experiment root")
    before = storage_guard(budget_roots)
    if directory.exists():
        verify_profile(directory, profile)
        return {"prepared": True, "reused": True, "model": MODEL, "revision": REVISION,
                "storage": before, "network_requests": 0}
    if check_only:
        raise ValueError("Prepared encoder is unavailable")
    projected = sum(row['bytes'] for row in profile['files'].values())
    storage_guard(budget_roots, projected)
    raw_header = base64.b64decode(header['header'], validate=True)
    if (len(raw_header) != header['bytes'] or len(raw_header) > 65536
            or hashlib.sha256(raw_header).hexdigest() != header['sha256']):
        raise ValueError("Pinned safetensors header is corrupt")
    try:
        import torch
        from safetensors.torch import load, save
    except ImportError as error:
        raise ValueError("Install the optional requirements-retrieval011.lock dependencies") from error
    directory.parent.mkdir(parents=True, exist_ok=True)
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise ValueError("Encoder storage cannot traverse symlinks")
    directory.mkdir(mode=0o700)
    requests = 0
    for name, expected in profile['files'].items():
        if name == 'model.fp16.safetensors':
            continue
        url = f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}'
        with urllib.request.urlopen(url, timeout=120) as stream:
            raw = stream.read(expected['bytes'] + 1)
        requests += 1
        if len(raw) != expected['bytes'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError('Pinned public encoder metadata differs')
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    expected = profile['original_weights']
    digest, buffer, size = hashlib.sha256(), io.BytesIO(), 0
    with urllib.request.urlopen(f'https://huggingface.co/{MODEL}/resolve/{REVISION}/model.safetensors', timeout=120) as stream:
        while block := stream.read(1024**2):
            size += len(block)
            if size > expected['bytes']:
                raise ValueError('Public model exceeded the pinned byte limit')
            digest.update(block)
            buffer.write(block)
    requests += 1
    if size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
        raise ValueError('Pinned original weight digest differs')
    weights = load(buffer.getvalue())
    buffer.close()
    half = {name: tensor.to(torch.float16) if tensor.is_floating_point() else tensor
            for name, tensor in weights.items()}
    del weights
    converted = save(half, metadata={'source_model': MODEL, 'source_revision': REVISION,
        'source_sha256': expected['sha256'], 'conversion': 'FP32 floating weights rounded to FP16 for storage'})
    length = struct.unpack('<Q', converted[:8])[0]
    if json.loads(converted[8:8 + length]) != json.loads(raw_header):
        raise ValueError('Derived weight tensor layout differs from the frozen profile')
    body = converted[8 + length:]
    digest = hashlib.sha256(struct.pack('<Q', len(raw_header)) + raw_header)
    digest.update(body)
    if digest.hexdigest() != profile['files']['model.fp16.safetensors']['sha256']:
        raise ValueError('Derived encoder bytes differ from the frozen profile')
    with (directory / 'model.fp16.safetensors').open('xb') as stream:
        stream.write(struct.pack('<Q', len(raw_header)))
        stream.write(raw_header)
        stream.write(body)
    verify_profile(directory, profile)
    return {'prepared': True, 'reused': False, 'model': MODEL, 'revision': REVISION,
            'storage_before': before, 'storage_after': storage_guard(budget_roots),
            'network_requests': requests,
            'scope': 'Pinned public encoder and exact documented FP16-storage conversion; no repair-model inference'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--encoder-dir', type=Path, required=True)
    parser.add_argument('--profile', type=Path, default=ROOT / 'profiles/coderank011.json')
    parser.add_argument('--header', type=Path, default=ROOT / 'profiles/coderank011-header.json')
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    try:
        for path in (args.profile, args.header):
            if path.is_symlink() or path.stat().st_size > 65536:
                raise ValueError('Frozen profile must be a bounded ordinary file')
        result = prepare(args.encoder_dir, json.loads(args.profile.read_text()),
                         json.loads(args.header.read_text()), args.budget_root, args.check_only)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Encoder preparation refused: ' + str(error) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
