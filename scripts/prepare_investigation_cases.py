"""Prepare public historical cases; reference material never enters agent tool roots."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime/investigations'
IDS = ['django__django-10097', 'django__django-10554', 'django__django-10880', 'django__django-10914', 'django__django-10973']
SUITES = ['validators', 'queries.test_qs_combinators', 'aggregation', 'test_utils', 'dbshell.test_postgresql']
REVISION = '6f8cb01'


def run(argv, **kwargs):
    return subprocess.run(argv, text=True, capture_output=True, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(root):
    items = [(str(p.relative_to(root)), sha(p)) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()]
    return hashlib.sha256(json.dumps(items, separators=(',', ':')).encode()).hexdigest()


def docker_check(source, image, command, test_patch='', reference=''):
    with tempfile.TemporaryDirectory(prefix='kairos-preflight-') as temporary:
        work = Path(temporary) / 'source'
        shutil.copytree(source, work, symlinks=True)
        for patch in [test_patch, reference]:
            if patch:
                applied = run(['git', 'apply', '-'], cwd=work, input=patch)
                if applied.returncode:
                    return {'returncode': 126, 'stdout': '', 'stderr': applied.stderr}
        result = run(['docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                      '--security-opt=no-new-privileges', '--user=10001:10001', '--cpus=2', '--memory=1g',
                      '--pids-limit=128', '--tmpfs=/tmp:rw,nosuid,size=128m',
                      '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/workspace',
                      '-v', str(work)+':/workspace:ro', '-w', '/workspace', image, *command], timeout=120)
        return {'returncode': result.returncode, 'stdout': result.stdout[-24000:], 'stderr': result.stderr[-24000:]}


def prepare_public():
    frozen=ROOT/'cases/provenance.json'
    if frozen.exists():
        return {record['instance_id']:record for record in json.loads(frozen.read_text())['records']}
    rows = []
    for offset in range(0, 500, 100):
        url = f'https://datasets-server.huggingface.co/rows?dataset=princeton-nlp/SWE-bench_Verified&config=default&split=test&offset={offset}&length=100'
        rows.extend(json.load(urllib.request.urlopen(url, timeout=40))['rows'])
    selected = {r['row']['instance_id']: r['row'] for r in rows}
    return selected


def own_cases():
    cases = []
    revision = run(['git', 'rev-parse', REVISION], cwd=ROOT).stdout.strip()
    for name in ['kairos-clock-lease', 'kairos-body-limit']:
        directory = RUNTIME / 'cases' / name
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / 'source'
        if not (source/'kairos_api').exists():
            archive = subprocess.run(['git', 'archive', revision, 'kairos_api'], cwd=ROOT, capture_output=True, check=True)
            source.mkdir(exist_ok=True)
            import io
            with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as files:
                files.extractall(source, filter='data')
        if name == 'kairos-clock-lease':
            verification = '''import datetime as dates
import kairos_api.jobs_repository as module
now = dates.datetime.now(dates.timezone.utc)
real = dates.datetime
class Clock(real):
    offset = 365
    @classmethod
    def now(cls, tz=None): return real.now(tz) + dates.timedelta(days=cls.offset)
module.datetime = Clock
class Connection:
    def execute(self, query, values):
        assert 'clock_timestamp()' in query, 'Database clock must be authoritative'
        self.expired = values[0] <= now
        return self
    def fetchone(self): return {'expired': self.expired}
repository = module.JobsRepository.__new__(module.JobsRepository)
job = {'id': 'case', 'lease_token': 1, 'lease_owner': 'worker'}
row = {**job, 'status': 'running', 'lease_expires_at': now + dates.timedelta(seconds=60)}
repository._locked = lambda connection, identifier: row
assert repository._fenced(Connection(), job) == row
Clock.offset = -365
row['lease_expires_at'] = now - dates.timedelta(seconds=1)
try: repository._fenced(Connection(), job)
except RuntimeError: pass
else: raise AssertionError('Expired database lease accepted')
print('Regression and both lease ownership checks passed')
'''
            target = source/'kairos_api/jobs_repository.py'
            original = target.read_text()
            fixed = original.replace('row["lease_expires_at"] <= datetime.now(timezone.utc)', 'connection.execute("SELECT %s::timestamptz <= clock_timestamp() AS expired", (row["lease_expires_at"],)).fetchone()["expired"]')
            import difflib
            reference = ''.join(difflib.unified_diff(original.splitlines(True),fixed.splitlines(True),fromfile='a/kairos_api/jobs_repository.py',tofile='b/kairos_api/jobs_repository.py'))
            title = 'A worker clock rejects a valid database lease'
            issue = 'At the historical revision, lease ownership compares a database timestamp with the worker host clock. A host clock one year ahead rejects a valid lease. A host clock behind accepts an expired lease. Make database time authoritative without weakening owner and fencing-token checks.'
            entry = 'kairos_api/jobs_repository.py'
        else:
            verification = '''from fastapi.testclient import TestClient
from kairos_api.app import create_app
client = TestClient(create_app())
response = client.post('/api/jobs', content=b'{' + b'x' * 32768, headers={'Content-Type':'application/json'})
assert response.status_code == 413, response.status_code
assert response.headers.get('cache-control') == 'no-store'
assert client.post('/api/jobs', content=b'{', headers={'Content-Type':'application/json'}).status_code == 422
print('Oversized body rejected before parsing; small invalid JSON remains 422')
'''
            original = (source/'kairos_api/app.py').read_text()
            fixed = original.replace('from fastapi.middleware.cors import CORSMiddleware', 'from fastapi.middleware.cors import CORSMiddleware\nfrom kairos_api.http_boundary import BoundedBodyMiddleware').replace('    def repo(request:', '    application.add_middleware(BoundedBodyMiddleware)\n\n    def repo(request:')
            import difflib
            reference = ''.join(difflib.unified_diff(original.splitlines(True),fixed.splitlines(True),fromfile='a/kairos_api/app.py',tofile='b/kairos_api/app.py'))
            boundary = (ROOT/'kairos_api/http_boundary.py').read_text()
            reference += ''.join(difflib.unified_diff([],boundary.splitlines(True),fromfile='/dev/null',tofile='b/kairos_api/http_boundary.py'))
            title = 'Oversized HTTP bodies reach JSON parsing'
            issue = 'At the historical revision, a 32,769-byte invalid JSON command reaches parsing and returns 422. Bound mutating HTTP bodies to 32,768 observed bytes before parsing or authentication. Return 413 with Cache-Control: no-store; retain ordinary validation of small JSON. Do not trust Content-Length alone.'
            entry = 'kairos_api/app.py'
        (directory/'verify.py').write_text(verification)
        (directory/'reference.patch').write_text(reference)
        # Verification is inserted only into the disposable verifier workspace.
        (directory/'test.patch').write_text('')
        cases.append({'id':name,'title':title,'issue':issue,'repository':'Kairos','revision':revision,
                      'source_url':'local-git:'+revision,'issue_url':None,'entry_files':[entry],
                      'image':'kairos-api:build002','command':['python','/verification/verify.py'],
                      'approved_prefix':'kairos_api/','split':'development' if 'clock' in name else 'validation',
                      'provenance':'Historical controlled reproduction; clock uses a deterministic timestamp fixture.' if 'clock' in name else 'Historical controlled HTTP reproduction.'})
    return cases


def main():
    RUNTIME.mkdir(parents=True,exist_ok=True)
    selected = prepare_public()
    cases = own_cases()
    for index, identifier in enumerate(IDS):
        record = selected[identifier]
        directory = RUNTIME/'cases'/identifier
        directory.mkdir(parents=True,exist_ok=True)
        for filename,key in [('reference.patch','patch'),('test.patch','test_patch')]:
            (directory/filename).write_text(record[key])
        (directory/'record.json').write_text(json.dumps(record,indent=2))
        source=directory/'source'
        if not source.exists():
            archive=directory/'source.tar.gz'
            urllib.request.urlretrieve('https://codeload.github.com/django/django/tar.gz/'+record['base_commit'],archive)
            source.mkdir()
            with tarfile.open(archive) as files:
                prefix=files.getmembers()[0].name+'/'
                for member in files.getmembers():
                    if member.name.startswith(prefix): member.name=member.name[len(prefix):]
                    if member.name: files.extract(member,source,filter='data')
        entry=[line[6:] for line in record['patch'].splitlines() if line.startswith('+++ b/') and line.endswith('.py')]
        cases.append({'id':identifier,'title':record['problem_statement'].splitlines()[0],
                      'issue':record['problem_statement'][:9000],'repository':'django/django','revision':record['base_commit'],
                      'source_url':'https://github.com/django/django/tree/'+record['base_commit'],
                      'issue_url':'https://github.com/django/django/pull/'+identifier.rsplit('-',1)[1],
                      'entry_files':entry,'image':'kairos-investigation-django:build003',
                      'command':['python','tests/runtests.py',SUITES[index],'--parallel=1','--verbosity=1'],
                      'approved_prefix':'django/','split':'development' if index<2 else 'validation',
                      'provenance':'SWE-bench Verified historical issue; human-localized source entry points. Not an official benchmark run.'})
    receipts=[]
    for case in cases:
        directory=RUNTIME/'cases'/case['id']
        image=run(['docker','image','inspect',case['image'],'--format','{{.Id}}']).stdout.strip()
        if not image: raise RuntimeError('Missing reviewed image: '+case['image'])
        case['image']=image
        case['source_digest']=tree_hash(directory/'source')
        case['reference_digest']=sha(directory/'reference.patch')
        case['verification_digest']=hashlib.sha256(((directory/'test.patch').read_text()+(directory/'verify.py').read_text() if (directory/'verify.py').exists() else (directory/'test.patch').read_text()).encode()).hexdigest()
        # Own cases require a verifier mount; public cases apply their hidden test patch.
        outputs=[]
        for variant in ['baseline','reference']:
            if case['repository']=='Kairos':
                with tempfile.TemporaryDirectory() as temporary:
                    work=Path(temporary)/'source';shutil.copytree(directory/'source',work)
                    if variant=='reference':
                        result=run(['git','apply','-'],cwd=work,input=(directory/'reference.patch').read_text())
                        if result.returncode: raise RuntimeError(result.stderr)
                    result=run(['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=10001:10001','--cpus=2','--memory=1g','--pids-limit=128','--tmpfs=/tmp:rw,nosuid,size=128m','-e','PYTHONDONTWRITEBYTECODE=1','-e','PYTHONPATH=/workspace','-v',str(work)+':/workspace:ro','-v',str(directory/'verify.py')+':/verification/verify.py:ro','-w','/workspace',image,*case['command']],timeout=120)
                    output={'returncode':result.returncode,'stdout':result.stdout[-24000:],'stderr':result.stderr[-24000:]}
            else:
                output=docker_check(directory/'source',image,case['command'],(directory/'test.patch').read_text(),(directory/'reference.patch').read_text() if variant=='reference' else '')
            outputs.append(output)
            print(case['id'],variant,output['returncode'],flush=True)
        case['qualified']=outputs[0]['returncode']!=0 and outputs[1]['returncode']==0
        receipts.append({'task_id':case['id'],'baseline':outputs[0],'reference':outputs[1],'qualified':case['qualified']})
    exclusions=[{'task_id':c['id'],'reason':'Reference repair does not pass the complete selected suite under the pinned environment.'} for c in cases if not c['qualified']]
    cases=[c for c in cases if c['qualified']]
    public_index=0
    for case in cases:
        if case['repository']=='django/django':
            case['split']='development' if public_index<2 else 'validation'
            public_index+=1
    manifest={'version':'repository-cases-v1','selection':{'order':'instance ID','lightweight_repositories':['django/django'],'exclusions':exclusions+[{'repository':'astropy/astropy','reason':'Compiled scientific dependencies excluded from the lightweight Python preflight on an 8GB host.'}],'localization':'Entry files selected by humans; both configurations receive identical localization.','contamination':'Public historical issues may occur in model training data.'},'cases':cases}
    output=ROOT/'cases';output.mkdir(exist_ok=True)
    (output/'investigations.json').write_text(json.dumps(manifest,indent=2)+'\n')
    evidence=ROOT/'evidence/build003';evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'case-preflight.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print('Qualified',sum(c['qualified'] for c in cases),'of',len(cases),flush=True)

if __name__=='__main__': main()
