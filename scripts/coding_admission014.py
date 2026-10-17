"""Validate a frozen offline admission evidence graph without executing repository code.

Hashes establish byte identity, not truthful authorship or legal permission. Rights
and family decisions remain attributable reviews; captured checks establish only
registered verification outcomes, not resistance to adversarial test forgery.
"""
import base64
import binascii
import hashlib
import re

EXPOSURE_SHA256 = 'df992139ab624087f6141eb8401e78294ff6bcb203dfb76c3ab22e0bbfed6957'
ROW_REFERENCES = {'qualification', 'binding', 'baseline', 'reference', 'screen', 'image',
                  'preparation', 'example', 'rights', 'family'}


def issue_digest(issue):
    return hashlib.sha256(' '.join(str(issue).lower().split()).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_result(capture, stage, binding):
    """Decode the original streams; never trust a separate successful summary."""
    from scripts.qualify006 import summary
    require(capture.get('stage') == stage and capture.get('binding') == binding,
            'Check stage or experiment binding differs')
    result = capture['result']
    raw = result.get('raw_output', {})
    require(raw.get('complete') is True and raw.get('encoding') == 'base64', 'Complete raw capture required')
    restored = dict(result)
    for name in ('stdout', 'stderr'):
        stream = raw[name]
        try:
            data = base64.b64decode(stream['data'], validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError('Invalid raw stream encoding') from error
        require(len(data) <= 1024**2 and len(data) == stream['bytes'] == stream['observed_bytes']
                and stream.get('truncated') is False
                and hashlib.sha256(data).hexdigest() == stream['sha256'], 'Raw stream bytes differ')
        restored[name] = data.decode('utf-8', errors='replace')
    verdict = summary(restored)
    require(verdict and not verdict.get('collection_errors'), 'Missing or incomplete captured verdict')
    return restored, verdict


def verify_admission_bundle(corpus, directory, expected_index_sha256):
    """Require exact membership and semantic bindings for every training/dev row.

    Caller separately enforces corpus size, splits, source ranges and ActionV7.
    No framework import, CUDA allocation, Docker call or arbitrary code execution
    occurs here. Missing evidence fails before the training run creates output.
    """
    from scripts.coding_train014 import encoded, read_bound, safe_path
    from scripts.coding_verifier014 import qualifies
    from kairos_api.model_runtime import digest

    require(directory is not None and expected_index_sha256 is not None,
            'Admission directory and index hash are required')
    index = read_bound(directory / 'index.json', expected_index_sha256)
    require(index.get('version') == 'coding-admission-index014-v1', 'Unknown admission index')
    files = index['files']
    require(isinstance(files, dict) and 1 <= len(files) <= 5500, 'Admission file count exceeds bound')
    require(all(re.fullmatch(r'[a-f0-9]{64}', key) for key in files), 'Invalid evidence digest')
    require(len(set(files.values())) == len(files), 'Duplicate admission paths')
    # Bound total parsing as well as each individual file. Sources and weights do
    # not belong in this receipt-only package.
    paths = {key: safe_path(directory, name) for key, name in files.items()}
    require(all(path.is_file() for path in paths.values()), 'Admission evidence file missing')
    require(sum(path.stat().st_size for path in paths.values()) <= 256 * 1024**2,
            'Admission package exceeds 256MiB')
    documents = {key: read_bound(path, key, maximum=4 * 1024**2) for key, path in paths.items()}
    used = set()

    def load(key):
        require(key in documents, 'Referenced admission evidence missing')
        used.add(key)
        return documents[key]

    require(index.get('exposure_sha256') == corpus.get('exposure_inventory_sha256') == EXPOSURE_SHA256,
            'Frozen exposure inventory differs')
    exposure = load(EXPOSURE_SHA256)
    forbidden_ids = {entry['instance_id'] for entry in exposure['exposures']} | set(exposure['reserved014_ids'])
    forbidden_issues = set(exposure['exposed_issue_digests'])
    rows = [*corpus['train'], *corpus['development']]
    ids = [row['instance_id'] for row in rows]
    require(len(ids) == len(set(ids)) and set(index['rows']) == set(ids), 'Admission row membership differs')
    for row in rows:
        references = index['rows'][row['instance_id']]
        require(set(references) == ROW_REFERENCES, 'Incomplete admission row references')
        receipts = {name: load(key) for name, key in references.items()}
        qualification, binding = receipts['qualification'], receipts['binding']
        case, scope = binding['case'], binding['scope']
        identity = {key: row[key] for key in ('instance_id', 'repository', 'source_commit', 'source_digest')}
        issue_sha = issue_digest(row['input']['issue'])
        require(row['instance_id'] not in forbidden_ids and issue_sha not in forbidden_issues,
                'Exposed or reserved task leaked into training/development')
        require((case['dataset_instance_id'], case['repository'], case['revision'], case['source_digest'], case['issue'])
                == (row['instance_id'], row['repository'], row['source_commit'], row['source_digest'], row['input']['issue']),
                'Qualified task/source/issue differs from corpus')
        screen, image = receipts['screen'], receipts['image']
        entries = [entry for entry in screen['ledger'] if entry['instance_id'] == row['instance_id']]
        require(row['instance_id'] in screen['candidate_ids'] and len(entries) == 1, 'Task outside frozen candidates')
        entry = entries[0]
        require((entry['repository'], entry['base_commit'], entry['issue_sha256'])
                == (row['repository'], row['source_commit'], issue_sha), 'Frozen screen identity differs')
        bound = digest({'case': case, 'scope': scope, 'screen_sha256': references['screen'],
                        'image_receipt_sha256': references['image']})
        require(binding.get('version') == 'coding-qualification-binding014-v1' and binding.get('model_calls') == 0
                and binding.get('binding') == bound and image.get('id') == case['image'], 'Qualification binding differs')
        require(qualification.get('version') == 'coding-qualification014-v1'
                and qualification.get('qualified') is True and qualification.get('model_calls') == 0
                and qualification.get('original_source_unchanged') is True
                and qualification.get('instance_id') == row['instance_id']
                and qualification.get('binding') == bound and qualification.get('image') == case['image'],
                'Independent qualification required')
        require(qualification['checks_sha256'] == {name: references[name] for name in ('baseline', 'reference')},
                'Qualification capture hashes differ')
        require(scope.get('version') == 'coding-selected-suite014-v1' and scope.get('omissions') == []
                and bool(scope['regressions']) and not set(scope['regressions']) & set(scope['existing'])
                and sorted(set(scope['selected'])) == sorted(set(scope['regressions'] + scope['existing'])),
                'Incomplete selected test scope')
        results = {}
        for stage in ('baseline', 'reference'):
            result, verdict = raw_result(receipts[stage], stage, bound)
            require(verdict.get('existing_required') == len(scope['existing'])
                    and sorted(verdict.get('existing_passed', [])) == sorted(scope['existing'])
                    and verdict.get('collected') == verdict.get('tests_run'), 'Selected existing checks incomplete')
            if stage == 'reference':
                require(sorted(verdict.get('regression_passed', [])) == sorted(scope['regressions']),
                        'Reference regressions incomplete')
            else:
                failures = verdict.get('regression_failed', [])
                require(failures and all(any(node == test or node.startswith(test + '[')
                        for test in scope['regressions']) for node in failures), 'Unrelated baseline failure')
                require(all(test in verdict.get('regression_passed', []) or any(
                        node == test or node.startswith(test + '[') for node in failures)
                        for test in scope['regressions']), 'Baseline regression coverage incomplete')
            results[stage] = result
        require(qualifies(results['baseline'], results['reference']), 'Captured checks do not qualify')
        preparation, example = receipts['preparation'], receipts['example']
        require(preparation.get('version') == 'coding-action-preparation014-v1'
                and preparation.get('instance_id') == row['instance_id']
                and preparation.get('status') == 'converted_not_admitted'
                and preparation.get('source_unchanged') is True and preparation.get('model_calls') == 0
                and preparation.get('example_sha256') == references['example'], 'Successful action conversion required')
        require(example.get('version') == 'coding-action-example014-v1'
                and example.get('reference_derived_supervision') is True
                and example.get('qualification_receipt_sha256') == references['qualification']
                and all(example.get(key) == value for key, value in identity.items())
                and example.get('input') == row['input'] and example.get('assistant_target') == row['assistant_target'],
                'Converted example differs from admitted row')
        for name, value in (('input', row['input']), ('target', row['assistant_target'])):
            require(preparation.get(name + '_sha256') == hashlib.sha256(encoded(value)).hexdigest(),
                    'Converted input or target hash differs')
        require(re.fullmatch(r'[a-f0-9]{64}', str(preparation.get('rendered_patch_sha256', ''))),
                'Mechanical patch replay identity missing')
        for name in ('qualification', 'rights', 'family'):
            require(row.get(name + '_receipt_sha256') == references[name], 'Corpus receipt reference differs')
        for name in ('rights', 'family'):
            review = receipts[name]
            require(review.get('version') == 'coding-' + name + '-review014-v1'
                    and all(review.get(key) == value for key, value in identity.items())
                    and review.get('issue_sha256') == issue_sha
                    and all(isinstance(review.get(key), str) and review[key].strip()
                            for key in ('reviewer', 'reviewed_at')), 'Attributable task-bound review required')
        rights = receipts['rights']
        require(rights.get('approved_for_training') is True
                and set(rights.get('materials', {})) == {'source', 'issue', 'reference_patch'}, 'All material rights require review')
        require(all(isinstance(item.get(key), str) and item[key].strip()
                    for item in rights['materials'].values() for key in ('license', 'provenance', 'basis')),
                'Material-specific license, provenance and use basis required')
        family = receipts['family']
        require(family.get('family_id') == row['family_id'] and family.get('near_duplicate_reviewed') is True
                and all(isinstance(family.get(key), str) and family[key].strip() for key in ('method', 'rationale')),
                'Family and near-duplicate review required')
    require(used == set(files), 'Unreferenced admission evidence')
    return {'version': 'coding-admission-verification014-v1', 'verified_rows': len(rows),
            'admission_index_sha256': expected_index_sha256, 'verified_files': len(used),
            'scope': 'Offline captured-evidence validation; no new execution or legal attestation.'}
