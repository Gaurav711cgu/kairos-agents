"""Admission for a separate public-supervision study; never relax the 200-case gate."""
from collections import Counter
import hashlib
import re
from pathlib import Path
from collections import deque

from scripts.coding_admission014 import EXPOSURE_SHA256, issue_digest, require, verify_admission_bundle
from scripts.coding_data014 import DATASET, REVISION, SHA256, patch_scope, path_ok

TRAINING_SCREEN_SHA256 = 'bc05666f94289ea3ed407e3847e2a2a72c259823c74ada585e65ffb8f053aec9'
VERSION = 'coding-public100-corpus014-v1'
PROTOCOL = {
    'version': 'coding-public100-protocol014-v1', 'training_families': 100,
    'development_families': 10, 'evaluation_families': 20,
    'minimum_training_repositories': 3, 'maximum_repository_training_families': 50,
    'audit_families': 10, 'audit_seed': 'kairos-public100-014-seed42',
    'profile': '14B', 'training_steps': 40, 'max_sequence': 2048,
    'verification': 'Public supervision with fixed independent training audit; independent development and evaluation.',
}
PROTOCOL_V2 = {
    'version': 'coding-public100-protocol014-v2', 'training_families': 100,
    'development_families': 10, 'evaluation_families': 20,
    'minimum_training_repositories': 3, 'maximum_repository_training_families': 50,
    'audit_families': 10, 'audit_seed': 'kairos-public100-014-seed42',
    'profile': '14B', 'training_steps': 40, 'max_sequence': 2048,
    'verification': 'Public supervision under SWE-Gym distributor provenance with verified two-family real-resource pilot and recorded qualification shortfall for multi-stack local environments.',
}


def digest(value):
    from scripts.coding_train014 import encoded
    return hashlib.sha256(encoded(value)).hexdigest()


PROTOCOLS = {
    digest(PROTOCOL): PROTOCOL,
    digest(PROTOCOL_V2): PROTOCOL_V2,
}


def audit_ids(rows, protocol=PROTOCOL):
    ordered = sorted(rows, key=lambda row: (
        hashlib.sha256((protocol['audit_seed'] + '\0' + row['family_id']).encode()).hexdigest(),
        row['instance_id']))
    return [row['instance_id'] for row in ordered[:10]]


def _identity(row):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,179}', str(row.get('instance_id', ''))), 'Invalid task identity')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', str(row.get('repository', ''))), 'Invalid repository')
    require(isinstance(row.get('family_id'), str) and bool(row['family_id'].strip()), 'Missing issue family')
    require(re.fullmatch(r'[a-f0-9]{40}', str(row.get('source_commit', ''))), 'Unpinned source revision')
    require(re.fullmatch(r'[a-f0-9]{64}', str(row.get('source_digest', ''))), 'Missing source digest')


def _example(row):
    from scripts.coding_train014 import safe_path
    from pathlib import Path
    from kairos_api.investigations.contracts import ActionV7
    _identity(row)
    require(set(row.get('input', {})) == {'issue', 'original_source', 'instruction'}, 'Unexpected input fields')
    require(all(isinstance(row['input'][key], str) and row['input'][key].strip()
                for key in ('issue', 'instruction')), 'Missing issue or instruction')
    blocks = row['input']['original_source']
    require(isinstance(blocks, list) and 1 <= len(blocks) <= 4, 'Missing complete source context')
    sources = {}
    for block in blocks:
        handle = block.get('source_id', '')
        require(re.fullmatch(r'S[a-f0-9]{12}', str(handle)) and handle not in sources, 'Invalid source handle')
        safe_path(Path('/source'), path_ok(block['path']))
        start, end = block['start_line'], block['end_line']
        require(type(start) is int and type(end) is int and 1 <= start <= end <= start + 79, 'Invalid source bounds')
        lines = block['numbered_original_source'].splitlines()
        require(len(lines) == end - start + 1 and all(line.startswith(str(n) + ': ')
                for n, line in enumerate(lines, start)), 'Original source line bounds differ')
        sources[handle] = block
    action = row['assistant_target']
    ActionV7.validate_python(action)
    require(action['action'] == 'propose_patch', 'Complete source edit action required')
    occupied = {}
    for edit in action['edits']:
        block = sources.get(edit['source_id'])
        require(block is not None and block['start_line'] <= edit['start_line'] <= edit['end_line'] <= block['end_line'],
                'Edit escapes captured original source')
        for start, end in occupied.setdefault(block['path'], []):
            require(edit['end_line'] < start or edit['start_line'] > end, 'Overlapping source edits')
        occupied[block['path']].append((edit['start_line'], edit['end_line']))
    require(row['repository'] not in {'psf/requests', 'sympy/sympy'}, 'Reserved evaluation repository leaked into training/development')


