"""Verify an inference-only export before accepting any captured generation.

This importer performs no model or test execution and never grades a repair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def verify(archive_path, prompts_path, expected_archive_sha, expected_runner_sha):
    archive_path, prompts_path = Path(archive_path), Path(prompts_path)
    if archive_path.is_symlink() or archive_path.stat().st_size > 4 * 1024**2:
        raise ValueError('Invalid or oversized archive')
    archive_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if archive_sha != expected_archive_sha:
        raise ValueError('Archive differs from Colab export receipt')
    prompts_raw = prompts_path.read_bytes()
    prompts = unique_json(prompts_raw)
    case_ids = [case['instance_id'] for case in prompts['cases']]
    if len(case_ids) != 12 or len(set(case_ids)) != 12:
        raise ValueError('Frozen case membership differs')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if (len(names) != len(set(names)) or 'manifest.json' not in names
                or any('/' in name or '\\' in name or not name.endswith('.json') for name in names)
                or sum(info.file_size for info in archive.infolist()) > 4 * 1024**2
                or any(info.flag_bits & 1 for info in archive.infolist())):
            raise ValueError('Unsafe or oversized archive membership')
        manifest = unique_json(archive.read('manifest.json'))
        if (manifest.get('version') != 'coding-inference-export020-v1'
                or manifest.get('contains_model_weights') is not False
                or manifest.get('training_runs') != 0
                or manifest.get('repair_verification_complete') is not False
                or set(names) != set(manifest['files']) | {'manifest.json'}):
            raise ValueError('Unexpected export manifest')
        files = {}
        for name, item in manifest['files'].items():
            raw = archive.read(name)
            if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Manifest hash differs: ' + name)
            files[name] = unique_json(raw)
    result, binding = files['generations.json'], files['binding.json']
    if (binding.get('prompts_sha256') != hashlib.sha256(prompts_raw).hexdigest()
            or binding.get('runner_sha256') != expected_runner_sha
            or binding.get('adapter_sha256') != prompts['adapter_files']['adapter_model.safetensors']['sha256']
            or binding.get('model_revision') != prompts['base_revision']
            or binding.get('generation') != prompts['generation']
            or binding.get('training_runs') != 0 or result.get('binding') != binding
            or result.get('version') != 'coding-generation-results020-v1'
            or result.get('training_runs') != 0 or result.get('inference_complete') is not True
            or result.get('repair_verification_complete') is not False):
        raise ValueError('Frozen inference binding differs')
    binding_sha = hashlib.sha256(canonical(binding)).hexdigest()
    expected_names = {'binding.json', 'generations.json'}
    expected_pairs = {(identifier, arm) for identifier in case_ids for arm in ['base', 'adapter']}
    seen = set()
    calls = 0
    contexts = {case['instance_id']: case for case in prompts['cases']}
    for record in result['records']:
        pair = record['instance_id'], record['arm']
        if pair not in expected_pairs or pair in seen:
            raise ValueError('Unexpected or duplicate arm/case')
        seen.add(pair)
        stem = '.'.join(pair)
        expected_names.add(stem + '.json')
        if files.get(stem + '.json') != record:
            raise ValueError('Aggregate capture differs')
        unsigned = {key: value for key, value in record.items() if key != 'capture_sha256'}
        if (record.get('capture_sha256') != hashlib.sha256(canonical(unsigned)).hexdigest()
                or record.get('binding_sha256') != binding_sha
                or record.get('verified_repair') is not None
                or record.get('verification_complete') is not False
                or type(record.get('model_calls')) is not int
                or record['model_calls'] not in [0, 1]):
            raise ValueError('Invalid capture integrity or premature grading')
        case = contexts[pair[0]]
        if record['model_calls']:
            calls += 1
            expected_names.add(stem + '.intent.json')
            intent = files[stem + '.intent.json']
            if (intent.get('binding_sha256') != binding_sha
                    or intent.get('instance_id') != pair[0] or intent.get('arm') != pair[1]
                    or intent.get('prompt_sha256') != hashlib.sha256(canonical(case['messages'])).hexdigest()
                    or not case['context_available']
                    or record['status'] not in ['captured', 'inference_error']):
                raise ValueError('Dispatch intent differs')
            if record['status'] == 'captured':
                tokens = record['output_token_ids']
                if (not isinstance(record['text'], str) or len(record['text'].encode()) > 128 * 1024
                        or not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens)
                        or len(tokens) != record['output_tokens'] or len(tokens) > 1024
                        or record['input_tokens'] + len(tokens) > 4096):
                    raise ValueError('Invalid generation dimensions')
        elif record['status'] != 'unavailable':
            raise ValueError('Zero-dispatch record must remain unavailable')
    if seen != expected_pairs or set(files) != expected_names or calls > 18:
        raise ValueError('Incomplete or extra captures')
    return {'version': 'inference-import020-v1', 'archive_sha256': archive_sha,
            'manifest_members_verified': len(manifest['files']), 'cases': 12,
            'model_calls': calls, 'training_runs': 0, 'repair_verification_complete': False,
            'records': result['records'], 'binding': binding}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--prompts', type=Path, required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--runner-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.archive, args.prompts, args.archive_sha256, args.runner_sha256)
    with args.output.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
    print(json.dumps({key: value[key] for key in ['manifest_members_verified', 'cases', 'model_calls', 'repair_verification_complete']}))
