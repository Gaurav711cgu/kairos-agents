"""Read-only error analysis of F025 run-3 rejected replies against pinned base source."""
import json, pathlib, re, difflib
from scripts.search_replace025 import parse_blocks
H = pathlib.Path.home() / 'Desktop/resume/kairos-closeout020/f025-run3'
X = H / 'results/extract/f025-results'
W = pathlib.Path('/private/tmp/f025-score-run3-work')
pkg = {c['chain_id']: c for c in json.loads((H / 'upload/f025-package.json').read_text())['chains']}
for chain_id in sorted(pkg):
    inst = chain_id.split('/')[1]
    src = W / inst / 'registry/cases' / inst / 'source'
    region_paths = sorted({r['path'] for r in pkg[chain_id]['regions']})
    receipts = [json.loads(l) for l in (X / 'receipts' / (chain_id + '.jsonl')).read_text().splitlines()]
    for f, rec in zip(sorted((X / 'captures' / chain_id).glob('c*.json')), receipts):
        text = json.loads(f.read_text())['result']['text']
        if rec['kind'] in ('accepted',):
            continue
        blocks = parse_blocks(text)
        head = f'{chain_id[-20:]} {f.stem} {rec["kind"]}'
        if not blocks:
            print(head, 'NO-BLOCK reply:', repr(text[:160]))
            continue
        for path, search, _ in blocks:
            real = re.sub(r'^(path/to/)+', '', path)
            candidates = [real] if (src / real).is_file() else region_paths
            best = None
            for p in candidates:
                lines = (src / p).read_text().splitlines(True)
                s = search.splitlines(True)
                for i in range(len(lines) - len(s) + 1):
                    ratio = difflib.SequenceMatcher(None, ''.join(lines[i:i + len(s)]), search).ratio()
                    if not best or ratio > best[0]:
                        best = (ratio, p, i + 1, lines[i:i + len(s)])
            ratio, p, line, window = best
            exact = (src / p).read_text().count(search)
            first_diff = next(((a, b) for a, b in zip(search.splitlines(True), window) if a != b), None)
            print(head, f'path={path!r} -> {p}:{line} exact_count={exact} similarity={ratio:.2f}')
            if first_diff:
                print('     model:', repr(first_diff[0][:100])); print('     real :', repr(first_diff[1][:100]))
