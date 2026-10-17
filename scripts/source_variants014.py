"""Two bounded development revisions; held-out data never enters selection."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import argparse
import json

from scripts import retrieval_adapter014 as trainer

PROFILES = {
    'hard8-lr0003': {'learning_rate': 0.0003, 'negative_top_k': 8},
    'hard8-lr001': {'learning_rate': 0.001, 'negative_top_k': 8},
}


def hard_pairs(groups):
    """Mine only frozen training similarities; other functions remain pseudo-negatives."""
    pairs = []
    for index, group in enumerate(groups):
        trainer.require(group.get('unit_kind') == 'source_function', 'Source-only mining required')
        positives = [i for i, row in enumerate(group['rows']) if row['relevance'] == 1]
        negatives = [i for i, row in enumerate(group['rows']) if row['relevance'] == 0]
        scores = group['codes'] @ group['query']
        negatives.sort(key=lambda i: (-float(scores[i]), group['rows'][i]['example_id']))
        pairs.extend((index, positive, negative) for positive in positives for negative in negatives[:8])
    trainer.require(bool(pairs), 'No source contrastive pairs')
    counts = Counter(groups[g]['key'][0] for g, _, _ in pairs)
    weights = [len(pairs) / (len(counts) * counts[groups[g]['key'][0]]) for g, _, _ in pairs]
    return pairs, weights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    for name in ('data', 'cache', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--frozen-sha256', required=True)
    parser.add_argument('--cache-sha256', required=True)
    args = parser.parse_args()
    trainer.PROTOCOL = {**trainer.PROTOCOL, **PROFILES[args.profile],
        'development_revision': args.profile, 'negative_policy': 'Eight highest frozen-base cosine training candidates; unjudged pseudo-negatives'}
    trainer.pair_table = hard_pairs
    bundle = trainer.load_source_bundle(args.data, args.frozen_sha256)
    bundle = replace(bundle, identity={**bundle.identity, 'development_revision': args.profile,
        'variant_implementation_sha256': trainer.sha(Path(__file__).read_bytes())})
    cache = trainer.load_embedding_cache(args.cache, args.cache_sha256, bundle)
    report = trainer.fit(bundle, cache, args.output)
    exported = trainer.export_projection(args.output / report['checkpoint'], report['checkpoint_manifest_sha256'], args.output / 'selected-inference')
    print(json.dumps({'profile': args.profile, 'selected_step': report['selected_step'],
        'development': report['development']['summary'], 'inference_manifest_sha256': exported}))


if __name__ == '__main__':
    main()
