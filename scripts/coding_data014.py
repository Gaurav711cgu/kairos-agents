"""Acquire and screen pinned public repair supervision; never qualify or train it."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.request

from scripts.qualify014 import immutable, no_symlinks, sha, storage_guard, covered
from scripts.retrieval_study011 import issue_digest, load

DATASET = 'SWE-Gym/SWE-Gym'
REVISION = 'bb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb'
FILENAME = 'data/train-00000-of-00001.parquet'
BYTES = 43644473
SHA256 = '60569cea74bb281f7a5579467436a2bc1932c6e0c5f2f7fa0d084392abd9ad97'
EXPECTED_EXPOSURE_SHA256 = 'df992139ab624087f6141eb8401e78294ff6bcb203dfb76c3ab22e0bbfed6957'
EXPECTED_ROWS = 2438
MAX_CANDIDATES = 500
RESERVED_REPOSITORIES = {'psf/requests', 'sympy/sympy'}
REQUIRED = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'patch', 'test_patch', 'FAIL_TO_PASS', 'PASS_TO_PASS'}
PIN = re.compile(r'[a-f0-9]{40}\Z')


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def path_ok(name):
    path=PurePosixPath(name)
    if (not name or '\\' in name or path.is_absolute() or name!=path.as_posix()
            or any(p in {'','.', '..'} or p.startswith('.') for p in name.split('/'))):
        raise ValueError('Unsafe source path')
    if path.suffix!='.py' or any(p in {'tests','test','testing','conftest.py'} or p.startswith('test_') for p in path.parts):
        raise ValueError('Protected or non-Python source edit')
    return name


def patch_scope(patch):
    """Conservative prefilter only; actual source replay remains mandatory."""
    if not isinstance(patch,str) or not patch or len(patch.encode())>256*1024:
        raise ValueError('Missing or oversized reference patch')
    old=[];new=[];changes=0;hunks=0;current=False
    for line in patch.splitlines():
        if line.startswith('--- '):
            if not line.startswith('--- a/'):raise ValueError('Creation/deletion or ambiguous source path')
            old.append(path_ok(line[6:]));current=False
        elif line.startswith('+++ '):
            if not line.startswith('+++ b/'):raise ValueError('Creation/deletion or ambiguous source path')
            new.append(path_ok(line[6:]));current=False
        elif line.startswith('@@ '):hunks+=1;current=True
        elif current and line.startswith(('+','-')):changes+=1
        elif line.startswith('diff --git '):current=False
        elif line.startswith(('GIT binary patch','Binary files','rename from','rename to','old mode','new mode','new file mode','deleted file mode')):
            raise ValueError('Unsupported source operation')
    if not old or old!=new or len(set(old))!=len(old) or len(old)>2 or not 0<changes<=40 or not hunks:
        raise ValueError('Outside two-file/40-line source repair scope')
    return {'paths':old,'changed_lines':changes,'hunks':hunks}


def selectors(value):
    result=json.loads(value) if isinstance(value,str) else value
    if not isinstance(result,list) or any(not isinstance(v,str) or not v for v in result):
        raise ValueError('Invalid test selector list')
    return result


def screen(rows,exposure):
    if not isinstance(rows,list):raise ValueError('Dataset must be a complete row list')
    ids=[r.get('instance_id') for r in rows]
    if any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,179}',v) for v in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Invalid or duplicate instance identity')
    exposed={r['instance_id'] for r in exposure['exposures']}
    exposed_issues=set(exposure['exposed_issue_digests'])
    ledger=[];candidates=[];seen_issues={};seen_patches={};seen_sources={}
    for row in sorted(rows,key=lambda r:r['instance_id']):
        identifier=row['instance_id']; entry={'instance_id':identifier,'repository':row.get('repo'),'status':'excluded'}
        try:
            if not REQUIRED<=set(row):raise ValueError('Missing required fields')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',row['repo']) or not PIN.fullmatch(row['base_commit']):raise ValueError('Invalid repository/revision')
            if not isinstance(row['problem_statement'],str) or not row['problem_statement'].strip():raise ValueError('Missing issue text')
            issue=issue_digest(row['problem_statement'])
            if identifier in exposed or issue in exposed_issues:raise ValueError('Reserved or previously exposed issue')
            if row['repo'] in RESERVED_REPOSITORIES:raise ValueError('Repository reserved for adapter evaluation')
            scope=patch_scope(row['patch'])
            if not isinstance(row['test_patch'],str) or not row['test_patch']:raise ValueError('Missing independent test patch')
            failing=selectors(row['FAIL_TO_PASS']);selectors(row['PASS_TO_PASS'])
            if not failing:raise ValueError('No declared regression test')
            normalized=text_sha(' '.join(row['patch'].split()))
            source=(row['repo'],row['base_commit'])
            if issue in seen_issues:raise ValueError('Duplicate issue text: '+seen_issues[issue])
            if normalized in seen_patches:raise ValueError('Duplicate normalized patch: '+seen_patches[normalized])
            if source in seen_sources:raise ValueError('Duplicate source revision: '+seen_sources[source])
            seen_issues[issue]=identifier;seen_patches[normalized]=identifier;seen_sources[source]=identifier
            entry.update(row_sha256=hashlib.sha256(canonical(row)).hexdigest(),base_commit=row['base_commit'],issue_sha256=issue,
                         reference_patch_sha256=text_sha(row['patch']),test_patch_sha256=text_sha(row['test_patch']),scope=scope)
            if len(candidates)>=MAX_CANDIDATES:raise ValueError('Predeclared candidate inspection bound reached')
            entry.update(status='pending_qualification',reason='Requires issue-family/license review, pinned source, reviewed environment and independent baseline/reference checks')
            candidates.append(identifier)
        except (ValueError,TypeError,KeyError) as error:
            entry['reason']=str(error)
        ledger.append(entry)
    repositories=Counter(r['repository'] for r in ledger if r['status']=='pending_qualification')
    return {'version':'coding-data-screen014-v1','dataset':DATASET,'revision':REVISION,'rows':len(rows),
            'max_candidate_inspections':MAX_CANDIDATES,'candidate_order':'instance_id ascending after fixed safety/scope/exposure prefilters',
            'candidate_ids':candidates,'candidate_repository_counts':dict(sorted(repositories.items())),
            'dispositions':dict(sorted(Counter(r['status'] for r in ledger).items())),
            'exclusion_reasons':dict(sorted(Counter(r['reason'] for r in ledger if r['status']=='excluded').items())),
            'independently_verified_training_repairs':0,'training_ready':False,'cloud_upload_allowed':False,
            'limits':'Static screening is not qualification, issue-family resolution, rights approval, source replay or verified repair evidence.',
            'ledger':ledger}


def checked_exposure(path):
    if sha(path)!=EXPECTED_EXPOSURE_SHA256:raise ValueError('Frozen training exposure inventory differs')
    exposure=load(path)
    if exposure.get('version')!='training-exposure014-v1' or len(exposure.get('reserved014_ids',[]))!=24:
        raise ValueError('Complete current evaluation exclusions are required')
    if not set(exposure['reserved014_ids'])<={r['instance_id'] for r in exposure['exposures']}:
        raise ValueError('A reserved evaluation identity is absent from the exclusion ledger')
    return exposure


def fetch(runtime,roots,opener=urllib.request.urlopen):
    runtime=no_symlinks(runtime)
    if not covered(runtime,roots):raise ValueError('Intake runtime must be inside a counted storage root')
    storage_guard(roots,BYTES+4*1024**2)
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    destination=runtime/'swe-gym.parquet';pending=runtime/'swe-gym.parquet.pending'
    if destination.exists():
        if destination.stat().st_size!=BYTES or sha(destination)!=SHA256:raise ValueError('Existing dataset bytes differ')
        return destination
    if pending.exists():raise ValueError('Partial download preserved; inspect it before starting a new intake')
    url=f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{FILENAME}'
    request=urllib.request.Request(url,headers={'User-Agent':'kairos-coding-data014'})
    total=0;hasher=hashlib.sha256()
    with opener(request,timeout=60) as response,pending.open('xb') as output:
        pending.chmod(0o600)
        while chunk:=response.read(1024*1024):
            total+=len(chunk)
            if total>BYTES:raise ValueError('Dataset exceeds pinned byte count')
            hasher.update(chunk);output.write(chunk)
    if total!=BYTES or hasher.hexdigest()!=SHA256:raise ValueError('Dataset size or SHA-256 differs')
    pending.rename(destination)
    immutable(runtime/'acquisition.json',{'version':'coding-acquisition014-v1','dataset':DATASET,'revision':REVISION,
              'origin':url,'bytes':total,'sha256':SHA256,'acquired_at':datetime.now(timezone.utc).isoformat(),
              'dataset_license_label':'MIT; upstream licenses and issue rights require independent review',
              'source_execution':False,'model_training':False,'cloud_upload':False})
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--exposure',type=Path,required=True)
    parser.add_argument('--budget-root',type=Path,action='append',required=True)
    args=parser.parse_args();exposure=checked_exposure(args.exposure);dataset=fetch(args.runtime,args.budget_root)
    import pyarrow.parquet as pq
    rows=pq.read_table(dataset).to_pylist()
    if len(rows)!=EXPECTED_ROWS:raise ValueError('Pinned dataset row count differs')
    result=screen(rows,exposure)
    result.update(dataset_sha256=SHA256,exposure_sha256=sha(args.exposure))
    immutable(args.runtime/'screen.json',result)
    storage_guard(args.budget_root)
    print(json.dumps({k:v for k,v in result.items() if k not in {'ledger','candidate_ids','exclusion_reasons'}},indent=2))


if __name__=='__main__':main()
