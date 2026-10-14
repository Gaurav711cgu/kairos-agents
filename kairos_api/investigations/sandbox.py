"""Source tools and a network-disabled verifier. No model-selected shell commands."""
import os
import ast
import json
import re
import hashlib
import base64
from kairos_api.model_runtime import digest
import difflib
import resource
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4
from kairos_api.investigations.patches import apply_patch, source_path

RAW_OUTPUT_LIMIT = 1048576
OUTPUT_TAIL_LIMIT = 24000


def capture_output(stdout, stderr):
    """Retain exact output bytes within one combined capture budget.

    A stream at the file guard is conservatively incomplete: the Docker client
    may have been unable to write its next byte. This is an explicit failed
    verification, never evidence of a successful completed check.
    """
    tails = []
    raw = {'encoding': 'base64', 'maximum_bytes': RAW_OUTPUT_LIMIT}
    remaining = RAW_OUTPUT_LIMIT
    observed = 0
    guard_reached = False
    for name, stream in (('stdout', stdout), ('stderr', stderr)):
        stream.flush()
        size = stream.tell()
        observed += size
        guard_reached = guard_reached or size >= RAW_OUTPUT_LIMIT
        stream.seek(max(0, size - OUTPUT_TAIL_LIMIT))
        tails.append(stream.read().decode(errors='replace'))
        stream.seek(0)
        value = stream.read(min(size, remaining))
        remaining -= len(value)
        raw[name] = {'data': base64.b64encode(value).decode('ascii'),
                     'bytes': len(value), 'observed_bytes': size,
                     'sha256': hashlib.sha256(value).hexdigest(),
                     'truncated': len(value) != size}
    exceeded = observed >= RAW_OUTPUT_LIMIT or guard_reached
    raw.update(observed_bytes=observed, complete=not exceeded,
               scope='Exact captured stream bytes; a quota failure retains bounded prefixes')
    return tails, raw, exceeded