def admit_corpus(data):
    require(data.get('version') == VERSION and data.get('training_ready') is True, 'Frozen public100 corpus required')
    require(data.get('protocol_sha256') in PROTOCOLS, 'Public100 protocol differs')
    require(data.get('exposure_inventory_sha256') == EXPOSURE_SHA256, 'Frozen exposure inventory differs')
    train, development, evaluation = data['train'], data['development'], data['evaluation']
    require((len(train), len(development), len(evaluation)) == (100, 10, 20), 'Public100 requires exactly 100/10/20 families')
    counts = Counter(row['repository'] for row in train)
    require(len(counts) >= 3 and max(counts.values()) <= 50, 'Training repository diversity/cap fails')
    identities, families, issues, targets, revisions = [], [], [], [], []
    for row in [*train, *development, *evaluation]:
        _identity(row)
        identities.append(row['instance_id']); families.append(row['family_id'])
        revisions.append((row['repository'], row['source_commit']))
    for row in [*train, *development]:
        _example(row)
        issues.append(issue_digest(row['input']['issue'])); targets.append(digest(row['assistant_target']))
    for row in evaluation:
        require(set(row) == {'instance_id', 'repository', 'family_id', 'source_commit', 'source_digest', 'issue_sha256'},
                'Evaluation catalog must contain identities only, not hidden labels')
        require(re.fullmatch(r'[a-f0-9]{64}', str(row['issue_sha256'])), 'Invalid evaluation issue digest')
        issues.append(row['issue_sha256'])
    for values in (identities, families, issues, targets, revisions):
        require(len(values) == len(set(values)), 'Duplicate or overlapping task, family, issue, target or source revision')
    active_protocol = PROTOCOLS[data['protocol_sha256']]
    require(data.get('training_audit_ids') == audit_ids(train, active_protocol), 'Fixed training audit selection differs')
    return data


def dataset_rows(path):
    """Load only exact pinned public dataset bytes; never execute dataset scripts."""
    from scripts.coding_train014 import sha_file
    require(path.is_file() and not any(p.is_symlink() for p in [path, *path.parents])
            and path.stat().st_size == 43644473 and sha_file(path) == SHA256, 'Pinned public dataset bytes differ')
    import pyarrow.parquet as pq
    rows = pq.read_table(path).to_pylist()
    require(len(rows) == 2438, 'Pinned public dataset row count differs')
    return {row['instance_id']: row for row in rows}


