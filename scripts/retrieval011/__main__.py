"""Build/query revision-bound source indexes without Docker or live repair calls."""
from pathlib import Path
import argparse
import json
import shutil
import time

from .core import Limits, build_index, load_index, query


def storage_guard(roots, projected=0):
    if not roots:
        raise ValueError("Declare all owned experiment roots with --budget-root")
    paths = sorted({Path(p).absolute() for p in roots}, key=lambda p: len(p.parts))
    if any(any(q.is_symlink() for q in (p, *p.parents)) for p in paths):
        raise ValueError("Budget roots cannot traverse symlinks")
    unique = [p for i, p in enumerate(paths) if not any(p.is_relative_to(old) for old in paths[:i])]
    if any(not p.is_dir() for p in unique):
        raise ValueError("Declared budget roots must already exist")
    owned = sum(q.stat().st_size for p in unique for q in p.rglob('*')
                if q.is_file() and not q.is_symlink())
    free = min(shutil.disk_usage(p).free for p in unique)
    if owned + projected > 6 * 1024**3 or free - projected < 4 * 1024**3:
        raise ValueError("Declared experiment storage exceeds 6 GiB or the 4 GiB free reserve")
    return {"owned_bytes": owned, "projected_bytes": projected, "free_bytes": free,
            "budget_bytes": 6 * 1024**3, "reserve_bytes": 4 * 1024**3,
            "scope": "Caller-declared owned experiment roots, de-duplicated; machine paths are private"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'query'))
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--approved-prefix', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--index-root', type=Path, required=True)
    parser.add_argument('--index-id')
    parser.add_argument('--exact-backend', choices=('numpy', 'faiss'), default='numpy')
    parser.add_argument('--mode', choices=('lexical', 'dense', 'hybrid'), default='lexical')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--encoder-dir', type=Path)
    parser.add_argument('--query')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--budget-root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        original_root = args.source_root.resolve(strict=True)
        if args.output and args.output.resolve(strict=False).is_relative_to(original_root):
            raise ValueError("Evidence output must be outside the original source snapshot")
        anchor = args.index_root.absolute()
        if anchor.resolve(strict=False).is_relative_to(original_root) or original_root.is_relative_to(anchor.resolve(strict=False)):
            raise ValueError("Index storage must be separate from original source")
        if not any(anchor.is_relative_to(p.absolute()) for p in args.budget_root):
            raise ValueError("Index storage must belong to a declared budget root")
        storage = storage_guard(args.budget_root, 96 * 1024**2 if args.action == 'build' else 0)
        encoder = None
        if args.mode != 'lexical':
            if not args.profile or not args.encoder_dir:
                raise ValueError("Dense/hybrid retrieval requires explicit pinned profile and model directory")
            if args.profile.stat().st_size > 65536 or args.profile.is_symlink():
                raise ValueError("Encoder profile must be a bounded ordinary file")
            if not any(args.encoder_dir.absolute().is_relative_to(p.absolute()) for p in args.budget_root):
                raise ValueError("Encoder storage must belong to a declared budget root")
            from .encoder import CodeRankEncoder
            encoder = CodeRankEncoder(args.encoder_dir, json.loads(args.profile.read_text()))
        started = time.monotonic()
        if args.action == 'build':
            index = build_index(args.source_root, args.approved_prefix, args.revision,
                                args.index_root, encoder=encoder, limits=Limits(encode_batch_size=16),
                                exact_backend=args.exact_backend)
            result = {"action": "build", "index_id": index.index_id, "revision": index.revision,
                "source_snapshot_digest": index.source_snapshot_digest,
                "files": len(index.files), "chunks": len(index.chunks),
                "source_omissions": list(index.omissions), "encoder_identity": index.encoder_identity,
                "exact_backend": index.exact_backend, "seconds": round(time.monotonic() - started, 3)}
        else:
            if not args.index_id or not args.query:
                raise ValueError("Query requires an existing --index-id and explicit --query")
            index = load_index(args.index_root, args.index_id, args.source_root,
                               args.approved_prefix, args.revision, encoder=encoder)
            found = query(index, args.query, mode=args.mode, limit=args.limit, encoder=encoder)
            result = {"action": "query", "audit": found.audit,
                      "regions": [item['chunk'] for item in found.selected],
                      "seconds": round(time.monotonic() - started, 3)}
        result['storage_before'] = storage
        result['storage_after'] = storage_guard(args.budget_root)
        raw = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
        if args.output:
            if args.output.is_symlink():
                raise ValueError("Output cannot be a symlink")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as stream:
                stream.write(raw)
            print(json.dumps({"completed": True, "action": args.action,
                              "index_id": index.index_id, "seconds": result['seconds']}))
        else:
            print(raw, end='')
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Retrieval refused: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
