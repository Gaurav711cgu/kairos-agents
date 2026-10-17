"""Prepare private source-bound supervision without model calls or training admission."""
import argparse
import difflib
import hashlib
from pathlib import Path

from kairos_api.investigations.context_v7 import initial_sources, source_block
from kairos_api.investigations.contracts import ActionV7
from kairos_api.model_runtime import digest
from kairos_api.investigations.patches import source_path
from kairos_api.investigations.registry import CaseRegistry, tree_hash
from kairos_api.investigations.sandbox import Workspace
from scripts import qualify014 as q
from scripts.coding_data014 import canonical, patch_scope
from scripts.coding_verifier014 import qualifies
from scripts.retrieval_study011 import issue_digest


def convert_action(workspace, reference_patch, regions, *, anchor_policy='preceding-v1'):
    """Render a reference target only inside independently selected original regions.

    Callers must capture regions from issue/source before this function sees the
    reference patch. No missing region is expanded using the answer. Generated
    actions must replay through the same production edit validator byte-for-byte.
    """
    if anchor_policy not in {'preceding-v1','captured-neighbor-v2'}:raise ValueError('Unknown insertion anchor policy')
    scope=patch_scope(reference_patch)
    original_root=workspace.registry.directory(workspace.case)/'source'
    bindings={block['source_id']:item['reference'] for item in regions for block in [source_block(item)]}
    for reference in bindings.values():workspace.restore_reference({'reference':reference})
    workspace.propose(reference_patch)
    expected={name:source_path(workspace.root,workspace.case['approved_prefix'],name).read_bytes() for name in scope['paths']}
    edits=[]
    for name in scope['paths']:
        original=source_path(original_root,workspace.case['approved_prefix'],name).read_bytes()
        before=original.decode('utf-8').splitlines(keepends=True)
        after=expected[name].decode('utf-8').splitlines(keepends=True)
        for tag,start,end,new_start,new_end in difflib.SequenceMatcher(a=before,b=after,autojunk=False).get_opcodes():
            if tag=='equal':continue
            replacement=''.join(after[new_start:new_end])
            if start==end:
                # Original v1 always uses the preceding line. Revision two may
                # use the following line only when that line was already read.
                choices=[]
                if start>0:choices.append((start-1,end,before[start-1]+replacement))
                if before and start<len(before):choices.append((start,end+1,replacement+before[start]))
                if anchor_policy=='preceding-v1':choices=choices[:1]
                allowed=[choice for choice in choices if any(r['path']==name and r['start_line']<=choice[0]+1<=choice[1]<=r['end_line'] for r in bindings.values())]
                if not allowed:raise ValueError('Reference edit is outside issue-only selected context; no answer-assisted expansion')
                start,end,replacement=allowed[0]
            matches=sorted((handle,reference) for handle,reference in bindings.items()
                           if reference['path']==name and reference['start_line']<=start+1<=end<=reference['end_line'])
            if not matches:raise ValueError('Reference edit is outside issue-only selected context; no answer-assisted expansion')
            handle,_=matches[0]
            edits.append({'source_id':handle,'start_line':start+1,'end_line':end,'new':replacement})
    action={'action':'propose_patch','edits':edits}
    ActionV7.validate_python(action)
    rendered=workspace.propose_line_edits(edits,bindings)
    for name,raw in expected.items():
        if source_path(workspace.root,workspace.case['approved_prefix'],name).read_bytes()!=raw:
            raise ValueError('Rendered action differs from the verified reference bytes')
    return action,rendered


def verified_capture(folder,screen,identifier):
    """Check source, selected scope, full captures and original bindings offline."""
    output=q.no_symlinks(folder)
    receipt=q.load(output/'receipt.json');binding=q.load(output/'binding.json')
    case=binding['case'];scope=binding['scope'];registry=CaseRegistry(output/'registry.json',output/'registry')
    if (receipt.get('qualified') is not True or receipt.get('model_calls')!=0
            or receipt.get('original_source_unchanged') is not True
            or receipt.get('instance_id')!=identifier or case.get('dataset_instance_id')!=identifier
            or registry.cases()!=[case] or q.load(output/'scope.json')!=scope):
        raise ValueError('Complete independent qualification is required')
    matches=[item for item in screen['ledger'] if item['instance_id']==identifier]
    if identifier not in screen['candidate_ids'] or len(matches)!=1:raise ValueError('Task is outside frozen candidates')
    entry=matches[0]
    if (case['repository']!=entry['repository'] or case['revision']!=entry['base_commit']
            or issue_digest(case['issue'])!=entry['issue_sha256']
            or case['reference_digest']!=entry['reference_patch_sha256']):
        raise ValueError('Captured task differs from frozen source/issue/reference')
    bound=binding['binding']
    runtime=output.parents[2]
    images=[path for path in (runtime/'environments').glob('*/image.json') if q.load(path).get('id')==case['image']]
    if len(images)!=1 or digest({'case':case,'scope':scope,'screen_sha256':q.sha(runtime/'screen.json'),'image_receipt_sha256':q.sha(images[0])})!=bound:
        raise ValueError('Original qualification binding differs')
    if receipt['binding']!=bound or receipt['image']!=case['image']:
        raise ValueError('Qualification receipt binding differs')
    captures={}
    if set(receipt['checks_sha256'])!={'baseline','reference'}:raise ValueError('Both complete checks are required')
    for key,expected in receipt['checks_sha256'].items():
        capture=q.load(output/(key+'.json'))
        if q.sha(output/(key+'.json'))!=expected or capture['binding']!=bound or capture['stage']!=key:
            raise ValueError('Captured check integrity differs')
        captures[key]=capture['result']
    if not qualifies(captures['baseline'],captures['reference']):raise ValueError('Captured checks do not qualify')
    registry.verify(case)
    directory=registry.directory(case)
    if hashlib.sha256((directory/'test.patch').read_bytes()).hexdigest()!=entry['test_patch_sha256']:
        raise ValueError('Independent test patch differs from frozen row')
    return registry,case,receipt