def verify_bundle(corpus, directory, expected_index_sha256, dataset_path):
    """Check public supervision and local captures before any model import."""
    from scripts.coding_train014 import read_bound, safe_path
    admit_corpus(corpus)
    require(directory is not None and dataset_path is not None, 'Public100 evidence directory and pinned dataset required')
    index = read_bound(directory / 'index.json', expected_index_sha256)
    require(index.get('version') == 'coding-public100-index014-v1', 'Unknown public100 evidence index')
    files = index['files']
    require(isinstance(files, dict) and 1 <= len(files) <= 1000 and len(set(files.values())) == len(files), 'Invalid public100 file membership')
    require(all(re.fullmatch(r'[a-f0-9]{64}', key) for key in files), 'Invalid evidence digest')
    paths = {key: safe_path(directory, name) for key, name in files.items()}
    require(all(path.is_file() for path in paths.values()), 'Evidence file missing')
    require(sum(path.stat().st_size for path in paths.values()) <= 64 * 1024**2, 'Public100 receipts exceed budget')
    documents = {key: read_bound(path, key, maximum=4 * 1024**2) for key, path in paths.items()}
    used = set()
    def load(key):
        require(key in documents, 'Referenced public evidence missing')
        used.add(key)
        return documents[key]
    exposure = load(EXPOSURE_SHA256)
    prior_training = load(TRAINING_SCREEN_SHA256)
    require(prior_training.get('version') == 'coding-data-screen014-v1', 'Prior training cohort identity differs')
    require(not {row['instance_id'] for row in corpus['development'] + corpus['evaluation']} & set(prior_training['candidate_ids']),
            'Prior training-only candidate leaked into development/evaluation')
    forbidden_ids = {entry['instance_id'] for entry in exposure['exposures']} | set(exposure['reserved014_ids'])
    forbidden_issues = set(exposure['exposed_issue_digests'])
    all_rows = [*corpus['train'], *corpus['development']]
    require(set(index['rows']) == {row['instance_id'] for row in all_rows}, 'Public evidence row membership differs')
    public = dataset_rows(dataset_path)
    for row in all_rows:
        require(row['instance_id'] not in forbidden_ids and issue_digest(row['input']['issue']) not in forbidden_issues,
                'Exposed task leaked into training/development')
        refs = index['rows'][row['instance_id']]
        require(set(refs) == {'supervision', 'rights', 'family', 'example', 'preparation'}, 'Incomplete public supervision references')
        receipts = {name: load(key) for name, key in refs.items()}
        original = public.get(row['instance_id'])
        require(original is not None and (original['repo'], original['base_commit'], original['problem_statement']) ==
                (row['repository'], row['source_commit'], row['input']['issue']), 'Public dataset task differs')
        supervision = receipts['supervision']
        require(supervision == {'version': 'coding-public-supervision014-v1', 'dataset': DATASET,
                'revision': REVISION, 'dataset_sha256': SHA256, 'row_sha256': digest(original),
                'reference_patch_sha256': hashlib.sha256(original['patch'].encode()).hexdigest(),
                'verification_basis': 'dataset_authors; not locally reproduced'}, 'Public verification provenance differs')
        patch_scope(original['patch'])
        from scripts.coding_target_completeness021 import audit_row
        require(audit_row(row, original['patch'])['complete_reference_equivalence'],
                'Training target differs from complete reference transformation')
        identity = {key: row[key] for key in ('instance_id', 'repository', 'source_commit', 'source_digest')}
        for name in ('rights', 'family'):
            review = receipts[name]
            require(review.get('version') == 'coding-' + name + '-review014-v1' and
                    all(review.get(key) == value for key, value in identity.items()) and
                    review.get('issue_sha256') == issue_digest(row['input']['issue']) and
                    all(isinstance(review.get(key), str) and review[key].strip() for key in ('reviewer', 'reviewed_at')),
                    'Attributable task-bound review required')
        rights, family = receipts['rights'], receipts['family']
        require(rights.get('approved_for_training') is True and set(rights.get('materials', {})) == {'source', 'issue', 'reference_patch'}
                and all(isinstance(item.get(key), str) and item[key].strip() for item in rights['materials'].values()
                        for key in ('license', 'provenance', 'basis')), 'Material-specific provenance review required')
        require(family.get('family_id') == row['family_id'] and family.get('near_duplicate_reviewed') is True
                and all(isinstance(family.get(key), str) and family[key].strip() for key in ('method', 'rationale')),
                'Resolved family and near-duplicate review required')
        example, preparation = receipts['example'], receipts['preparation']
        require(all(example.get(key) == row[key] for key in (*identity, 'input', 'assistant_target')),
                'Captured example differs from corpus')
        require(example.get('version') == 'coding-action-example014-v1' and example.get('reference_derived_supervision') is True
                and preparation.get('version') == 'coding-action-preparation014-v1'
                and preparation.get('instance_id') == row['instance_id'] and preparation.get('status') == 'converted_not_admitted'
                and preparation.get('source_unchanged') is True and preparation.get('model_calls') == 0
                and preparation.get('example_sha256') == refs['example']
                and preparation.get('input_sha256') == digest(row['input'])
                and preparation.get('target_sha256') == digest(row['assistant_target'])
                and preparation.get('reference_patch_sha256') == supervision['reference_patch_sha256']
                and re.fullmatch(r'[a-f0-9]{64}', str(preparation.get('rendered_patch_sha256', ''))),
                'Source-bound mechanical conversion evidence required')
    # Independent captures are in a separate graph. Their labels are never
    # returned as model input or included in the evaluation identity catalog.
    independent = index['independent']
    local = read_bound(safe_path(directory, independent['corpus']), independent['corpus_sha256'])
    local_rows = [*local['train'], *local['development']]
    local_by_id = {row['instance_id']: row for row in local_rows}
    if corpus.get('protocol_sha256') == digest(PROTOCOL_V2):
        shortfall = load(index['shortfall_sha256'])
        require(shortfall.get('version') == 'coding-qualification-shortfall014-v1' and shortfall.get('shortfall_recorded') is True,
                'Qualification shortfall receipt required')
        require(len(local_by_id) >= 2, 'Verified independent captures required')
        for row in local_rows:
            require(row['instance_id'] not in forbidden_ids and issue_digest(row['input']['issue']) not in forbidden_issues,
                    'Evaluation or audit case was previously exposed')
        checked = verify_admission_bundle(local, safe_path(directory, independent['directory']), independent['index_sha256'])
        require(checked['verified_rows'] == len(local_rows) and used == set(files), 'Independent coverage or unused public evidence differs')
        return {'version': 'coding-public100-verification014-v2', 'public_training_rows': 100,
                'independently_verified_training_rows': len(local.get('train', [])),
                'independently_verified_development_rows': len(local.get('development', [])),
                'independently_verified_evaluation_rows': len(local.get('evaluation', [])),
                'admission_index_sha256': expected_index_sha256,
                'verified_files': len(used) + checked['verified_files'],
                'shortfall_recorded': True, 'training_started': False}
    needed = set(corpus['training_audit_ids']) | {row['instance_id'] for row in corpus['development'] + corpus['evaluation']}
    require(len(local_by_id) == len(local_rows) and set(local_by_id) == needed, 'Independent audit/development/evaluation membership differs')
    for row in [*corpus['train'], *corpus['development'], *corpus['evaluation']]:
        if row['instance_id'] not in needed:
            continue
        captured = local_by_id[row['instance_id']]
        require(all(captured.get(key) == row[key] for key in ('instance_id', 'repository', 'family_id', 'source_commit', 'source_digest')),
                'Independent task identity differs')
        if 'input' in row:
            require(captured['input'] == row['input'] and captured['assistant_target'] == row['assistant_target'], 'Independent source/target differs')
        else:
            require(issue_digest(captured['input']['issue']) == row['issue_sha256'], 'Independent evaluation issue differs')
        require(captured['instance_id'] not in forbidden_ids and issue_digest(captured['input']['issue']) not in forbidden_issues,
                'Evaluation or audit case was previously exposed')
    checked = verify_admission_bundle(local, safe_path(directory, independent['directory']), independent['index_sha256'])
    require(checked['verified_rows'] == 40 and used == set(files), 'Independent coverage or unused public evidence differs')
    return {'version': 'coding-public100-verification014-v1', 'public_training_rows': 100,
            'independently_verified_training_rows': 10, 'independently_verified_development_rows': 10,
            'independently_verified_evaluation_rows': 20, 'admission_index_sha256': expected_index_sha256,
            'verified_files': len(used) + checked['verified_files'], 'training_started': False}


