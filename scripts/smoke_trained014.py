"""Exercise actual encoder/head/index integration on an explicitly synthetic source fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import time
from scripts.retrieval011.__main__ import storage_guard

SOURCE = '''import hmac
import re

def slugify(text):
    """Convert a heading to a lowercase URL slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def running_total(values):
    """Return the cumulative sums of a sequence of numbers."""
    result = []
    total = 0
    for value in values:
        total += value
        result.append(total)
    return result

def validate_token(candidate, expected):
    """Compare authentication tokens in constant time."""
    return hmac.compare_digest(candidate, expected)
'''
ROOT = Path(__file__).resolve().parents[1]
HEAD = '404b4e89a224ee424da41b650e23619d401e6b9187fd5f1f2209d1190bff62d0'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['encoder-dir', 'profile', 'output']:p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--budget-root', type=Path, action='append', required=True)
    p.add_argument('--backend', choices=['numpy', 'faiss'], default='numpy')
    a = p.parse_args()
    if a.output.exists() or any(x.is_symlink() for x in [a.output,*a.output.parents]):p.error('New ordinary output path required')
    if not all(any(path.absolute().is_relative_to(r.absolute()) for r in a.budget_root) for path in [a.output,a.encoder_dir]):p.error('Output and weights must belong to counted roots')
    budget = storage_guard(a.budget_root, projected=16*1024**2)
    a.output.mkdir(parents=True, mode=0o700)
    from scripts.retrieval011.encoder import CodeRankEncoder
    from scripts.trained_encoder014 import TrainedCodeEncoder014
    from scripts.retrieval011.core import build_index, query
    profile = json.loads(a.profile.read_bytes())
    started = time.monotonic()
    base = CodeRankEncoder(a.encoder_dir, profile, batch_size=2, threads=2)
    encoder = TrainedCodeEncoder014(base, ROOT / 'evidence/measurement014/training/adapter', HEAD)
    source = a.output / 'source/sample';source.mkdir(parents=True)
    (source / 'functions.py').write_text(SOURCE)
    revision = hashlib.sha256(SOURCE.encode()).hexdigest()
    index = build_index(a.output/'source','sample/',revision,a.output/'indexes',encoder=encoder,exact_backend=a.backend)
    result = query(index,'compare authentication tokens in constant time',mode='dense',limit=3,encoder=encoder)
    rejected = False
    try: query(index,'compare authentication tokens',mode='dense',encoder=base)
    except ValueError as error:
        if 'differs' not in str(error):raise
        rejected = True
    if not rejected or not result.selected:raise ValueError('Trained retrieval integration did not complete')
    receipt = {'version':'trained-retrieval014-smoke-v1','passed':True,'synthetic_fixture':True,
        'scope':'Actual pinned encoder and learned head; mechanical integration only, not retrieval quality or repair evidence',
        'adapter_manifest_sha256':HEAD,'index_id':index.index_id,'backend':a.backend,'chunks':len(index.chunks),
        'base_query_encoder_rejected':rejected,'elapsed_seconds':time.monotonic()-started,
        'selected':[{'path':x['chunk']['path'],'start_line':x['chunk']['start_line'],'end_line':x['chunk']['end_line'],'score':x['score']} for x in result.selected],
        'encoder_identity':encoder.identity,'storage_before':budget}
    (a.output/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['passed','chunks','backend','base_query_encoder_rejected','elapsed_seconds']}))

if __name__ == '__main__':main()
