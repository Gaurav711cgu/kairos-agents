"""Revision-bound, issue-only localization benchmark on development cases.

Retrieval arms receive only the public issue and pinned original source. Gold
patch paths are parsed after every arm has finished and are used only for
scoring. Exposed identifiers (any mention in this repository or the resume
evidence tree) are excluded before the deterministic split. The validation and
holdout buckets are never fetched by this command. No model, Docker or training.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import time
import types
import urllib.request
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
VERSION = 'localization-dev024-v1'
PREFIXES = {'django/django': 'django/', 'pytest-dev/pytest': 'src/_pytest/'}
ID = re.compile(rb'(?:django__django|pytest-dev__pytest)-[0-9]+')
SPLIT_SALT = 'kairos-split024:'
MAX_ARCHIVE = 80 * 1024 ** 2
MAX_REGIONS = 4  # both arms cap context at four regions, so recall beyond @4 is undefined


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def exposed_ids(roots, skip, own):
    """Every case identifier mentioned anywhere in local evidence counts as exposed."""
    found = set()
    for root in roots:
        for directory, names, files in os.walk(root):
            if Path(directory).resolve() in own:
                names[:] = []
                continue
            names[:] = [n for n in names if n not in {'.git', 'node_modules', '.venv', '.next', '__pycache__'}]
            for name in files:
                path = Path(directory, name)
                if path.resolve() in skip:
                    continue
                try:
                    if path.is_symlink() or path.stat().st_size > 50 * 1024 ** 2:
                        continue
                    found.update(m.decode() for m in ID.findall(path.read_bytes()))
                    if zipfile.is_zipfile(path):  # compressed members hide identifiers from the byte scan
                        with zipfile.ZipFile(path) as archive:
                            for member in archive.infolist():
                                if member.file_size <= 50 * 1024 ** 2:
                                    found.update(m.decode() for m in ID.findall(archive.read(member)))
                except (OSError, zipfile.BadZipFile):
                    continue
    return found


def bucket(instance_id):
    value = int(hashlib.sha256((SPLIT_SALT + instance_id).encode()).hexdigest(), 16) % 10
    return 'development' if value < 3 else 'validation' if value < 5 else 'holdout'


def targets(patch, prefix):
    paths = dict.fromkeys(re.findall(r'^diff --git a/(\S+) b/', patch, re.M))
    return [p for p in paths if p.startswith(prefix) and p.endswith('.py')]


def fetch(row, cache):
    """Extract only approved-prefix Python files from the pinned public archive."""
    directory = cache / row['instance_id']
    receipt_path = directory / 'source.json'
    if receipt_path.exists():
        return json.loads(receipt_path.read_text())
    repository, revision, prefix = row['repo'], row['base_commit'], PREFIXES[row['repo']]
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Unpinned revision')
    url = 'https://codeload.github.com/' + repository + '/tar.gz/' + revision
    source = directory / 'source'
    source.mkdir(parents=True, exist_ok=False)
    hasher, total, files = hashlib.sha256(), 0, 0

    class Bounded:
        def __init__(self, raw):
            self.raw = raw

        def read(self, size=-1):
            nonlocal total
            chunk = self.raw.read(size)
            total += len(chunk)
            if total > MAX_ARCHIVE:
                raise ValueError('Archive exceeds bounded download')
            hasher.update(chunk)
            return chunk

    with urllib.request.urlopen(url, timeout=120) as response:
        if response.geturl() != url:
            raise ValueError('Pinned archive URL redirected')
        with tarfile.open(fileobj=Bounded(response), mode='r|gz') as archive:
            for member in archive:
                parts = member.name.split('/', 1)
                if len(parts) != 2 or not member.isreg():
                    continue
                relative = parts[1]
                if not relative.startswith(prefix) or not relative.endswith('.py') or '..' in relative.split('/'):
                    continue
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                files += 1
        while response.read(1024 * 1024):
            pass
    receipt = {'repository': repository, 'revision': revision, 'url': url, 'archive_bytes': total,
               'archive_sha256': hasher.hexdigest(), 'python_files': files}
    receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    return receipt


class ChatTokenizer:
    """Qwen2.5 system/user chat template over the hash-bound tokenizer.json.

    Verified token-identical to transformers apply_chat_template on all 20
    frozen unseen023 prompts; any other role shape is refused.
    """

    def __init__(self, path):
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(path))

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=True):
        if [m['role'] for m in messages] != ['system', 'user'] or not tokenize or not add_generation_prompt:
            raise ValueError('Unsupported chat-template shape')
        text = ''.join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages) + '<|im_start|>assistant\n'
        return self.tokenizer.encode(text, add_special_tokens=False).ids


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace(row, cache):
    from kairos_api.investigations.sandbox import Workspace
    directory = cache / row['instance_id']
    view = types.SimpleNamespace(
        case={'id': row['instance_id'], 'issue': row['problem_statement'], 'approved_prefix': PREFIXES[row['repo']],
              'entry_files': [], 'entry_lines': {}},
        registry=types.SimpleNamespace(directory=lambda _: directory), references={})
    view.read_original = types.MethodType(Workspace.read_original, view)
    return view


def arms():
    """Frozen v3, checkpointed H1/H2 selector snapshots, and the live candidate."""
    from scripts import coding_context_v3_014, coding_context_v6_024
    snapshots = PROJECT / 'evidence/localization024'
    return {'frozen023': coding_context_v3_014.select,
            'h1': load_module('selector_h1', snapshots / 'h1/source/coding_context_v6_024.py').select,
            'h2': load_module('selector_h2', snapshots / 'h2/source/coding_context_v6_024.py').select,
            'candidate': coding_context_v6_024.select}


def ordered_paths(regions):
    return list(dict.fromkeys(r['reference']['path'] for r in regions))


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centre - half, 4), round(centre + half, 4)]


def score(paths, gold):
    rank = next((i + 1 for i, p in enumerate(paths) if p in gold), None)
    return {'rank': rank, **{f'recall@{k}': rank is not None and rank <= k for k in (1, MAX_REGIONS)}}


def summarize(rows, arm):
    scored = [r for r in rows if r['targets']]
    n = len(scored)
    out = {'cases': n}
    for key in ['recall@1', f'recall@{MAX_REGIONS}']:
        k = sum(r['arms'][arm]['selected'][key] for r in scored)
        out['selected_' + key] = {'k': k, 'n': n, 'ci95': wilson(k, n)}
    k = sum(r['arms'][arm]['final_context_hit'] for r in scored)
    out['final_context_recall'] = {'k': k, 'n': n, 'ci95': wilson(k, n)}
    for outcome in ['hunks_contained', 'scope_limit']:
        out[outcome] = sum(r['arms'][arm]['containment'] == outcome for r in scored)
    out['truncation_losses'] = sum(r['arms'][arm]['selected']['rank'] is not None and not r['arms'][arm]['final_context_hit'] for r in scored)
    out['mean_prompt_tokens'] = round(sum(r['arms'][arm]['prompt_tokens'] for r in scored) / max(n, 1), 1)
    out['mean_regions'] = round(sum(r['arms'][arm]['final_regions'] for r in scored) / max(n, 1), 2)
    out['seconds'] = round(sum(r['arms'][arm]['seconds'] for r in scored), 2)
    return out


def paired(rows, a, b, metric=lambda arm: arm['final_context_hit']):
    scored = [r for r in rows if r['targets']]
    gains = [r['instance_id'] for r in scored if metric(r['arms'][b]) and not metric(r['arms'][a])]
    losses = [r['instance_id'] for r in scored if metric(r['arms'][a]) and not metric(r['arms'][b])]
    gain, loss = len(gains), len(losses)
    # Exact two-sided sign test on discordant pairs.
    d = gain + loss
    p = min(1.0, 2 * sum(math.comb(d, i) for i in range(min(gain, loss) + 1)) / 2 ** d) if d else 1.0
    return {'baseline': a, 'candidate': b, 'gains': gain, 'losses': loss, 'sign_test_p': round(p, 4), 'gain_cases': gains, 'loss_cases': losses}


def containment(row, cache, record, finals):
    """Replay the gold edit inside each arm's final packed regions (scoring only)."""
    from kairos_api.investigations.sandbox import Workspace
    from scripts.coding_actions014 import convert_action
    from scripts.patch_roundtrip024 import classify, prefix_patch
    gold = prefix_patch(row['patch'], PREFIXES[row['repo']])
    directory = cache / row['instance_id']
    registry = types.SimpleNamespace(verify=lambda _: None, directory=lambda _: directory)
    work = Workspace(registry, {'id': row['instance_id'], 'issue': row['problem_statement'], 'approved_prefix': PREFIXES[row['repo']], 'entry_files': [], 'entry_lines': {}})
    try:
        for arm, final in finals.items():
            try:
                convert_action(work, gold, final, anchor_policy='captured-neighbor-coalesced-v3')
                record['arms'][arm]['containment'] = 'hunks_contained'
            except Exception as error:  # every rejection is classified, never dropped
                record['arms'][arm]['containment'] = classify(error) if final else 'no_context'
    finally:
        work.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parquet', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True, help='hash-bound tokenizer-assets directory')
    parser.add_argument('--context', type=Path, required=True, help='frozen unseen023 context.py providing pack()')
    parser.add_argument('--exposure-root', type=Path, action='append', required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-repository', type=int, default=20)
    parser.add_argument('--allow-source-download', action='store_true')
    parser.add_argument('--expect-exposure-sha256', help='fail instead of silently shifting the case pool')
    parser.add_argument('--bucket', choices=['development', 'validation'], default='development', help='holdout is never fetched')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Result receipts are immutable; choose a new output path')
    import pyarrow.parquet as pq
    table = pq.read_table(args.parquet, columns=['instance_id', 'repo', 'base_commit', 'problem_statement', 'patch'])
    rows = [r for r in table.to_pylist() if r['repo'] in PREFIXES]
    # This benchmark's own receipts name development/validation cases; they are not exposure.
    exposed = exposed_ids(args.exposure_root, {args.parquet.resolve()}, {(PROJECT / 'evidence/localization024').resolve()})
    exposed &= {r['instance_id'] for r in rows}  # test fixtures and prose numbers are not dataset cases
    if args.expect_exposure_sha256 and digest(sorted(exposed)) != args.expect_exposure_sha256:
        raise ValueError('Exposure identifier set changed; find the new mention before comparing runs')
    pool = [r for r in rows if r['instance_id'] not in exposed]
    split = {r['instance_id']: bucket(r['instance_id']) for r in pool}
    order = lambda r: hashlib.sha256((SPLIT_SALT + r['instance_id']).encode()).hexdigest()
    development = []
    for repository in PREFIXES:
        chosen = sorted((r for r in pool if r['repo'] == repository and split[r['instance_id']] == args.bucket), key=order)
        development.extend(chosen[:args.per_repository])
    pack = load_module('frozen_context023', args.context).pack
    tokenizer = ChatTokenizer(args.tokenizer / 'tokenizer.json')
    selectors = arms()
    results = []
    for row in development:
        if not args.allow_source_download and not (args.cache / row['instance_id'] / 'source.json').exists():
            raise ValueError('Pinned source missing; --allow-source-download not supplied')
        receipt = fetch(row, args.cache)
        record = {'instance_id': row['instance_id'], 'repository': row['repo'], 'revision': row['base_commit'],
                  'archive_sha256': receipt['archive_sha256'], 'issue_sha256': hashlib.sha256(row['problem_statement'].encode()).hexdigest(), 'arms': {}}
        finals = {}
        for arm, select in selectors.items():
            started = time.perf_counter()
            view = workspace(row, args.cache)
            regions = select(view)
            try:
                packed = pack(row['problem_statement'], regions, tokenizer)
                final, tokens, error = packed['regions'], packed['prompt_tokens'], None
            except ValueError as failure:
                final, tokens, error = [], 0, str(failure)
            finals[arm] = final
            record['arms'][arm] = {'selected_paths': ordered_paths(regions), 'final_paths': ordered_paths(final),
                                   'final_regions': len(final), 'prompt_tokens': tokens, 'pack_error': error,
                                   'seconds': round(time.perf_counter() - started, 3)}
        # Labels are read only after every arm has produced its context.
        gold = targets(row['patch'], PREFIXES[row['repo']])
        record['targets'] = gold
        for item in record['arms'].values():
            item['selected'] = score(item['selected_paths'], gold)
            item['final_context_hit'] = any(p in gold for p in item['final_paths'])
            item['indexed_target'] = all((args.cache / row['instance_id'] / 'source' / p).is_file() for p in gold)
        containment(row, args.cache, record, finals)
        results.append(record)
        print(json.dumps({'case': row['instance_id'], **{a: v['final_context_hit'] for a, v in record['arms'].items()}}), flush=True)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(['git', 'status', '--porcelain'], cwd=PROJECT, capture_output=True, text=True).stdout)
    counts = {name: sum(v == name for v in split.values()) for name in ['development', 'validation', 'holdout']}
    report = {
        'version': VERSION,
        'scope': args.bucket.capitalize() + '-bucket localization only; not repair performance. Labels used only for scoring.',
        'git_commit': commit, 'git_dirty': dirty,
        'implementation_sha256': {'benchmark': sha(__file__), 'context_pack': sha(args.context),
                                  **{name: sha(f.__globals__['__file__']) for name, f in selectors.items()}},
        'dataset': {'parquet_sha256': sha(args.parquet), 'rows_in_scope': len(rows)},
        'exposure': {'excluded': len(set(r['instance_id'] for r in rows) & exposed), 'identifiers_sha256': digest(sorted(exposed))},
        'split': {'salt': SPLIT_SALT, 'counts': counts, 'assignment_sha256': digest(split), 'fetched_buckets': [args.bucket]},
        'prompt_token_limit': 3072, 'model_calls': 0, 'docker_runs': 0,
        'summary': {arm: summarize(results, arm) for arm in selectors},
        'paired': {f'{a}->candidate': {'final_context': paired(results, a, 'candidate'), 'recall@1': paired(results, a, 'candidate', lambda x: x['selected']['recall@1']),
                                       'hunks_contained': paired(results, a, 'candidate', lambda x: x['containment'] == 'hunks_contained')}
                   for a in ['frozen023', 'h1', 'h2']},
        'cases': results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(report['summary'], indent=1))


if __name__ == '__main__':
    main()
