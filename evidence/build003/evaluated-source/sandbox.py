"""Source tools and a network-disabled verifier. No model-selected shell commands."""
import os
import difflib
import resource
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4
from kairos_api.investigations.patches import apply_patch, source_path


class Workspace:
    def __init__(self, registry, case):
        registry.verify(case)
        self.case, self.registry = case, registry
        self.temporary = tempfile.TemporaryDirectory(prefix='kairos-investigation-')
        self.root = Path(self.temporary.name)/'source'
        self.reset()

    def reset(self):
        if self.root.exists(): shutil.rmtree(self.root)
        shutil.copytree(self.registry.directory(self.case)/'source',self.root,symlinks=True)

    def close(self):
        self.temporary.cleanup()

    def propose(self, patch):
        self.reset()
        try:
            return apply_patch(self.root,self.case['approved_prefix'],patch)
        except Exception:
            self.reset()
            raise

    def propose_edits(self, edits):
        self.reset()
        changes={}
        for edit in edits:
            target=source_path(self.root,self.case['approved_prefix'],edit['path'])
            if not target.is_file(): raise ValueError('Edit target does not exist')
            original=target.read_text()
            if original.count(edit['old'])!=1: raise ValueError('Old text must match exactly once in the original source')
            if edit['old']==edit['new']: raise ValueError('Edit makes no change')
            offset=original.index(edit['old'])
            changes.setdefault(edit['path'],[]).append((offset,offset+len(edit['old']),edit['new']))
        for name,ranges in changes.items():
            ranges.sort()
            if any(left[1]>right[0] for left,right in zip(ranges,ranges[1:])): raise ValueError('Overlapping edits rejected')
            changed=(self.root/name).read_text()
            for start,end,replacement in reversed(ranges): changed=changed[:start]+replacement+changed[end:]
            changes[name]=changed
        patch=''
        for name,changed in changes.items():
            original=(self.root/name).read_text()
            patch+=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
        result=self.propose(patch)
        return {**result,'patch':patch,'construction':'Exact model-authored replacements; mechanical unified diff'}

    def read(self, path, start_line=1):
        target = source_path(self.root,self.case['approved_prefix'],path)
        if not target.is_file() or target.stat().st_size>250000:
            raise ValueError('Source file missing or exceeds 250KB')
        lines = target.read_text().splitlines()
        text='\n'.join(f'{n}: {line}' for n,line in enumerate(lines,start=1) if start_line<=n<start_line+160)
        return {'path':path,'start_line':start_line,'total_lines':len(lines),'text':text[:12000],
                'truncated':start_line+159<len(lines) or len(text)>12000}

    def search(self, query):
        matches=[]
        for path in sorted((self.root/self.case['approved_prefix']).rglob('*.py')):
            try:
                name=str(path.relative_to(self.root));target=source_path(self.root,self.case['approved_prefix'],name)
                if not target.is_file() or target.stat().st_size>250000: continue
                for n,line in enumerate(target.read_text().splitlines(),1):
                    if query.casefold() in line.casefold():
                        matches.append({'path':name,'line':n,'text':line[:200]})
                        if len(matches)>=30: return {'matches':matches,'truncated':True}
            except (ValueError,UnicodeError): continue
        return {'matches':matches,'truncated':False}

    def checks(self, timeout=120):
        directory=self.registry.directory(self.case)
        with tempfile.TemporaryDirectory(prefix='kairos-verification-') as temporary:
            work=Path(temporary)/'source';shutil.copytree(self.root,work,symlinks=True)
            hidden=(directory/'test.patch').read_text()
            if hidden:
                result=subprocess.run(['git','apply','-'],cwd=work,input=hidden,text=True,capture_output=True,timeout=5)
                if result.returncode:
                    return {'passed':False,'environment_error':True,'returncode':126,'stdout':'','stderr':'Hidden verification could not be installed'}
            name='kairos-check-'+uuid4().hex
            argv=['docker','run','--rm','--name',name,'--network=none','--read-only','--cap-drop=ALL',
                  '--security-opt=no-new-privileges','--user=10001:10001','--cpus=2','--memory=1g',
                  '--pids-limit=128','--tmpfs=/tmp:rw,nosuid,size=128m','-e','PYTHONDONTWRITEBYTECODE=1',
                  '-e','PYTHONPATH=/workspace','-v',str(work)+':/workspace:ro','-w','/workspace']
            if (directory/'verify.py').exists():
                argv+=['-v',str(directory/'verify.py')+':/verification/verify.py:ro']
            supervisor="import subprocess,sys,os,signal; p=subprocess.Popen(sys.argv[1:],start_new_session=True);\ntry: code=p.wait(timeout=120)\nexcept subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL); code=124\nsys.exit(code)"
            argv += [self.case['image'],'python','-c',supervisor,*self.case['command']]
            started=time.monotonic()
            try:
                # Redirect output to disk so malicious output cannot fill host memory.
                with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
                    result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=max(1,min(timeout,120)),
                                          preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576)))
                    output=[]
                    for file in (stdout,stderr):
                        size=file.tell();file.seek(max(0,size-24000));output.append(file.read().decode(errors='replace'))
                    return {'passed':result.returncode==0,'environment_error':result.returncode in {125,126,127},
                            'returncode':result.returncode,'stdout':output[0],'stderr':output[1],
                            'seconds':round(time.monotonic()-started,3),'output_limit_bytes':24000,'output_truncated':any(len(value.encode())>=24000 for value in output)}
            except subprocess.TimeoutExpired:
                return {'passed':False,'environment_error':False,'returncode':124,'stdout':'','stderr':'Verification timed out'}
            finally:
                subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
