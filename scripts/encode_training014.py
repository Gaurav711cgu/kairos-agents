"""Encode separately admitted source-training or held-out data with pinned weights."""
from pathlib import Path
import argparse
import math
import json
import os
import time

from scripts.build_functions014 import load_for_training014, canonical, sha
from scripts.evaluate_functions014 import load_for_evaluation014
from scripts.retrieval011.encoder import CodeRankEncoder, verify_profile
from scripts.retrieval011.__main__ import storage_guard


PROFILE_SHA256 = "2aa1ac9712e4e22d3be04c46dd136245ad18f304999a244c308e699c158d99c0"


def _metadata(value, texts, *, queries):
    """Consume CodeRank's documented metadata dictionary and bind exact inputs."""
    if (not isinstance(value, dict) or value.get("query_prefix_applied") is not queries
            or value.get("max_tokens") != 512 or not isinstance(value.get("inputs"), list)
            or len(value["inputs"]) != len(texts)):
        raise ValueError("Encoder metadata shape, prefix or token limit changed")
    for item, text in zip(value["inputs"], texts):
        if (not isinstance(item, dict) or item.get("input_sha256") != sha(text)
                or type(item.get("encoded_tokens")) is not int
                or not 0 < item["encoded_tokens"] <= 512
                or type(item.get("input_tokens_with_special_and_prefix")) is not int
                or item["input_tokens_with_special_and_prefix"] < item["encoded_tokens"]
                or type(item.get("truncated")) is not bool
                or type(item.get("included_character_end")) is not int
                or not 0 <= item["included_character_end"] <= len(text)
                or type(item.get("omitted_bytes")) is not int
                or item["omitted_bytes"] != (len(text[item["included_character_end"]:].encode()) if item["truncated"] else 0)):
            raise ValueError("Encoder metadata does not bind exact admitted input")
    return value["inputs"]


def _vectors(value, count):
    if len(value) != count:
        raise ValueError("Encoder row count changed")
    result = []
    for vector in value:
        row = vector.tolist()
        if (len(row) != 768 or any(type(number) not in (float, int) or not math.isfinite(number) for number in row)
                or abs(sum(number * number for number in row) - 1) > 1e-4):
            raise ValueError("Encoder must return finite L2-normalized 768-dimensional vectors")
        result.append(row)
    return result


def encode(args):
    if any(path.is_symlink() for path in (args.data.absolute(), *args.data.absolute().parents)):
        raise ValueError("Data root cannot traverse symlinks")
    data = args.data.resolve(strict=True)
    if args.output.exists() or any(path.is_symlink() for path in (args.output.absolute(), *args.output.absolute().parents)):
        raise ValueError('Use a new encoding output directory')
    if not any(args.output.absolute().is_relative_to(p.absolute()) for p in args.budget_root):
        raise ValueError('Output must belong to the aggregate experiment budget')
    # The training path never opens the private manifest or holdout file.
    if args.heldout:
        rows, _ = load_for_evaluation014(data, args.frozen_sha256)
    else:
        train, development, _ = load_for_training014(data, args.frozen_sha256)
        rows = [*train, *development]
    if args.profile.is_symlink() or not args.profile.is_file() or args.profile.stat().st_size > 65536:
        raise ValueError("Encoder profile must be a bounded ordinary file")
    profile = json.loads(args.profile.read_text())
    if sha(canonical(profile)) != PROFILE_SHA256 or profile.get("max_tokens") != 512:
        raise ValueError("Trusted encoder profile changed")
    if not any(args.encoder_dir.absolute().is_relative_to(p.absolute()) for p in args.budget_root):
        raise ValueError("Encoder must belong to the aggregate experiment budget")
    verify_profile(args.encoder_dir, profile)
    before = storage_guard(args.budget_root, len(rows) * 768 * 2 * 26 + 4 * 1024**2)
    args.output.mkdir(parents=True, mode=0o700)
    started = time.monotonic()
    encoder = CodeRankEncoder(args.encoder_dir, profile, batch_size=2, threads=2)
    encoded, metadata = [], []
    for start in range(0, len(rows), 16):
        group = rows[start:start + 16]
        query_texts = [row['query'] for row in group]
        code_texts = [row['code'] for row in group]
        query = _vectors(encoder.encode_queries(query_texts), len(group))
        query_metadata = _metadata(encoder.last_metadata, query_texts, queries=True)
        code = _vectors(encoder.encode(code_texts), len(group))
        code_metadata = _metadata(encoder.last_metadata, code_texts, queries=False)
        for i, row in enumerate(group):
            encoded.append({'example_id': row['example_id'], 'query_sha256': sha(row['query']),
                'code_sha256': sha(row['code']), 'query': query[i], 'code': code[i]})
            metadata.append({'example_id': row['example_id'], 'query': query_metadata[i], 'code': code_metadata[i]})
        print(json.dumps({'encoded': min(start + 16, len(rows)), 'total': len(rows), 'heldout': args.heldout}), flush=True)
    identity = {'model_id': profile['model'], 'revision': profile['revision'], 'dimension': 768,
        'pooling': 'cls', 'normalize': True, 'max_tokens': 512, 'query_prefix': profile['query_prefix'],
        'profile_sha256': sha(canonical(profile))}
    cache = {'schema_version': 'kairos-frozen-embeddings014-v1', 'frozen_sha256': args.frozen_sha256,
             'encoder': identity, 'rows': encoded}
    raw = canonical(cache) + b'\n'
    target = args.output / 'embeddings.json'
    with target.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    receipt = {'version': 'encoding014-v1', 'rows': len(rows), 'heldout': args.heldout,
        'cache_sha256': sha(raw), 'cache_bytes': len(raw), 'frozen_sha256': args.frozen_sha256,
        'encoder': identity, 'encoding': metadata, 'elapsed_seconds': time.monotonic() - started,
        'implementation_sha256': sha(Path(__file__).read_bytes()), 'storage_before': before,
        'scope': 'Frozen base embeddings only; no optimizer, model fitting or repair outcome'}
    (args.output / 'receipt.json').write_bytes(canonical(receipt) + b'\n')
    storage_guard(args.budget_root)
    print(json.dumps({k: receipt[k] for k in ('rows', 'heldout', 'cache_sha256', 'elapsed_seconds')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'output', 'profile', 'encoder-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--frozen-sha256', required=True)
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--heldout', action='store_true')
    encode(parser.parse_args())


if __name__ == '__main__':
    main()
