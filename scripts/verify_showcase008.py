"""Verify declared delivery changes against the preserved build007 source seal."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.package_release007 import (fingerprint, inventory, read_json, safe_name,
                                       verify_archive, _resolved_file)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = 'evidence/docs008'
METADATA = {OUTPUT+'/manifest.json', OUTPUT+'/receipt.json'}


ALLOWED_SOURCE_CHANGES = frozenset({
    '.gitignore',
    'BRAIN.md',
    'DECISIONS.md',
    'README.md',
    'dashboard/app/advancement/page.tsx',
    'dashboard/app/capacity/page.tsx',
    'dashboard/app/docs/page.tsx',
    'dashboard/app/engineering/page.tsx',
    'dashboard/app/how-it-works/page.tsx',
    'dashboard/app/investigations.css',
    'dashboard/app/investigations/page.tsx',
    'dashboard/app/layout.tsx',
    'dashboard/app/page.tsx',
    'dashboard/app/workbench/page.tsx',
    'dashboard/components/InvestigationInspector.tsx',
    'dashboard/e2e/public.spec.ts',
    'dashboard/e2e/reviewer-execution.spec.ts',
    'dashboard/e2e/reviewer-public.spec.ts',
    'dashboard/eslint.config.mjs',
    'dashboard/playwright.execution.config.ts',
    'dashboard/public/live-workflow/receipt.json',
    'scripts/reviewer.py',
    'scripts/reviewer_inference.py',
    'scripts/reviewer_runtime.py',
    'scripts/study007_runtime.py',
    'scripts/verify_reviewer005.py',
    'scripts/verify_showcase008.py',
    'tests/test_reviewer_inference.py',
})


def allowed(name):
    return name in ALLOWED_SOURCE_CHANGES or name.startswith("docs/showcase/") or name.startswith(OUTPUT+"/")


def verify(root):
    root=Path(root).resolve(strict=True)
    manifest_path=root/OUTPUT/'manifest.json'
    overlay=read_json(manifest_path)
    receipt=read_json(root/OUTPUT/'receipt.json')
    if (overlay.get('version')!='showcase-delivery008-v1' or receipt.get('passed') is not True
            or receipt.get('manifest')!=fingerprint(manifest_path)):
        raise ValueError('Delivery manifest binding differs')
    base=read_json(root/'evidence/build007/manifest.json')
    base_receipt=read_json(root/'evidence/build007/publication-receipt.json')
    index=read_json(root/'evidence/build007/publication-index.json')
    actual_bindings={name:fingerprint(root/('evidence/build007/'+name))
                     for name in ('manifest.json','publication.tar.gz','publication-index.json','publication-receipt.json')}
    if overlay.get('preserved_build007')!=actual_bindings:
        raise ValueError('Preserved build007 publication bytes differ')
    if (base_receipt.get('archive')!=actual_bindings['publication.tar.gz']
            or base_receipt.get('manifest')!=actual_bindings['manifest.json']
            or base_receipt.get('index')!=actual_bindings['publication-index.json']
            or index.get('archive')!=actual_bindings['publication.tar.gz']
            or index.get('manifest')!=actual_bindings['manifest.json']):
        raise ValueError('Original publication bindings differ')
    expected=dict(base['files'])
    files=overlay.get('files')
    if not isinstance(files,dict) or not files:
        raise ValueError('Delivery overlay is empty')
    for name,value in files.items():
        safe_name(name)
        if name in METADATA or not allowed(name):
            raise ValueError('Undeclared executable or private path in delivery overlay')
        if fingerprint(_resolved_file(root,name))!=value:
            raise ValueError('Delivery file differs: '+name)
        expected[name]=value
    actual={name:value for name,value in inventory(root).items() if name not in METADATA}
    if actual!=expected:
        raise ValueError('Active source differs outside the declared delivery overlay')
    verify_archive(root/'evidence/build007/publication.tar.gz',
                   {**base['files'],'evidence/build007/manifest.json':actual_bindings['manifest.json']})
    return {'passed':True,'delivery_files':len(files),'base_source_files':len(base['files']),
            'api_worker_and_frozen_study_evidence_unchanged':True,'original_build007_archive_verified':True,
            'delivery_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'acceptance_and_live_execution_have_separate_receipts':True,
            'scope':'Byte consistency relative to trusted local receipts; no signature or production certification'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--publication',action='store_true',help='Also verify the separate delivery publication archive')
    args=parser.parse_args()
    try:
        result=verify(args.root)
        if args.publication:
            publication=read_json(args.root/OUTPUT/'publication-receipt.json')
            package=args.root/OUTPUT/'publication.tar.gz'
            manifest=args.root/OUTPUT/'manifest.json'
            receipt=args.root/OUTPUT/'receipt.json'
            if (publication.get('passed') is not True or publication.get('archive')!=fingerprint(package)
                    or publication.get('manifest')!=fingerprint(manifest)
                    or publication.get('source_receipt')!=fingerprint(receipt)):
                raise ValueError('Delivery publication binding differs')
            overlay=read_json(manifest);base=read_json(args.root/'evidence/build007/manifest.json')
            members={**base['files'],**overlay['files'],OUTPUT+'/manifest.json':fingerprint(manifest),
                     OUTPUT+'/receipt.json':fingerprint(receipt)}
            members.update({'evidence/build007/'+name:value for name,value in overlay['preserved_build007'].items()})
            verify_archive(package,members)
            result['delivery_publication_archive_verified']=True
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(1,'Delivery verification failed: '+(str(error) if isinstance(error,ValueError) else type(error).__name__)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
