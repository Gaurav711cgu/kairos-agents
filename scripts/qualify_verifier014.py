"""Apply a measured unittest-capture correction before any fresh model dispatch."""
from pathlib import Path
import sys
import re
from scripts import qualify014 as q, qualify_chain014 as chain, qualify006, verifier_unittest014


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    policy_path = Path(argv[argv.index('--image-policy') + 1])
    previous = Path(argv[argv.index('--previous') + 1])
    policy = q.load(policy_path)
    revision = policy.get('verifier_revision', {})
    if (revision.get('implementation_sha256') != q.sha(Path(__file__))
            or revision.get('generator_sha256') != q.sha(Path(verifier_unittest014.__file__))
            or revision.get('protocol') != verifier_unittest014.VERSION):
        raise ValueError('Reviewed policy must bind the exact structured verifier correction')
    identifiers = revision.get('candidate_ids', [])
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError('Explicit distinct verifier-correction case IDs required')
    for identifier in identifiers:
        evidence = previous / 'cases' / identifier
        receipt = q.load(evidence / 'receipt.json')
        reference = q.load(evidence / 'reference.json')['result']
        from scripts.comparison014 import raw_complete014
        final_ok = (raw_complete014(reference) and receipt.get('reference_summary', {}).get('tests_run', 0) > 0
            and bool(re.search(r'^OK(?:\s+\([^\n]*\))?$', reference['stderr'], re.MULTILINE)))
        if (not identifier.startswith('django__django-') or receipt.get('status') != 'environment_failure'
                or receipt.get('baseline_summary', {}).get('tests_run', 0) <= 0
                or receipt['baseline_summary'].get('execution_complete') is not False
                or not (receipt.get('reference_complete_pass') is True or final_ok)):
            raise ValueError('Only captured incomplete unittest baseline reporting with a passing reference is eligible')
    original = qualify006.verifier
    def corrected(row, source):
        return verifier_unittest014.verifier(row, source) if row['instance_id'] in identifiers else original(row, source)
    qualify006.verifier = corrected
    return chain.main(argv)

if __name__ == '__main__':
    raise SystemExit(main())
