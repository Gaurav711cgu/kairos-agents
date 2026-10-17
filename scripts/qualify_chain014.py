"""Extend pre-model dependency revisions while preserving exact receipt chains."""
from pathlib import Path
from scripts import qualify014 as q, qualify_revision014 as revision

ORIGINAL_POLICY = revision.image_policy
ORIGINAL_SELECTION = revision.selected_image
ORIGINAL_EXECUTE = q.execute_case
RETAIN_ENVIRONMENT = {}


def previous_chain(path, cohort):
    binding, plan, report = (q.load(path / n) for n in ['binding.json', 'plan.json', 'report.json'])
    expected = [(c['instance_id'], c['split']) for c in cohort['candidates']]
    if (report.get('binding') != binding['binding'] or plan.get('binding') != binding['binding']
            or report.get('model_calls') != 0 or report.get('execution_complete') is not True
            or [(c['instance_id'], c['split']) for c in report['candidates']] != expected):
        raise ValueError('Chain requires a complete, model-free, exact-cohort prior report')
    for intent in path.glob('cases/*/*.started.json'):
        if not intent.with_name(intent.name.replace('.started.json', '.json')).is_file():
            raise ValueError('Uncertain prior check cannot be retried')
    receipts = {}
    for entry in report['candidates']:
        target = path / 'cases' / entry['instance_id'] / 'receipt.json'
        receipt = q.load(target)
        if receipt['instance_id'] != entry['instance_id'] or receipt['status'] != entry['status'] or receipt.get('model_calls') != 0:
            raise ValueError('Prior terminal receipt differs from report')
        if receipt.get('binding') != binding['binding']:
            reuse = q.load(target.parent / 'reuse-provenance.json')
            if (reuse.get('revision_binding') != binding['binding'] or reuse.get('checks_rerun') != 0
                    or reuse.get('original_receipt_sha256') != q.sha(target)
                    or binding.get('prior_receipts_sha256', {}).get(entry['instance_id']) != q.sha(target)):
                raise ValueError('Reused receipt lacks exact bound preservation provenance')
        receipts[entry['instance_id']] = (target, receipt)
    return binding, plan, report, receipts


def copy_chain(path, destination, binding, roots):
    files = sorted(path.parent.glob('*.json'))
    q.storage_guard(roots, sum(p.stat().st_size for p in files))
    for source in files:
        name = source.name
        if name == 'reuse-provenance.json':
            name = 'prior-reuse-' + q.sha(source) + '.json'
        q.immutable(destination / name, q.load(source))
        if q.sha(source) != q.sha(destination / name):
            raise ValueError('Prior capture bytes changed')
    q.immutable(destination / 'reuse-provenance.json', {'revision_binding': binding,
        'original_receipt': str(path), 'original_receipt_sha256': q.sha(path), 'checks_rerun': 0})


def checked_policy(path):
    raw = q.load(path)
    addition = raw.get('pytest_dependency_revision')
    if addition:
        parent = revision.ORIGINAL_IMAGES['pytest-dev/pytest']
        proposed = raw['repositories']['pytest-dev/pytest']['*']
        if (addition.get('parent') != parent or addition.get('image') != proposed
                or proposed.get('tag') != 'kairos-investigation-pytest:metadata014'
                or set(addition.get('packages', {})) != {'importlib-metadata', 'zipp'}):
            raise ValueError('Only the reviewed additive legacy pytest dependency image is admitted')
        revision.ORIGINAL_IMAGES['pytest-dev/pytest'] = proposed
        try:
            policy = ORIGINAL_POLICY(path)
        finally:
            revision.ORIGINAL_IMAGES['pytest-dev/pytest'] = parent
    else:
        policy = ORIGINAL_POLICY(path)
    if policy.get('environment_chain_sha256') != q.sha(Path(__file__)):
        raise ValueError('Reviewed policy must bind this chain implementation')
    for identifier, item in policy.get('retained_qualified_cases', {}).items():
        receipt = Path(item['receipt'])
        if q.sha(receipt) != item['sha256'] or q.load(receipt).get('qualified') is not True:
            raise ValueError('Retained image must bind a captured qualified receipt')
        case = q.load(receipt.parent / 'case-definition.json')
        if case['id'] != identifier or case['image'] != item['image']['id']:
            raise ValueError('Retained qualified image differs from original case')
    RETAIN_ENVIRONMENT.clear()
    for identifier, item in policy.get('retained_environment_cases', {}).items():
        receipt = Path(item['receipt'])
        if q.sha(receipt) != item['sha256'] or q.load(receipt).get('status') != 'environment_failure' or not item.get('reason'):
            raise ValueError('Retained environment exclusion needs its exact failed receipt and reason')
        RETAIN_ENVIRONMENT[identifier] = item
    return policy


def retain_selected_image(policy, row):
    prior = policy.get('retained_qualified_cases', {}).get(row['instance_id']) or policy.get('retained_environment_cases', {}).get(row['instance_id'])
    return prior['image'] if prior else ORIGINAL_SELECTION(policy, row)


def execute_or_preserve(entry, row, out, roots, binding, allow_download, deps):
    retained = RETAIN_ENVIRONMENT.get(entry['instance_id'])
    if retained is None:
        return ORIGINAL_EXECUTE(entry, row, out, roots, binding, allow_download, deps)
    previous = Path(retained['receipt'])
    destination = out / 'cases' / entry['instance_id']
    copy_chain(previous, destination, binding, roots)
    q.immutable(destination / 'environment-retention.json', {'checks_rerun': 0, 'reason': retained['reason'], 'prior_receipt_sha256': q.sha(previous)})
    return {**q.load(previous), 'actual_revision_action': 'retain_environment_exclusion', 'retry_exclusion_reason': retained['reason']}


def main(argv=None):
    revision.VERSION = 'qualification014-environment-chain-v1'
    revision.previous_run = previous_chain
    revision.copy_receipt = copy_chain
    revision.image_policy = checked_policy
    revision.selected_image = retain_selected_image
    q.execute_case = execute_or_preserve
    return revision.main(argv)

if __name__ == '__main__':
    raise SystemExit(main())