def prepare(runtime,identifier,revision,roots,preparation_revision='v1'):
    if revision not in {'v1','v2'}:raise ValueError('Unsupported qualification revision')
    if preparation_revision not in {'v1','v2','v3'}:raise ValueError('Unsupported action preparation revision')
    if not q.re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,179}',identifier):raise ValueError('Invalid task identifier')
    runtime=q.no_symlinks(runtime)
    if not q.covered(runtime,roots):raise ValueError('Runtime must be inside counted storage roots')
    screen=q.load(runtime/'screen.json')
    output=runtime/'qualification-preparation'/identifier/('qualification-'+revision)
    registry,case,receipt=verified_capture(output,screen,identifier)
    q.storage_guard(roots,q.tree_bytes(registry.directory(case)/'source')+q.CHECK_RESERVATION)
    destination=output/('action-preparation-'+preparation_revision)
    if destination.exists():raise ValueError('Action preparation exists; preserve it instead of replacing labels')
    destination.mkdir(mode=0o700)
    workspace=None
    try:
        with q.counted_temporary(destination/'temporary'):
            workspace=Workspace(registry,case)
            try:
                # Selection sees issue/source only; target/test bytes are read later.
                if preparation_revision in {'v2','v3'}:
                    if preparation_revision=='v3':
                        from scripts.coding_context_v3_014 import select
                    else:
                        from scripts.coding_context014 import select
                    regions=select(workspace)
                else:regions=initial_sources(workspace,use_entry_hints=False)
                if not regions:raise ValueError('No issue-only original-source context found')
                context=[source_block(item) for item in regions]
                patch=(registry.directory(case)/'reference.patch').read_text()
                action,rendered=convert_action(workspace,patch,regions,anchor_policy='captured-neighbor-v2' if preparation_revision in {'v2','v3'} else 'preceding-v1')
            finally:
                if workspace is not None:workspace.close()
        if tree_hash(registry.directory(case)/'source')!=case['source_digest']:raise ValueError('Original source changed')
        prompt={'issue':case['issue'],'original_source':context,'instruction':'Return one propose_patch JSON action using source_id, start_line, end_line and new. Replace inclusive whole original-source lines. Preserve indentation.'}
        example={'version':'coding-action-example014-v1','instance_id':identifier,'repository':case['repository'],'source_commit':case['revision'],'source_digest':case['source_digest'],'input':prompt,'assistant_target':action,'reference_derived_supervision':True,'training_admitted':False,'tokenized':False,'qualification_receipt_sha256':q.sha(output/'receipt.json')}
        q.immutable(destination/'example.json',example)
        result={'version':'coding-action-preparation014-v1','instance_id':identifier,'status':'converted_not_admitted','example_sha256':q.sha(destination/'example.json'),'input_sha256':hashlib.sha256(canonical(prompt)).hexdigest(),'target_sha256':hashlib.sha256(canonical(action)).hexdigest(),'rendered_patch_sha256':hashlib.sha256(rendered['patch'].encode()).hexdigest(),'context_policy':'Issue-only AST localization before reading reference; no target-assisted expansion','context_regions':len(context),'edits':len(action['edits']),'source_unchanged':True,'model_calls':0,'training_admitted':False,'remaining':['rights/family/near-duplicate gates','corpus/split freeze','complete tokenized sequence bound']}
    except ValueError as error:
        result={'version':'coding-action-preparation014-v1','instance_id':identifier,'status':'conversion_rejected','reason':str(error),'training_admitted':False,'model_calls':0}
    result['preparation_revision']=preparation_revision
    result['preparation_source_sha256']=q.sha(Path(__file__))
    if preparation_revision in {'v2','v3'}:
        context_name='coding_context_v3_014.py' if preparation_revision=='v3' else 'coding_context014.py'
        result['context_source_sha256']=q.sha(Path(__file__).with_name(context_name))
    q.immutable(destination/'receipt.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--task-id',required=True)
    parser.add_argument('--revision',choices=['v1','v2'],default='v1');parser.add_argument('--preparation-revision',choices=['v1','v2','v3'],default='v1');parser.add_argument('--budget-root',type=Path,action='append',required=True)
    args=parser.parse_args()
    import json
    print(json.dumps(prepare(args.runtime,args.task_id,args.revision,args.budget_root,args.preparation_revision),indent=2))


if __name__=='__main__':main()
