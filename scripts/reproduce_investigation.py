"""Recheck one recorded candidate in a fresh source copy and disposable container."""
import argparse
import json
import subprocess
from pathlib import Path
from kairos_api.investigations.registry import CaseRegistry
from kairos_api.investigations.sandbox import Workspace
from kairos_api.model_runtime import digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',required=True);parser.add_argument('--output',required=True);parser.add_argument('--image',help='Explicit reviewed replacement image for a fresh-machine reproduction, recorded as an environment change');args=parser.parse_args()
    record=json.loads(Path(args.record).read_text())
    registry=CaseRegistry();case=registry.get(record['task_id'])
    if registry.fingerprint(case)!=record['task_digest']:
        current={k:v for k,v in case.items() if k!='image'}
        frozen={k:v for k,v in record['task_snapshot'].items() if k!='image'}
        if not args.image or current!=frozen: raise ValueError('Recorded case differs from frozen registry; only an explicit image replacement is supported')
    case=dict(case)
    if args.image:
        case['image']=subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
        if not case['image'].startswith('sha256:'): raise ValueError('Replacement image has no immutable identifier')
    patches=[s for s in record['steps'] if s['name']=='propose_patch' and s['state']=='captured' and 'error' not in s['result']['body']]
    if not patches: raise ValueError('This attempt contains no accepted patch; inspect its recorded rejection instead')
    selection=next((s['result']['body'] for s in record['steps'] if s['name']=='draft_selection' and s['state']=='captured'),{})
    last=next((s for s in reversed(patches) if not selection.get('selected_patch_digest') or digest(s['result']['body'].get('patch',''))==selection['selected_patch_digest']),patches[-1]);patch=last['result']['body'].get('patch',last['request']['body'].get('patch',''))
    workspace=Workspace(registry,case)
    try:
        workspace.propose(patch);result=workspace.checks()
        expected=record['outcome']=='verified_repair'
        output={'task_id':case['id'],'record_id':record['id'],'source_digest':case['source_digest'],'patch_digest':digest(patch),
                'recorded_image':record['task_snapshot']['image'],'reproduction_image':case['image'],
                'environment_changed':case['image']!=record['task_snapshot']['image'],
                'mode':'Fresh source copy and disposable network-disabled container; no model or database call',
                'checks':result,'recorded_repair_verified':expected,'outcome_reproduced':bool(result['passed'])==expected}
        Path(args.output).write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
        if not output['outcome_reproduced']: raise SystemExit(1)
    finally: workspace.close()

if __name__=='__main__': main()
