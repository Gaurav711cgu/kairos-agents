"""Compile only complete, hash-bound public comparison captures for the website."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
from kairos_api.model_runtime import digest, canonical


def entry(raw, filename):
    if len(raw) > 1024 * 1024:
        raise ValueError('Public download exceeds existing bounded codec')
    return {'base64': base64.b64encode(raw).decode(), 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(), 'filename': filename,
        'media_type': 'text/x-diff' if filename.endswith('.patch') else 'application/json'}


def prepare(root):
    comparison = root/'evidence/measurement014/comparison'
    report_raw = (comparison/'report.json').read_bytes()
    report = json.loads(report_raw)
    if not report.get('execution_complete') or report.get('frozen_candidates') != 24:
        raise ValueError('Complete original frozen comparison required')
    qualification = root/'evidence/measurement014/qualification'
    catalog = {'root': {'attempts.json': entry(report_raw, 'attempts.json'),
        'receipt.json': entry((qualification/'index.json').read_bytes(), 'receipt.json')}}
    for case in report['cases']:
        for arm, result in case['arms'].items():
            if not result['record_sha256']:
                continue
            raw = (comparison/'records'/case['instance_id']/arm/'bundle.json').read_bytes()
            if hashlib.sha256(raw).hexdigest() != result['record_sha256']:
                raise ValueError('Original captured investigation digest differs')
            value = json.loads(raw)
            if value['task_id'] != case['instance_id'] or value['outcome'] != result['outcome']:
                raise ValueError('Capture differs from paired result')
            name = case['instance_id'] + '-' + arm
            files = {'bundle.json': entry(raw, 'bundle.json'),
                'receipt.json': entry((qualification/case['instance_id']/'receipt.json').read_bytes(), 'receipt.json')}
            proposals = [(s.get('result') or {}).get('body', {}).get('patch') for s in value['steps'] if s['name'] == 'propose_patch' and s['state'] == 'captured']
            proposals = [p for p in proposals if isinstance(p, str)]
            checks = [(s.get('result') or {}).get('body', {}) for s in value['steps'] if s['name'] == 'run_checks' and s['state'] == 'captured']
            winner = next((check for check in checks if check.get('passed') is True), None)
            selected = next((patch for patch in proposals if winner and digest(patch) == winner.get('patch_digest')), None)
            if result['verified'] and selected is None:
                raise ValueError('Verified verdict lacks a matching captured patch/check digest')
            patch = selected or (proposals[-1] if proposals else None)
            if patch:
                files['candidate.patch'] = entry(patch.encode(), 'candidate.patch')
            if checks:
                files['checks.json'] = entry(canonical(winner or checks[-1]).encode(), 'checks.json')
            catalog[name] = files
    path = root/'dashboard/lib'
    (path/'comparison014-report.json').write_bytes(report_raw)
    (path/'comparison014-downloads.json').write_text(json.dumps(catalog, sort_keys=True, separators=(',', ':'))+'\n')
    return {'captured_investigations': len(catalog)-1, 'attempts': report['attempts']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps(prepare(p.parse_args().root)))
