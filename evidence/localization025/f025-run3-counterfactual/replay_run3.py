"""Counterfactual: real run-3 replies through the fixed edit layer on pinned source. Not a model run."""
import json, pathlib, collections
from types import SimpleNamespace
from kairos_api.investigations.sandbox import Workspace
from scripts.search_replace025 import parse_blocks, apply_blocks
H = pathlib.Path.home() / 'Desktop/resume/kairos-closeout020/f025-run3'
X = H / 'results/extract/f025-results'
W = pathlib.Path('/private/tmp/f025-score-run3-work')
pkg = {c['chain_id']: c for c in json.loads((H / 'upload/f025-package.json').read_text())['chains']}
out, tally = {}, collections.Counter()
for chain_id, c in sorted(pkg.items()):
    inst = chain_id.split('/')[1]
    case_dir = W / inst / 'registry/cases' / inst
    rec = json.loads((X / 'chains' / (chain_id + '.json')).read_text())
    regions = rec['regions'] + rec.get('read_regions', [])
    rows = []
    for f in sorted((X / 'captures' / chain_id).glob('c*.json')):
        blocks = parse_blocks(json.loads(f.read_text())['result']['text'])
        if not blocks:
            continue
        w = Workspace(SimpleNamespace(verify=lambda _: None, directory=lambda _: case_dir), {'issue': '', 'approved_prefix': 'django/', 'entry_files': []})
        try:
            v = apply_blocks(w, blocks, regions)
        finally:
            w.close()
        rows.append({'call': f.stem, 'accepted': v['accepted'], 'reason': (v['reason'] or '')[:120], 'patch': v['patch']})
        tally['accepted' if v['accepted'] else 'rejected'] += 1
    out[chain_id] = rows
    first = next((r for r in rows if r['accepted']), None)
    print(f"{chain_id:38} orig={rec['status']:9} edit_replies={len(rows)} first_accept={first['call'] if first else None}",
          '' if first else (rows[-1]['reason'] if rows else 'no edit replies'))
print(dict(tally))
json.dump(out, open(pathlib.Path(__file__).parent / 'replay_run3.json', 'w'), indent=1)