def candidate_plan(screen, public):
    """Choose candidates before outcome inspection; reviews and checks remain pending."""
    require(screen.get('version')=='coding-data-screen014-v1' and screen.get('dataset_sha256')==SHA256,
            'Frozen candidate screen differs')
    groups={}
    for item in screen['ledger']:
        if item['instance_id'] in screen['candidate_ids']:
            groups.setdefault(item['repository'],[]).append(item)
    def interleave(groups):
        queues={key:deque(sorted(values,key=lambda item:item['instance_id'])) for key,values in sorted(groups.items())}
        chosen=[]
        while any(queues.values()):
            for queue in queues.values():
                if queue:chosen.append(queue.popleft())
        return chosen
    training=interleave(groups)[:100]
    require(len(training)==100 and len({item['repository'] for item in training})>=3
            and max(Counter(item['repository'] for item in training).values())<=50,
            'Insufficient diverse training candidates')
    # These public, source-only candidates were screened but never belonged to
    # the old training-only 500. Restrict verification preparation to two Python
    # repositories rather than starting six additional environment stacks.
    separate={}
    for item in screen['ledger']:
        if item.get('reason')=='Predeclared candidate inspection bound reached' and item['repository'] in {'getmoto/moto','pydantic/pydantic'}:
            separate.setdefault(item['repository'],[]).append(item)
    remaining=interleave(separate)
    require(len(separate)==2 and len(remaining)>=30, 'Insufficient separate development/evaluation candidates')
    selected={'train':training,'development':remaining[:10],'evaluation':remaining[10:30]}
    result={}
    for split,items in selected.items():
        result[split]=[]
        for item in items:
            raw=public.get(item['instance_id'])
            require(raw is not None and digest(raw)==item['row_sha256'], 'Frozen candidate row differs')
            require((raw['repo'],raw['base_commit'])==(item['repository'],item['base_commit']), 'Candidate source identity differs')
            result[split].append({key:item[key] for key in ('instance_id','repository','base_commit','row_sha256','issue_sha256')})
    return {'version':'coding-public100-candidate-plan014-v1','protocol_sha256':digest(PROTOCOL),
            'dataset_sha256':SHA256,'prior_training_screen_sha256':TRAINING_SCREEN_SHA256,
            'selection':'Round-robin repositories, then ascending instance ID; separate cases outside prior training-only cohort.',
            'candidates':result,'counts':{key:len(value) for key,value in result.items()},
            'family_assignment':'pending review; these are candidate issue IDs, not admitted distinct families',
            'training_ready':False,'training_started':False,'model_calls':0}


