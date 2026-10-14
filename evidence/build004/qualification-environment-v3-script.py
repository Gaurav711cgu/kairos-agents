"""Deterministic case qualification. No model execution and no success-based selection."""
import hashlib,json,random,re,shutil,subprocess,tarfile,urllib.request
from pathlib import Path
from kairos_api.investigations.registry import CaseRegistry,tree_hash
from kairos_api.investigations.sandbox import Workspace
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'.runtime/investigations';OUT=ROOT/'evidence/build004';SEED=741903
REPOSITORIES=['django/django','pytest-dev/pytest','psf/requests']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def output(value,path):path.write_text(json.dumps(value,indent=2)+'\n')
def command(args):return subprocess.check_output(args,text=True).strip()
def main():
    rows=json.loads((RUNTIME/'study004/records.json').read_text());old=json.loads((ROOT/'cases/provenance.json').read_text())
    excluded_ids={r['instance_id'] for r in old['records']}
    manifest={'version':'repository-cases-v1','cases':[]};receipts=[];exclusions=[]
    images={'django/django':command(['docker','image','inspect','kairos-investigation-django:build003','--format','{{.Id}}'])}
    images.update({repo:command(['docker','image','inspect','kairos-investigation-study:build004','--format','{{.Id}}']) for repo in REPOSITORIES[1:]})
    temporary_manifest=RUNTIME/'study004/qualification-registry.json'
    for repository in REPOSITORIES:
        accepted=0
        for row in sorted((r for r in rows if r['repo']==repository),key=lambda r:r['instance_id']):
            identifier=row['instance_id']
            if identifier in excluded_ids:
                exclusions.append({'id':identifier,'reason':'Previously attempted or preflighted in build003'});continue
            if accepted>=6:break
            directory=RUNTIME/'cases'/identifier;directory.mkdir(parents=True,exist_ok=True)
            receipt_path=OUT/'qualification'/f'{identifier}.json';receipt_path.parent.mkdir(exist_ok=True)
            if receipt_path.exists():
                receipt=json.loads(receipt_path.read_text());receipts.append(receipt)
                if receipt['qualified']:manifest['cases'].append(receipt['case']);accepted+=1
                else:exclusions.append({'id':identifier,'reason':receipt['reason']})
                continue
            try:
                paths=[line[6:] for line in row['patch'].splitlines() if line.startswith('+++ b/')]
                prefix='django/' if repository=='django/django' else 'src/_pytest/' if repository=='pytest-dev/pytest' else 'requests/'
                changed=sum(1 for line in row['patch'].splitlines() if line[:1] in ('+','-') and not line.startswith(('+++','---')))
                if not paths or len(paths)>3 or changed>200 or any(not path.startswith(prefix) or not path.endswith('.py') for path in paths):raise ValueError('Maintainer repair exceeds registered source-only patch scope')
                archive=directory/'source.tar.gz';source=directory/'source'
                if not source.exists():
                    urllib.request.urlretrieve('https://codeload.github.com/'+repository+'/tar.gz/'+row['base_commit'],archive)
                    source.mkdir()
                    with tarfile.open(archive) as files:
                        for member in files:
                            parts=member.name.split('/',1)
                            if len(parts)==2 and parts[1]:member.name=parts[1];files.extract(member,source,filter='data')
                (directory/'reference.patch').write_text(row['patch']);(directory/'test.patch').write_text(row['test_patch'])
                (directory/'record.json').write_text(json.dumps(row,indent=2))
                case={'id':identifier,'title':row['problem_statement'].splitlines()[0],'issue':row['problem_statement'],'repository':repository,'revision':row['base_commit'],
                      'source_url':'https://github.com/'+repository+'/tree/'+row['base_commit'],'issue_url':'https://github.com/'+repository+'/pull/'+identifier.rsplit('-',1)[1],
                      'entry_files':paths,'approved_prefix':prefix,'split':'qualification','provenance':'Build004 curated SWE-bench Verified case; human-localized entry files. Public training contamination possible.',
                      'image':images[repository],'qualified':True,'command':['python','/verification/verify.py']}
                if repository=='django/django':
                    modules=sorted({line[12:-3].replace('/','.') for line in row['test_patch'].splitlines() if line.startswith('+++ b/tests/') and line.endswith('.py') and not line.endswith('__init__.py')})
                    if not modules:raise ValueError('No registered Django regression module')
                    script="import subprocess,sys,re,json\np=subprocess.run("+repr(['python','tests/runtests.py',*modules,'--parallel=1','--verbosity=1'])+",capture_output=True,text=True)\nprint(p.stdout);print(p.stderr,file=sys.stderr)\nm=re.search(r'Ran (\\d+) tests?',p.stdout+p.stderr)\nprint('KAIROS_VERIFIER_RESULT '+json.dumps({'tests_run':int(m.group(1)) if m else 0,'complete':bool(m) and p.returncode==0}))\nsys.exit(p.returncode if m else 126)\n"
                else:
                    regression=json.loads(row['FAIL_TO_PASS']);existing=json.loads(row['PASS_TO_PASS'])[:20];selected=list(dict.fromkeys(regression+existing))
                    if not regression or not selected:raise ValueError('Missing registered regression tests')
                    bootstrap="import sys,types\nsys.path.insert(0,'/workspace/src')\nv=types.ModuleType('_pytest._version');v.version="+repr(row['version'])+";v.version_tuple=tuple(int(n) for n in v.version.split('.'));sys.modules['_pytest._version']=v\nimport _pytest;_pytest._version=v\n" if repository=='pytest-dev/pytest' else ''
                    script=bootstrap+"import pytest,json\nclass Report:\n def __init__(self):self.passed=set();self.failed=set()\n def pytest_runtest_logreport(self,report):\n  r=report\n  if r.when=='call' and r.passed:self.passed.add(r.nodeid)\n  if r.failed:self.failed.add(r.nodeid)\np=Report()\ncode=pytest.main("+repr(['-q','-p','no:cacheprovider',*selected])+",plugins=[p])\nexpected=set("+repr(selected)+")\ncomplete=expected.issubset(p.passed) and not p.failed\nprint('KAIROS_VERIFIER_RESULT '+json.dumps({'tests_run':len(p.passed|p.failed),'complete':complete,'passed':sorted(p.passed),'failed':sorted(p.failed)}))\nraise SystemExit(0 if code==0 and complete else code or 126)\n"
                (directory/'verify.py').write_text(script)
                case.update(source_digest=tree_hash(source),reference_digest=sha(directory/'reference.patch'),verification_digest=hashlib.sha256((row['test_patch']+script).encode()).hexdigest())
                manifest['cases'].append(case);output(manifest,temporary_manifest);registry=CaseRegistry(temporary_manifest,RUNTIME)
                workspace=Workspace(registry,case)
                try:
                    baseline=workspace.checks();workspace.propose(row['patch']);reference=workspace.checks()
                finally:workspace.close()
                baseline_text=baseline.get('stdout','')+baseline.get('stderr','')
                # A parser/import/timeout failure is not a reproduced behavioral regression.
                matches=re.findall(r'KAIROS_VERIFIER_RESULT (\{[^\n]+\})',baseline_text)
                baseline_summary=json.loads(matches[-1]) if matches else {}
                ref_matches=re.findall(r'KAIROS_VERIFIER_RESULT (\{[^\n]+\})',reference.get('stdout','')+reference.get('stderr',''))
                reference_summary=json.loads(ref_matches[-1]) if ref_matches else {}
                qualified=not baseline['passed'] and not baseline['environment_error'] and baseline.get('returncode') not in (124,126,127) and baseline_summary.get('tests_run',0)>0 and reference['passed'] and reference_summary.get('complete')
                reason=None if qualified else 'Baseline regression or reference repair did not reproduce under registered 1GB/120s environment'
                receipt={'id':identifier,'qualified':bool(qualified),'reason':reason,'baseline':baseline,'reference':reference,'case':case}
                if not qualified:manifest['cases'].pop()
                else:accepted+=1
            except Exception as error:
                receipt={'id':identifier,'qualified':False,'reason':type(error).__name__+': '+str(error)[:400]}
            output(receipt,receipt_path);receipts.append(receipt)
            if not receipt['qualified']:exclusions.append({'id':identifier,'reason':receipt['reason']})
            output({'complete':False,'accepted':len(manifest['cases']),'exclusions':exclusions},OUT/'qualification-progress.json')
            print(identifier,receipt['qualified'],receipt.get('reason'),flush=True)
    for repository in REPOSITORIES:
        subset=[case for case in manifest['cases'] if case['repository']==repository]
        ordering=sorted(subset,key=lambda c:hashlib.sha256((str(SEED)+':'+c['id']).encode()).hexdigest())
        for index,case in enumerate(ordering):case['split']='development' if index<2 else 'evaluation'
    complete=len(manifest['cases'])==18
    manifest['selection']={'seed':SEED,'order':'instance ID ascending per repository','development':2,'evaluation':4,'target_per_repository':6,'complete':complete,'exclusions':exclusions,'status':'qualified; not evaluated','contamination':'Public historical cases may appear in training'}
    output(manifest,ROOT/'cases/study004.json');output({'complete':complete,'qualified':len(manifest['cases']),'exclusions':exclusions,'receipts':[str((OUT/'qualification'/f"{r['id']}.json").relative_to(ROOT)) for r in receipts]},OUT/'qualification.json')
    # Add new qualified cases without modifying historical case objects or registry format.
    active=json.loads((ROOT/'cases/investigations.json').read_text());ids={c['id'] for c in manifest['cases']};active['cases']=[c for c in active['cases'] if c['id'] not in ids]+manifest['cases'];output(active,ROOT/'cases/investigations.json')
    print('Qualification complete:',complete,'qualified:',len(manifest['cases']),flush=True)
if __name__=='__main__':main()
