"""Reproduce the selected CPU retrieval head from exact captured embeddings."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_SHA = '3d8d8769715c86b5d808ccfce4a0d894bdd4d289986cbb0f6b57900df9d7810d'
MAX_CACHE = 32 * 1024**2

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def unpack_cache(package, split, target):
    manifest = package / 'summary.json'
    if manifest.is_symlink() or sha(manifest.read_bytes()) != SUMMARY_SHA:
        raise ValueError('Reviewed training package manifest differs')
    summary = json.loads(manifest.read_bytes())
    item = summary['caches'][split]
    source = package / item['logical_path']
    if source.is_symlink() or not source.resolve().is_relative_to(package.resolve()):
        raise ValueError('Embedding archive escapes the package')
    raw = source.read_bytes()
    if sha(raw) != item['compressed_sha256'] or source.stat().st_size > MAX_CACHE:
        raise ValueError('Embedding archive hash or size differs')
    if target.exists() or target.is_symlink():
        raise ValueError('Cache extraction target must be new')
    with gzip.open(source, 'rb') as stream:
        expanded = stream.read(MAX_CACHE + 1)
    if len(expanded) != item['raw_bytes'] or len(expanded) > MAX_CACHE or sha(expanded) != item['raw_sha256']:
        raise ValueError('Expanded embedding bytes differ')
    target.write_bytes(expanded)
    return summary, item['raw_sha256']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    a = parser.parse_args()
    from scripts.retrieval011.__main__ import storage_guard
    if any(p.is_symlink() for p in (a.output, *a.output.parents)):
        parser.error('Output must not traverse symlinks')
    if a.output.exists() or not any(a.output.absolute().is_relative_to(p.absolute()) for p in a.budget_root):
        parser.error('Output must be new and inside the declared aggregate storage roots')
    storage_guard(a.budget_root, projected=64 * 1024**2)
    a.output.mkdir(parents=True, mode=0o700)
    package = ROOT / 'evidence/measurement014/training'
    summary, cache_sha = unpack_cache(package, 'train-dev', a.output / 'train-dev.json')
    selection_path = package / 'selected-training014.json'
    if sha(selection_path.read_bytes()) != summary['files']['selected-training014.json']['sha256']:
        raise ValueError('Frozen selection bytes differ')
    selection = json.loads(selection_path.read_bytes())
    for name, expected in selection['source_sha256'].items():
        source = ROOT / name
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT) or sha(source.read_bytes()) != expected:
            raise ValueError('Frozen training implementation differs: ' + name)
    argv = [sys.executable, '-m', 'scripts.source_variants014', '--profile', 'hard8-lr0003',
        '--data', str(ROOT / 'evidence/measurement014/data/prepared'), '--cache', str(a.output / 'train-dev.json'),
        '--output', str(a.output / 'fit'), '--frozen-sha256', summary['frozen_sha256'], '--cache-sha256', cache_sha]
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1', 'OMP_NUM_THREADS': '2'}
    with (a.output / 'fit.log').open('wb') as log:
        completed = subprocess.run(argv, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    if completed.returncode:
        raise SystemExit('Training failed; captured fit.log retained')
    result = json.loads((a.output / 'fit/training-report.json').read_bytes())
    artifact = a.output / 'fit/selected-inference/manifest.json'
    exact_manifest = sha(artifact.read_bytes()) == summary['adapter_manifest_sha256']
    exact = (sha((artifact.parent / 'adapter.json').read_bytes()) == summary['files']['adapter/adapter.json']['sha256'] and result['selected_step'] == summary['selected_step'])
    receipt = {'version': 'training014-reproduction-v1', 'passed': exact, 'selected_step': result['selected_step'],
        'projection_bytes_equal': exact, 'complete_manifest_equal': exact_manifest,
        'checkpoint_manifest_sha256': result['checkpoint_manifest_sha256'], 'adapter_manifest_sha256': sha(artifact.read_bytes()),
        'scope': 'CPU reproduction from captured frozen embeddings; encoder execution and hidden evaluation are separate receipts',
        'runtime': result['runtime']}
    (a.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    raise SystemExit(0 if exact else 1)

if __name__ == '__main__':
    main()
