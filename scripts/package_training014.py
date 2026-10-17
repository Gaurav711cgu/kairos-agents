"""Package measured retrieval training without publishing runtime state or weights."""
from pathlib import Path
import argparse
import base64
import gzip
import hashlib
import json

FROZEN = '0665b9ec9202ac05ff1a71f1c66239ac13081eb2cdd207e5dfa4402e07872729'
SELECTED = '404b4e89a224ee424da41b650e23619d401e6b9187fd5f1f2209d1190bff62d0'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()

def package(runtime, output, website):
    if output.exists() or website.exists():
        raise ValueError('Packaging destinations must be new; preserve earlier receipts')
    selection = json.loads((runtime / 'selected-training014.json').read_bytes())
    evaluation = json.loads((runtime / 'heldout-evaluation014.json').read_bytes())
    if selection['heldout_metrics_read'] is not False or evaluation['frozen_sha256'] != FROZEN or evaluation['inference_manifest_sha256'] != SELECTED:
        raise ValueError('Selection or frozen evaluator identity differs')
    files = {}
    for name in ['selected-training014.json', 'selected-resume014.json', 'heldout-evaluation014.json', 'development-revisions014.json']:
        files[name] = (runtime / name).read_bytes()
    for run in ['training014-full', 'training014-hard8-lr0003', 'training014-hard8-lr001']:
        files[run + '/training-report.json'] = (runtime / run / 'training-report.json').read_bytes()
    selected = runtime / 'training014-hard8-lr0003' / 'selected-inference'
    manifest = (selected / 'manifest.json').read_bytes()
    if sha(manifest) != SELECTED:
        raise ValueError('Selected adapter manifest changed')
    for name in ['adapter.json', 'manifest.json']:
        files['adapter/' + name] = (selected / name).read_bytes()
    for filename, identity in json.loads(manifest)['files'].items():
        raw = files['adapter/' + filename]
        if sha(raw) != identity['sha256'] or len(raw) != identity['bytes']:
            raise ValueError('Selected adapter tensor bytes changed')
    caches = {}
    for split in ['train-dev', 'holdout']:
        directory = runtime / ('encoding-' + split + '014')
        raw = (directory / 'embeddings.json').read_bytes()
        receipt = json.loads((directory / 'receipt.json').read_bytes())
        if sha(raw) != receipt['cache_sha256'] or receipt['frozen_sha256'] != FROZEN:
            raise ValueError('Captured embedding bytes differ')
        compressed = gzip.compress(raw, mtime=0)
        if gzip.decompress(compressed) != raw:
            raise ValueError('Cache round trip differs')
        name = 'embeddings/' + split + '.json.gz'
        files[name] = compressed
        files['embeddings/' + split + '-receipt.json'] = encode(receipt)
        caches[split] = {'logical_path': name, 'compressed_sha256': sha(compressed), 'raw_sha256': sha(raw), 'raw_bytes': len(raw)}
    for name, raw in files.items():
        if not name.endswith('.gz') and (b'/Users/' in raw or b'api_key' in raw.lower()):
            raise ValueError('Machine path or credential-like field in public capture: ' + name)
    summary = {'version': 'retrieval-training014-public-v1', 'parameters': 24576, 'steps': 200, 'selected_step': evaluation['selected_step'],
        'train': 166, 'development': 135, 'heldout': evaluation['queries'], 'model': 'nomic-ai/CodeRankEmbed',
        'encoder_frozen': True, 'scope': 'Repository-disjoint docstring-to-function retrieval; original docstrings removed from code',
        'summary': evaluation['summary'], 'uncertainty': evaluation['uncertainty'], 'changes': evaluation['mrr_comparison'],
        'resume': json.loads(files['selected-resume014.json']), 'frozen_sha256': FROZEN, 'adapter_manifest_sha256': SELECTED,
        'caches': caches, 'selection': 'Development only, three predeclared profiles; no held-out retuning',
        'files': {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(files.items())}}
    files['summary.json'] = encode(summary)
    output.mkdir(parents=True)
    for name, raw in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    # Fixed logical downloads reuse the existing bounded, hash-checked HTTP codec.
    download_files = {'bundle.json': files['heldout-evaluation014.json'], 'receipt.json': files['selected-resume014.json'],
        'retrieval.json': files['summary.json'], 'adapter.json': files['adapter/adapter.json']}
    downloads = {name: {'filename': name, 'media_type': 'application/json', 'bytes': len(raw), 'sha256': sha(raw),
        'base64': base64.b64encode(raw).decode()} for name, raw in download_files.items()}
    website.mkdir(parents=True)
    (website / 'training014-summary.json').write_bytes(encode(summary))
    (website / 'training014-downloads.json').write_bytes(encode(downloads))
    return {'files': len(files), 'bytes': sum(map(len, files.values())), 'summary_sha256': sha(files['summary.json'])}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['runtime', 'output', 'website']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(package(a.runtime, a.output, a.website)))

if __name__ == '__main__':
    main()
