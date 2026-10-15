"""Verify the development-evidence overlay and every preserved parent seal."""
from pathlib import Path
import argparse
import json

from scripts.package_release007 import fingerprint, inventory, read_json, validate_entries
from scripts.verify_loop012 import inherited_inventory, MANIFEST as PARENT_MANIFEST, PARENT_COMMIT as RETRIEVAL_COMMIT
from scripts.verify_retrieval011 import MANIFEST as RETRIEVAL_MANIFEST
from scripts.verify_showcase008 import METADATA

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='evidence/evaluation013/manifest.json'
PARENT_COMMIT='4f487000d5d6d92c10c4b08589d4dbf9644816ae'
ALLOWED={'README.md','BRAIN.md','DECISIONS.md','.github/workflows/regression-gate.yml',
    'scripts/acceptance007.py','scripts/study010.py','scripts/pilot013.py','scripts/export_pilot013.py',
    'scripts/cohort013.py','scripts/repair_report013.py','scripts/training_bundle013.py',
    'scripts/verify_evaluation013.py','scripts/audit_training013.py',
    'tests/test_pilot013.py','tests/test_cohort013.py','tests/test_export_pilot013.py',
    'tests/test_repair_report013.py','tests/test_training_bundle013.py','tests/test_verify_evaluation013.py',
    'tests/test_audit_training013.py','dashboard/app/repair-investigation/page.tsx',
    'dashboard/app/api/pilot013/[...path]/route.ts','dashboard/app/repair-workflow/page.tsx',
    'dashboard/app/page.tsx','dashboard/app/how-it-works/page.tsx',
    'dashboard/lib/repair010-downloads.ts','dashboard/lib/repair010-downloads.test.mjs',
    'dashboard/lib/pilot013-summary.json','dashboard/lib/pilot013-bundle.json','dashboard/lib/pilot013-downloads.json',
    'dashboard/e2e/pilot013.spec.ts','dashboard/playwright.recorded.config.ts',
    'docs/EVALUATION_013.md','docs/DELIVERY_PLAN_013.md','docs/TRAINING_PREPARATION_013.md',
    'docs/REPAIR_REPORTING_013.md','docs/CLOUD_TRAINING_013.md','notebooks/training-preflight013.ipynb'}


def allowed(name):
    return name in ALLOWED or name.startswith('evidence/evaluation013/') and Path(name).suffix in {'.json','.md','.patch','.png'}


def parent_inventory(root):
    base=inherited_inventory(root)
    parent=read_json(root/PARENT_MANIFEST)
    if (parent.get('version')!='loop012-phase2-v1' or parent.get('parent_commit')!=RETRIEVAL_COMMIT
            or parent.get('parent_manifest')!=fingerprint(root/RETRIEVAL_MANIFEST)):
        raise ValueError('Preserved loop012 ancestry differs')
    return {**base,**validate_entries(parent['files'])}


def verify_delta(actual,inherited,changes):
    changes=validate_entries(changes)
    if MANIFEST in changes or any(not allowed(name) for name in changes):
        raise ValueError('Undeclared evaluation source path')
    if actual!={**inherited,**changes}:
        raise ValueError('Active source differs from the sealed evaluation phase')


def verify(root):
    root=Path(root).resolve(strict=True);value=read_json(root/MANIFEST)
    if value.get('version')!='evaluation013-v1' or value.get('parent_commit')!=PARENT_COMMIT:
        raise ValueError('Unknown evaluation phase identity')
    if value.get('parent_manifest')!=fingerprint(root/PARENT_MANIFEST):
        raise ValueError('Preserved loop012 manifest differs')
    excluded={*METADATA,'evidence/ci009/manifest.json','evidence/repair010/manifest.json',
              RETRIEVAL_MANIFEST,PARENT_MANIFEST,MANIFEST}
    actual={name:row for name,row in inventory(root).items() if name not in excluded}
    verify_delta(actual,parent_inventory(root),value['files'])
    return {'passed':True,'phase':'evaluation013','files':len(value['files']),
            'historical_seals_and_archive_verified':True,
            'scope':'Exact source and capture bindings; held-out qualification and cloud training require separate results'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    try:result=verify(args.root)
    except (ValueError,OSError,KeyError,TypeError) as error:parser.exit(1,'Evaluation seal failed: '+str(error)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()
