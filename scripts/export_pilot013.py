"""Export reviewed development captures; never execute or replace a model result."""
from pathlib import Path
import argparse
import base64
import hashlib
import json

from kairos_api.model_runtime import canonical
from scripts.study010 import report010
from scripts.repair012.retrieval_loop012 import VERSION


def raw_json(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode()


def package(runtime):
    runtime = Path(runtime).resolve(strict=True)
    report = report010(runtime, expected_version=VERSION)
    record = json.loads((runtime/'record.json').read_bytes())
    receipt = json.loads((runtime/'result.json').read_bytes())
    experiment = json.loads((runtime/'experiment.json').read_bytes())
    if (record.get('status') != 'completed' or record.get('outcome') != 'verified_repair'
            or record.get('task_snapshot',{}).get('split') != 'development'
            or not record.get('integrity',{}).get('verified')
            or not report.get('source_unchanged') or report.get('failure') or report.get('cleanup_errors')):
        raise ValueError('A completed, source-isolated development repair is required for this showcase')
    sequences = [step['seq'] for step in record['steps']]
    if sequences != list(range(1,len(sequences)+1)):
        raise ValueError('Ordered captures are incomplete')
    for step in record['steps']:
        if step['state'] != 'captured' or not step.get('result'):
            raise ValueError('The complete captured sequence is required')
        for capture in (step['request'],step['result']):
            raw = (runtime/'blobs'/capture['sha256']).read_bytes()
            if (hashlib.sha256(raw).hexdigest()!=capture['sha256']
                    or raw != canonical(capture['body']).encode()):
                raise ValueError('Original captured artifact differs')
    patch = next(step for step in reversed(record['steps']) if step['name']=='propose_patch')
    check = next(step for step in reversed(record['steps']) if step['name']=='run_checks')
    selection = next(step for step in record['steps'] if step['name']=='retrieval_selection012')
    if not check['result']['body'].get('passed') or not check['result']['body'].get('verification_complete'):
        raise ValueError('Complete independent checks must pass')
    sources = selection['result']['body']['observations']
    usage = [step['result']['body'].get('usage') for step in record['steps'] if step['kind']=='model']
    def tokens(field):
        values = [item.get(field) if isinstance(item,dict) else None for item in usage]
        return sum(values) if all(type(v)is int and v>=0 for v in values) else None
    summary = {'version':'development-pilot013-public-v1','scope':receipt['scope'],
        'task_id':record['task_id'],'title':record['task_snapshot']['title'],
        'source_revision':record['task_snapshot']['revision'],'issue_url':record['task_snapshot']['issue_url'],
        'source_url':record['task_snapshot']['source_url'],'recorded_at':receipt['recorded_at'],
        'outcome':record['outcome'],'calls':record['model_calls'],'patches':record['patch_count'],
        'checks':record['check_count'],'tests_run':check['result']['body']['tests_run'],
        'elapsed_seconds':receipt['elapsed_seconds'],'input_tokens':tokens('prompt_tokens'),
        'output_tokens':tokens('completion_tokens'),'requested_model':experiment['provider']['requested_model'],
        'resolved_model':experiment['provider']['resolved_model'],'source_unchanged':True,
        'retrieval_method':selection['result']['body']['audit']['mode'], 'selected_regions':len(sources),
        'maintainer_entry_hints_used':False,'baseline_and_reference_provenance':'Previously qualified public development case; existing baseline/reference receipts, not a fresh evaluation',
        'original_record_sha256':hashlib.sha256((runtime/'record.json').read_bytes()).hexdigest(),
        'source_hashes':experiment['source'],'configuration':record['config_snapshot']}
    public_receipt = {'summary':summary,'private_runtime_exported':False,
        'cleanup_errors':receipt['cleanup_errors'],'source_unchanged':receipt['source_unchanged'],
        'original_result_sha256':hashlib.sha256((runtime/'result.json').read_bytes()).hexdigest(),
        'experiment_sha256':hashlib.sha256((runtime/'experiment.json').read_bytes()).hexdigest(),
        'publication_scope':'Reviewed public-upstream development captures; static export, not API publication or a new execution'}
    files = {'candidate.patch':patch['result']['body']['patch'].encode(),
        'checks.json':(runtime/'blobs'/check['result']['sha256']).read_bytes(),
        'retrieval.json':(runtime/'blobs'/selection['result']['sha256']).read_bytes(),
        'bundle.json':(runtime/'record.json').read_bytes(),'receipt.json':raw_json(public_receipt)}
    # This showcase contains public upstream source and tool evidence only. Never
    # copy authentication files, process environments, database dumps or weights.
    for name,raw in files.items():
        if len(raw)>1024**2 or any(marker in raw for marker in (b'/Users/', b'OPENAI_API_KEY=', b'GEMINI_API_KEY=', b'Bearer ')):
            raise ValueError('Public capture requires privacy/size review: '+name)
    catalog = {name:{'base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest(),
        'bytes':len(raw),'filename':name,'media_type':'text/x-diff' if name.endswith('.patch') else 'application/json'}
        for name,raw in files.items()}
    return summary, files, catalog


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    summary,files,catalog=package(args.runtime)
    if args.output.exists():
        raise ValueError('Public output exists; preserve it and use a new release directory')
    args.output.mkdir(parents=True)
    for name,raw in {**files,'summary.json':raw_json(summary),'downloads.json':raw_json(catalog)}.items():
        (args.output/name).write_bytes(raw)
    print(json.dumps({'passed':True,'files':len(files)+2,'outcome':summary['outcome'],
                      'calls':summary['calls'],'tests_run':summary['tests_run']}))


if __name__=='__main__':
    main()
