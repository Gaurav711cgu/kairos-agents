"""Publish independently captured qualification evidence without machine paths."""
from pathlib import Path
import argparse
import hashlib
import json
import re


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sanitized(value):
    """Redact only machine locations, preserving an explicit record of each change."""
    changes = []
    def visit(item, key):
        if isinstance(item, dict):
            return {k: visit(v, key + '/' + k) for k, v in item.items()}
        if isinstance(item, list):
            return [visit(v, key + '/' + str(i)) for i, v in enumerate(item)]
        if isinstance(item, str) and any(p in item for p in ['/Users/', '/private/tmp/', '/var/folders/']):
            changes.append(key)
            return '[Private machine location omitted; original bytes are retained locally.]'
        return item
    return visit(value, ''), changes


def export(qualification, study, study_sha256, output):
    if digest(study) != study_sha256:
        raise ValueError('Frozen study digest differs')
    frozen = json.loads(study.read_bytes())
    if digest(qualification / 'report.json') != frozen['qualification_report_sha256']:
        raise ValueError('Frozen qualification report differs')
    if output.exists():
        raise ValueError('Evidence export destination must be new')
    exports = {}; rows = []
    for item in frozen['cases']:
        identifier = item['instance_id']
        if not re.fullmatch(r'(django__django|pytest-dev__pytest)-[0-9]+', identifier):
            raise ValueError('Unregistered case identifier')
        folder = qualification / 'cases' / identifier
        receipt_path = folder / 'receipt.json'
        if digest(receipt_path) != item['qualification_receipt_sha256']:
            raise ValueError('Frozen case receipt differs')
        receipt = json.loads(receipt_path.read_bytes())
        if (receipt['instance_id'], receipt['split']) != (identifier, item['split']):
            raise ValueError('Frozen case identity differs')
        evidence = receipt['evidence_sha256']
        for name, sha in evidence.items():
            if Path(name).name != name or not re.fullmatch('[a-f0-9]{64}', sha) or digest(folder / name) != sha:
                raise ValueError('Qualification artifact digest differs')
        files = {}
        # Material manifests are intentionally retained privately: they contain
        # thousands of path/hash entries, not hidden test or reference bytes.
        for name in ['receipt.json', 'baseline.json', 'reference.json', 'source.json', 'case-definition.json', 'test-scope.json']:
            original = folder / name
            body, redactions = sanitized(json.loads(original.read_bytes()))
            raw = encode(body)
            if any(marker in raw for marker in [b'OPENAI_API_KEY=', b'GEMINI_API_KEY=', b'Bearer ', b'/Users/', b'/private/tmp/']):
                raise ValueError('Private material in public qualification export')
            logical = identifier + '/' + name
            exports[logical] = raw
            files[name] = {'original_sha256': digest(original), 'public_sha256': hashlib.sha256(raw).hexdigest(),
                'public_bytes': len(raw), 'redacted_json_pointers': redactions,
                'representation': 'Derived JSON; original capture remains retained privately'}
        rows.append({'instance_id': identifier, 'split': item['split'], 'status': receipt['status'],
            'qualified': receipt['qualified'], 'reason': receipt.get('reason'), 'files': files})
    report = {'version': 'qualification014-public-export-v1', 'study_sha256': study_sha256,
        'original_report_sha256': frozen['qualification_report_sha256'], 'cases': rows,
        'qualified': sum(row['qualified'] for row in rows), 'model_calls_during_qualification': 0,
        'scope': 'Derived public views with exact original digests. Complete raw check streams remain inside baseline/reference captures; machine locations are explicitly redacted.'}
    output.mkdir(parents=True)
    for name, raw in exports.items():
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    (output / 'index.json').write_bytes(encode(report))
    return {'candidates': len(rows), 'qualified': report['qualified'], 'files': len(exports)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['qualification', 'study', 'output']:
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--study-sha256', required=True)
    a = p.parse_args()
    print(json.dumps(export(a.qualification, a.study, a.study_sha256, a.output)))


if __name__ == '__main__':
    main()
