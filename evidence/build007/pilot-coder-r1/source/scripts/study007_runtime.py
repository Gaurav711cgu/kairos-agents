"""Portable study locations, immutable receipts and owned local inference."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
CAPACITY=6*1024**3
RESERVE=4*1024**3


def sha(path):
    with Path(path).open('rb') as source: return hashlib.file_digest(source,'sha256').hexdigest()


def save(path,value,immutable=False,private=False):
    path=Path(path); raw=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
    if path.exists() and immutable:
        if path.read_bytes()!=raw: raise ValueError('Frozen receipt differs: '+path.name)
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink(): raise ValueError('Receipt path is a symlink')
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if private: temporary.chmod(0o600)
    temporary.replace(path)


def locations(args):
    state=Path(args.runtime or ROOT/'.runtime/study007').resolve()
    cache=Path(args.model_cache or ROOT/'.runtime/investigations').resolve()
    return {'root':ROOT,'state':state,'cache':cache,
            'dataset':Path(args.dataset or cache/'study004/records.json').resolve(),
            'cases':Path(args.case_root or state/'verification').resolve(),
            'environment':Path(args.environment_file or state/'environment.json').resolve(),
            'out':ROOT/'evidence/build007'}


def storage_guard(paths,projected=0):
    roots=sorted(set([paths['cache'],paths['state']]),key=lambda p:len(p.parts))
    unique=[p for i,p in enumerate(roots) if not any(p.is_relative_to(old) for old in roots[:i])]
    size=sum(p.stat().st_size for root in unique for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    anchor=next((p for p in unique if p.exists()),ROOT)
    free=shutil.disk_usage(anchor).free
    if size+projected>CAPACITY or free-projected<RESERVE:
        raise ValueError('Study exceeds 6GiB persistent budget or 4GiB free reserve')
    return {'owned_bytes':size,'free_bytes':free,'budget_bytes':CAPACITY,'reserve_bytes':RESERVE}


def profile(name):
    if name not in {'qwen3','coder'}: raise ValueError('Unknown pinned model profile')
    value=json.loads((ROOT/f'evidence/build004/inference-{name}-mac.json').read_text())
    if value['settings'].get('context')!=4096 or value['settings'].get('max_output_tokens')!=1024 or value['settings'].get('parallel')!=1:
        raise ValueError('Pinned profile does not match v7')
    return value


def verify_model(paths,name):
    value=profile(name)
    for item in value['files']:
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Invalid model manifest path')
        file=paths['cache']/relative
        if file.is_symlink() or not file.is_file() or file.stat().st_size!=item['bytes'] or sha(file)!=item['sha256']:
            raise ValueError('Pinned runtime/model hash mismatch: '+item['path'])
    with tarfile.open(paths['cache']/'runtime/llama.tar.gz') as archive:
        for item in archive.getmembers():
            if not item.isfile(): continue
            relative=Path(item.name)
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('Invalid runtime archive path')
            file=paths['cache']/'runtime'/relative
            with archive.extractfile(item) as stream: expected=hashlib.file_digest(stream,'sha256').hexdigest()
            if file.is_symlink() or not file.is_file() or sha(file)!=expected: raise ValueError('Extracted runtime hash mismatch')
    return value


def load_environment(paths):
    path=paths['environment']
    if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:
        raise ValueError('Private environment JSON must be a regular mode0600 file')
    data=json.loads(path.read_text())
    allowed={'DATABASE_URL','TEST_DATABASE_URL','KAIROS_MIGRATION_DATABASE_URL','KAIROS_BLOB_DIR'}
    if not isinstance(data,dict) or not data.get('DATABASE_URL') or set(data)-allowed:
        raise ValueError('Private environment contains unsupported keys')
    os.environ.update(data)
    os.environ['KAIROS_BLOB_DIR']=str(paths['state']/'blobs')
    return data


def source_manifest():
    files=list((ROOT/'kairos_api').rglob('*.py'))+list((ROOT/'kairos_api/migrations').glob('*.sql'))
    files+=list((ROOT/'scripts').glob('study007*.py'))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}


def start_model(paths,name):
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        raise RuntimeError('Pinned inference binary requires macOS ARM64; no provider substitution')
    value=verify_model(paths,name); storage_guard(paths)
    with httpx.Client(timeout=1,trust_env=False) as client:
        try: client.get('http://127.0.0.1:8130/health')
        except httpx.HTTPError: pass
        else: raise RuntimeError('Inference port occupied; existing process preserved')
    paths['state'].mkdir(parents=True,exist_ok=True)
    model=next(item['path'] for item in value['files'] if item['path'].endswith('.gguf'))
    argv=[str(paths['cache']/'runtime/llama-b11552/llama-server'),'--model',str(paths['cache']/model),
          '--host','127.0.0.1','--port','8130','--ctx-size','4096','--parallel','1','--threads','4',
          '--n-predict','1024','--jinja','--no-webui']
    log=(paths['state']/f'model-{name}.log').open('ab')
    process=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    identity={'pid':process.pid,'argv':argv,'profile':name}
    save(paths['state']/'model-process.json',identity,private=True)
    try:
        with httpx.Client(timeout=2,trust_env=False) as client:
            for _ in range(60):
                if process.poll() is not None: raise RuntimeError('Pinned inference exited; private log retained')
                try:
                    if client.get('http://127.0.0.1:8130/health').status_code==200: return process,log
                except httpx.HTTPError: pass
                time.sleep(1)
        raise TimeoutError('Inference startup exceeded sixty seconds')
    except BaseException:
        finish_model(process,log); raise


def finish_model(process,log):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=20)
        except subprocess.TimeoutExpired: process.kill();process.wait(timeout=10)
    log.close()


def stop(paths):
    record=paths['state']/'model-process.json'
    if not record.exists(): return {'stopped':False,'reason':'No owned inference receipt'}
    value=json.loads(record.read_text())
    result=subprocess.run(['ps','-p',str(value['pid']),'-o','command='],capture_output=True,text=True)
    if result.returncode: return {'stopped':False,'reason':'Owned process already exited'}
    if result.stdout.strip()!=' '.join(value['argv']):
        raise RuntimeError('Process identity changed; preserved unrelated process')
    os.kill(value['pid'],15)
    return {'stopped':True,'scope':'Owned inference only; databases and historical data preserved'}