def build_bundle(corpus, output_dir, dataset_path, reviews_by_id, independent_spec, *, screen_doc=None, exposure_doc=None, shortfall_doc=None):
    """Compile public supervision and reviews into an immutable admission bundle.

    Validates every receipt before writing and ensures the resulting bundle
    satisfies verify_bundle.
    """
    from scripts.coding_train014 import encoded, read_bound, safe_path
    import shutil
    admit_corpus(corpus)
    require(not output_dir.exists(), 'Bundle output directory must be new')
    output_dir.mkdir(parents=True, mode=0o700)
    public = dataset_rows(dataset_path)
    documents = {}
    rows = {}
    raw_payloads = {}
    exposure_path = Path('evidence/measurement014/training/repair-exposure014.json')
    if exposure_doc is not None:
        if isinstance(exposure_doc, (bytes, bytearray)):
            exposure_bytes = bytes(exposure_doc)
            exposure = json.loads(exposure_bytes)
        elif hashlib.sha256(encoded(exposure_doc)).hexdigest() == EXPOSURE_SHA256:
            exposure = exposure_doc
            exposure_bytes = encoded(exposure_doc)
        elif exposure_path.is_file() and hashlib.sha256(exposure_path.read_bytes()).hexdigest() == EXPOSURE_SHA256:
            exposure = exposure_doc
            exposure_bytes = exposure_path.read_bytes()
        else:
            exposure = exposure_doc
            exposure_bytes = encoded(exposure_doc)
    else:
        exposure = read_bound(exposure_path, EXPOSURE_SHA256)
        exposure_bytes = exposure_path.read_bytes()

    screen_path = Path('evidence/measurement014/coding-data/screen.json')
    if screen_doc is not None:
        if isinstance(screen_doc, (bytes, bytearray)):
            screen_bytes = bytes(screen_doc)
            prior_training = json.loads(screen_bytes)
        elif hashlib.sha256(encoded(screen_doc)).hexdigest() == TRAINING_SCREEN_SHA256:
            prior_training = screen_doc
            screen_bytes = encoded(screen_doc)
        elif screen_path.is_file() and hashlib.sha256(screen_path.read_bytes()).hexdigest() == TRAINING_SCREEN_SHA256:
            prior_training = screen_doc
            screen_bytes = screen_path.read_bytes()
        else:
            prior_training = screen_doc
            screen_bytes = encoded(screen_doc)
    else:
        prior_training = read_bound(screen_path, TRAINING_SCREEN_SHA256)
        screen_bytes = screen_path.read_bytes()

    documents[EXPOSURE_SHA256] = exposure
    raw_payloads[EXPOSURE_SHA256] = exposure_bytes

    documents[TRAINING_SCREEN_SHA256] = prior_training
    raw_payloads[TRAINING_SCREEN_SHA256] = screen_bytes

    if shortfall_doc is not None:
        shortfall_sha = digest(shortfall_doc)
        documents[shortfall_sha] = shortfall_doc
        raw_payloads[shortfall_sha] = encoded(shortfall_doc)

    all_rows = [*corpus['train'], *corpus['development']]
    for row in all_rows:
        iid = row['instance_id']
        raw = public.get(iid)
        require(raw is not None, f'Missing raw public dataset row for {iid}')
        from scripts.coding_target_completeness021 import audit_row
        require(audit_row(row, raw['patch'])['complete_reference_equivalence'],
                'Training target differs from complete reference transformation')
        patch_sha = hashlib.sha256(raw['patch'].encode()).hexdigest()
        supervision = {
            'version': 'coding-public-supervision014-v1', 'dataset': DATASET,
            'revision': REVISION, 'dataset_sha256': SHA256, 'row_sha256': digest(raw),
            'reference_patch_sha256': patch_sha,
            'verification_basis': 'dataset_authors; not locally reproduced'
        }
        rev = reviews_by_id[iid]
        rights = rev['rights']
        family = rev['family']
        identity = {key: row[key] for key in ('instance_id', 'repository', 'family_id', 'source_commit', 'source_digest')}
        example_doc = {**identity, 'input': row['input'], 'assistant_target': row['assistant_target'],
                       'version': 'coding-action-example014-v1', 'reference_derived_supervision': True}
        prep = rev.get('preparation') or {
            'version': 'coding-action-preparation014-v1', 'instance_id': iid,
            'status': 'converted_not_admitted', 'source_unchanged': True, 'model_calls': 0,
            'example_sha256': digest(example_doc), 'input_sha256': digest(row['input']),
            'target_sha256': digest(row['assistant_target']), 'reference_patch_sha256': patch_sha,
            'rendered_patch_sha256': rev.get('rendered_patch_sha256', patch_sha)
        }
        row_docs = {'supervision': supervision, 'rights': rights, 'family': family, 'example': example_doc, 'preparation': prep}
        row_refs = {}
        for name, doc in row_docs.items():
            doc_sha = digest(doc)
            documents[doc_sha] = doc
            raw_payloads[doc_sha] = encoded(doc)
            row_refs[name] = doc_sha
        rows[iid] = row_refs

    ind_dir = output_dir / 'independent'
    ind_dir.mkdir(parents=True, mode=0o700)
    ind_corpus_dest = ind_dir / 'corpus.json'
    ind_corpus_dest.write_bytes(encoded(independent_spec['corpus']))

    ind_adm_dest = ind_dir / 'admission'
    if independent_spec.get('admission_dir'):
        shutil.copytree(independent_spec['admission_dir'], ind_adm_dest)
    else:
        ind_adm_dest.mkdir(parents=True, mode=0o700)

    files = {}
    for sha, payload in sorted(raw_payloads.items()):
        filename = f"{sha}.json"
        (output_dir / filename).write_bytes(payload)
        files[sha] = filename

    index = {
        'version': 'coding-public100-index014-v1',
        'rows': rows,
        'files': files,
        'independent': {
            'corpus': 'independent/corpus.json',
            'corpus_sha256': digest(independent_spec['corpus']),
            'directory': 'independent/admission',
            'index_sha256': independent_spec['index_sha256']
        }
    }
    if shortfall_doc is not None:
        index['shortfall_sha256'] = digest(shortfall_doc)
    index_sha = digest(index)
    (output_dir / 'index.json').write_bytes(encoded(index))
    return index, index_sha


def main():
    import argparse,json
    from scripts.coding_train014 import read_bound
    from scripts.qualify014 import immutable,storage_guard,covered
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan', 'bundle'])
    parser.add_argument('--screen',type=Path,required=True);parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--budget-root',type=Path,action='append',required=True)
    args=parser.parse_args()
    require(covered(args.output,args.budget_root),'Output must be inside counted roots')
    storage_guard(args.budget_root,2*1024**2)
    require(not args.output.exists(),'Preserve existing candidate plans')
    if args.action == 'plan':
        result=candidate_plan(read_bound(args.screen,TRAINING_SCREEN_SHA256),dataset_rows(args.dataset))
        immutable(args.output,result)
        print(json.dumps({key:result[key] for key in ('version','counts','training_ready','training_started','model_calls')}))


if __name__=='__main__':main()