class Workspace:
    def __init__(self, registry, case):
        registry.verify(case)
        self.case, self.registry = case, registry
        self.temporary = tempfile.TemporaryDirectory(prefix='kairos-investigation-')
        self.root = Path(self.temporary.name)/'source'
        self.references = {}
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

    def read_original(self,path,start_line=1,end_line=None):
        original_root=self.registry.directory(self.case)/'source'
        target=source_path(original_root,self.case['approved_prefix'],path)
        if not target.is_file() or target.stat().st_size>250000: raise ValueError('Source file missing or exceeds 250KB')
        raw=target.read_bytes();lines=raw.decode().splitlines(True)
        if start_line<1 or start_line>len(lines): raise ValueError('Source line is outside the original file')
        if end_line is not None and not start_line<=end_line<=min(len(lines),start_line+79):
            raise ValueError('Source region must contain one to 80 original lines')
        chosen=[];size=0
        for line in lines[start_line-1:end_line if end_line is not None else start_line+79]:
            if size+len(line.encode())>8000: break
            chosen.append(line);size+=len(line.encode())
        if not chosen: raise ValueError('Complete source line exceeds excerpt budget')
        if end_line is not None and len(chosen)!=end_line-start_line+1:
            raise ValueError('Complete source region exceeds excerpt budget')
        reference={'path':path,'source_digest':hashlib.sha256(raw).hexdigest(),'start_line':start_line,'end_line':start_line+len(chosen)-1}
        reference['excerpt_id']=digest({**reference,'text':''.join(chosen)})
        result={'path':path,'start_line':start_line,'total_lines':len(lines),'text':''.join(f'{n}: {line}' for n,line in enumerate(chosen,start_line)),
                'reference':reference,'source':'original_snapshot','truncated':reference['end_line']<len(lines)}
        self.references[reference['excerpt_id']]=reference
        return result

    def restore_reference(self,result):
        reference=result.get('reference')
        if reference:
            actual=self.read_original(reference['path'],reference['start_line'],reference['end_line'])['reference']
            if actual!=reference: raise ValueError('Captured source reference changed')

    def propose_handle_edits(self,edits,sources):
        """Render exact source fragments; never infer indentation or repair code."""
        if not 1<=len(edits)<=3: raise ValueError('One to three exact edits are required')
        original_root=self.registry.directory(self.case)/'source'
        changes={};originals={}
        for edit in edits:
            handle=edit['source_id'];reference=sources.get(handle)
            if not re.fullmatch(r'S[a-f0-9]{12}',handle) or not isinstance(reference,dict):
                raise ValueError('Edit requires a captured source handle')
            if handle!='S'+reference.get('excerpt_id','')[:12]:
                raise ValueError('Source handle does not bind its captured excerpt')
            # Restoration independently checks the entire original SHA, region,
            # and excerpt digest. The handle only abbreviates that authority.
            self.restore_reference({'reference':reference})
            captured=self.references.get(reference['excerpt_id'])
            if captured!=reference: raise ValueError('Source handle reference changed')
            target=source_path(original_root,self.case['approved_prefix'],reference['path'])
            raw=target.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=reference['source_digest']:
                raise ValueError('Stale original-source digest')
            original=raw.decode();lines=original.splitlines(True)
            old,new=edit['old'],edit['new']
            if not old or len(old)>12000 or len(new)>12000 or '\x00' in old+new:
                raise ValueError('Exact edit exceeds source fragment bounds')
            if old==new: raise ValueError('Edit makes no change')
            if original.count(old)!=1:
                raise ValueError('Old text must match exactly once in original source')
            offset=original.index(old)
            region_start=sum(map(len,lines[:reference['start_line']-1]))
            region_end=sum(map(len,lines[:reference['end_line']]))
            if not region_start<=offset<offset+len(old)<=region_end:
                raise ValueError('Exact edit escapes captured excerpt')
            name=reference['path'];originals[name]=original
            changes.setdefault(name,[]).append((offset,offset+len(old),new))
        patch=''
        for name,ranges in changes.items():
            ranges.sort()
            if any(left[1]>right[0] for left,right in zip(ranges,ranges[1:])):
                raise ValueError('Overlapping edits rejected')
            original=originals[name];candidate=original
            for start,end,new in reversed(ranges): candidate=candidate[:start]+new+candidate[end:]
            try: ast.parse(candidate,filename=name)
            except SyntaxError as error:
                raise ValueError(f'Candidate Python syntax rejected at line {error.lineno}: {error.msg}') from None
            patch+=''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
        result=self.propose(patch)
        return {**result,'patch':patch,'construction':'captured-exact-fragments-v1','edits':edits,
                'reference_bindings':sources,'rendering':'Exact model-authored replacements; no indentation or semantic correction'}

    def propose_line_edits(self,edits,sources):
        """Render whole-line replacements using captured server-owned authority."""
        expanded=[]
        for edit in edits:
            handle=edit['source_id']; reference=sources.get(handle)
            if not isinstance(reference,dict) or handle!='S'+reference.get('excerpt_id','')[:12]:
                raise ValueError('Edit requires a captured source handle')
            self.restore_reference({'reference':reference})
            expanded.append({**reference,'start_line':edit['start_line'],
                             'end_line':edit['end_line'],'new':edit['new']})
        result=self.propose_snapshot_edits(expanded)
        return {**result,'construction':'captured-source-line-handles-v7','edits':edits,
                'reference_bindings':sources}

    def search_original(self,query):
        candidate=self.root
        try:
            self.root=self.registry.directory(self.case)/'source'
            return {**self.search(query),'source':'original_snapshot'}
        finally: self.root=candidate

    def propose_snapshot_edits(self,edits):
        original_root=self.registry.directory(self.case)/'source';changes={}
        for edit in edits:
            reference=self.references.get(edit['excerpt_id'])
            if not reference or reference['path']!=edit['path']: raise ValueError('Edit requires a captured original-source excerpt')
            target=source_path(original_root,self.case['approved_prefix'],edit['path']);raw=target.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=edit['source_digest'] or reference['source_digest']!=edit['source_digest']: raise ValueError('Stale original-source digest')
            start,end=edit['start_line'],edit['end_line']
            if not reference['start_line']<=start<=end<=reference['end_line']: raise ValueError('Edit range escapes captured excerpt')
            lines=raw.decode().splitlines(True)
            replacement=edit['new']
            # Whole-line edits need a separator before the following original line.
            # This renders a line boundary; it never changes model-authored code.
            if replacement and not replacement.endswith('\n'): replacement+='\n'
            if ''.join(lines[start-1:end])==replacement: raise ValueError('Edit makes no change')
            changes.setdefault(edit['path'],[]).append((start-1,end,replacement))
        patch=''
        for path,ranges in changes.items():
            ranges.sort()
            if any(left[1]>right[0] for left,right in zip(ranges,ranges[1:])): raise ValueError('Overlapping edits rejected')
            original=(original_root/path).read_text();lines=original.splitlines(True)
            for start,end,new in reversed(ranges): lines[start:end]=[new]
            try: ast.parse(''.join(lines),filename=path)
            except SyntaxError as error: raise ValueError(f'Candidate Python syntax rejected at line {error.lineno}: {error.msg}') from None
            patch+=''.join(difflib.unified_diff(original.splitlines(True),''.join(lines).splitlines(True),fromfile='a/'+path,tofile='b/'+path))
        result=self.propose(patch)
        return {**result,'patch':patch,'construction':'snapshot-edits-v2-line-boundaries','references':edits,'rendering':'A missing final replacement newline is supplied mechanically; source content is not repaired'}

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
            argv=['docker','run','--pull=never','--rm','--name',name,'--network=none','--read-only','--cap-drop=ALL',
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
                    timed_out=False
                    try:
                        result=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=max(1,min(timeout,120)),
                                              preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE,(RAW_OUTPUT_LIMIT,RAW_OUTPUT_LIMIT)))
                        returncode=result.returncode
                    except subprocess.TimeoutExpired:
                        timed_out=True
                        returncode=124
                    output,raw_output,output_exceeded=capture_output(stdout,stderr)
                    if timed_out and not output[1]: output[1]='Verification timed out'
                    requires_completion=bool(self.case.get('entry_lines'))
                    markers=re.findall(r'KAIROS_VERIFIER_RESULT (\{[^\n]+\})',output[0])
                    try: completion=json.loads(markers[-1]) if markers else None
                    except ValueError: completion=None
                    complete=bool(completion and completion.get('complete') is True and completion.get('tests_run',0)>0)
                    return {'passed':returncode==0 and not output_exceeded and (complete or not requires_completion),
                            'environment_error':returncode in {125,126,127} and completion is None,
                            'verification_complete':complete if requires_completion else None,
                            'verification_incomplete':requires_completion and not complete,
                            'tests_run':completion.get('tests_run') if completion else None,
                            'returncode':returncode,'stdout':output[0],'stderr':output[1],
                            'seconds':round(time.monotonic()-started,3),'output_limit_bytes':OUTPUT_TAIL_LIMIT,'output_truncated':any(len(value.encode())>=OUTPUT_TAIL_LIMIT for value in output),
                            'raw_output':raw_output,'output_limit_exceeded':output_exceeded,
                            'stop_reason':'output_limit_exceeded' if output_exceeded else ('timeout' if timed_out else 'check_completed')}
            finally:
                subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
