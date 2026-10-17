"""Measured two-example resource pilot using the production training recipe."""
import argparse
import hashlib
import json
from pathlib import Path


def state_digest(value, tensor_type=()):
    """Hash training state without pickle or lossy tensor conversion."""
    from scripts.coding_train014 import encoded
    def represent(item):
        if isinstance(item, tensor_type):
            cpu = item.detach().cpu().contiguous()
            return {'tensor_dtype': str(cpu.dtype), 'shape': list(cpu.shape),
                    'sha256': hashlib.sha256(cpu.reshape(-1).view(__import__('torch').uint8).numpy().tobytes()).hexdigest()}
        if isinstance(item, dict):
            return {'dict': [[represent(key), represent(val)] for key, val in sorted(item.items(), key=lambda pair: (type(pair[0]).__name__, repr(pair[0])))]}
        if isinstance(item, (list, tuple)):
            return {type(item).__name__: [represent(val) for val in item]}
        if item is None or type(item) in (str, int, float, bool):
            return {type(item).__name__: item}
        raise ValueError('Unsupported checkpoint proof state type')
    return hashlib.sha256(encoded(represent(value))).hexdigest()


def prepare_resource_base(model, torch):
    """Freeze the NF4 base without upcasting its large embedding/head matrices.

    Normalization/bias vectors retain FP32. Quantized matrices keep their
    existing representation. This bounded recipe is measured by the real pilot,
    rather than assuming the PEFT default's additional FP32 allocation will fit.
    """
    for parameter in model.parameters():
        parameter.requires_grad=False
    visited=set()
    for module in (model.get_input_embeddings(),model.get_output_embeddings()):
        if module is None:continue
        for parameter in module.parameters():
            if id(parameter) in visited:continue
            visited.add(id(parameter))
            if parameter.dtype in (torch.float32,torch.bfloat16) and parameter.ndim>1:
                parameter.data=parameter.data.to(torch.float16)
    for parameter in model.parameters():
        if parameter.ndim==1 and parameter.dtype in (torch.float16,torch.bfloat16):
            parameter.data=parameter.data.to(torch.float32)
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    return model



def supervised_positions(labels):
    """Positions predicting unmasked causal targets; retain the full input sequence."""
    if not isinstance(labels, list) or len(labels) < 2 or labels[0] != -100:
        raise ValueError('A masked prompt and causal target are required')
    if any(type(value) is not int or (value < 0 and value != -100) for value in labels):
        raise ValueError('Invalid causal target label')
    positions = [index - 1 for index, value in enumerate(labels) if index and value != -100]
    if not positions:
        raise ValueError('At least one supervised causal target is required')
    return positions


class SupervisedLogitsCollator:
    """Avoid dense ignored-token logits using pinned Qwen2's public forward API.

    Labels stay intact for Trainer's gradient-accumulation token denominator.
    Explicit shift_labels preserve exactly the original next-token objective.
    Batch size one is part of this versioned resource recipe.
    """
    def __init__(self, collator):
        self.collator = collator

    def __call__(self, features):
        import torch
        batch = self.collator(features)
        labels = batch.get('labels')
        if (labels is None or labels.ndim != 2 or labels.shape[0] != 1
                or labels.dtype != torch.long or batch['input_ids'].shape != labels.shape):
            raise ValueError('Supervised logits require the frozen one-example causal batch')
        positions = torch.tensor(supervised_positions(labels[0].tolist()), dtype=torch.long, device=labels.device)
        return {**batch, 'logits_to_keep': positions,
                'shift_labels': labels[:, positions + 1].contiguous()}


def resource_identity(binding):
    # Input identity remains bound within each pilot run and its resumed run.
    # Transfer covers the fixed padded recipe, not unseen data or repair quality.
    return {key: value for key, value in binding.items()
            if key not in {'planned_steps', 'corpus_sha256', 'admission_index_sha256', 'study', 'max_supervised_tokens'}}


def inspect_pilot(root, manifest):
    from scripts.coding_train014 import read_bound, safe_path, sha_file, verify_checkpoint
    from scripts.coding_admission014 import require
    runs = {}
    for name, steps in [('full', 20), ('interrupted', 10), ('resumed', 20)]:
        item = manifest['runs'][name]
        receipt = read_bound(safe_path(root, item['receipt']), item['receipt_sha256'])
        binding = receipt['binding']
        require(receipt.get('version') == 'coding-training-run014-v1' and binding.get('study') == 'resource2'
                and binding.get('profile') == '14B' and binding.get('planned_steps') == 20
                and receipt.get('completed_steps') == steps and receipt.get('run_complete') is (steps == 20),
                'Incomplete or unrelated pilot stage')
        checkpoint = safe_path(root, item['checkpoint'])
        verify_checkpoint(checkpoint, item['checkpoint_receipt_sha256'], binding)
        proof = read_bound(checkpoint / 'resource-proof.json', item['proof_sha256'])
        state = json.loads((checkpoint / 'trainer_state.json').read_bytes())
        require(state.get('global_step') == steps and proof.get('step') == steps,
                'Pilot checkpoint step differs')
        require(set(proof) == {'step', 'adapter', 'optimizer', 'scheduler', 'rng'} and
                all(isinstance(proof[key], str) and len(proof[key]) == 64 for key in ('adapter', 'optimizer', 'scheduler', 'rng')),
                'Complete checkpoint state proof required')
        runs[name] = (receipt, proof)
    before, partial, after = (runs[name][0] for name in ('full', 'interrupted', 'resumed'))
    require(before['binding'] == partial['binding'] == after['binding'], 'Pilot dispatch identities differ')
    require(before.get('resumed_from_receipt_sha256') is None and partial.get('resumed_from_receipt_sha256') is None
            and after.get('resumed_from_receipt_sha256') == manifest['runs']['interrupted']['checkpoint_receipt_sha256'],
            'Resumed run does not bind the interrupted checkpoint')
    checks = {'resource_fit': before.get('resource_fit_verified') is True and after.get('resource_fit_verified') is True,
              'adapter_changed': before.get('adapter_updated') is True and after.get('adapter_updated') is True}
    for key in ('adapter', 'optimizer', 'scheduler', 'rng'):
        checks[key + '_equal'] = runs['full'][1][key] == runs['resumed'][1][key]
    return {'version': 'coding-resource-comparison014-v1', 'identity': resource_identity(before['binding']),
            'resource_corpus_sha256': before['binding']['corpus_sha256'], 'checks': checks,
            'passed': all(checks.values()), 'full_corpus_training_complete': False,
            'repair_effectiveness_verified': False,
            'max_supervised_tokens': before['binding'].get('max_supervised_tokens'),
            'scope': 'Measured padded recipe and checkpoint resume on two real examples, not a 100-example fit or repair improvement.'}


def verify_acceptance(path, expected_sha256, binding):
    from scripts.coding_train014 import read_bound
    from scripts.coding_admission014 import require
    manifest = read_bound(path, expected_sha256)
    require(manifest.get('version') == 'coding-resource-acceptance014-v1', 'Unknown resource pilot acceptance')
    actual = inspect_pilot(path.parent, manifest)
    if binding.get('loss_projection') == 'supervised-causal-positions-v1':
        requested=binding.get('max_supervised_tokens');measured=actual.get('max_supervised_tokens')
        require(type(requested) is int and type(measured) is int and 0 < requested <= measured,
                'Supervised-token memory demand exceeds the measured pilot coverage')
    require(actual['passed'] and manifest.get('comparison') == actual
            and actual['identity'] == resource_identity(binding), 'Measured recipe fit/resume acceptance differs')
    return actual


def main():
    from scripts.coding_train014 import sha_file
    from scripts.qualify014 import immutable
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    manifest = {'version': 'coding-resource-acceptance014-v1', 'runs': {}}
    for name, steps in [('full', 20), ('interrupted', 10), ('resumed', 20)]:
        folder = args.root / name; checkpoint = folder / ('checkpoint-' + str(steps))
        manifest['runs'][name] = {'receipt': str((folder / 'receipt.json').relative_to(args.root)),
            'receipt_sha256': sha_file(folder / 'receipt.json'), 'checkpoint': str(checkpoint.relative_to(args.root)),
            'checkpoint_receipt_sha256': sha_file(checkpoint / 'kairos-checkpoint.json'),
            'proof_sha256': sha_file(checkpoint / 'resource-proof.json')}
    manifest['comparison'] = inspect_pilot(args.root, manifest)
    immutable(args.root / 'resource-acceptance.json', manifest)
    print(json.dumps(manifest['comparison']))
    if not manifest['comparison']['passed']:
        raise SystemExit(1)


if __name__ == '__main__': main()
