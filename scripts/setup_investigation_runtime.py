"""Install and verify the pinned official macOS ARM64 inference runtime locally."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'.runtime/investigations'
FILES=[
 ('runtime/llama.tar.gz',12086252,'f4b33fe40d098033fb1a19a8a4a84383c4ca84c37b6a60d9f9a253f349b48c07','https://github.com/ggml-org/llama.cpp/releases/download/b11552/llama-b11552-bin-macos-arm64.tar.gz'),
 ('models/Qwen3-1.7B-Q8_0.gguf',1834426016,'061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a','https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf?download=true'),
]


def file_hash(path):
    with path.open('rb') as source: return hashlib.file_digest(source,'sha256').hexdigest()


def setup():
    if platform.system()!='Darwin' or platform.machine()!='arm64':
        raise RuntimeError('Pinned binary targets macOS ARM64. No automatic runtime/provider substitution.')
    RUNTIME.mkdir(parents=True,exist_ok=True)
    for name,size,expected,url in FILES:
        target=RUNTIME/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            if shutil.disk_usage(RUNTIME).free<size+4*1024**3: raise RuntimeError('Download would violate the 4GiB free-space reserve')
            partial=target.with_suffix('.partial');written=0
            with urllib.request.urlopen(url,timeout=90) as response,partial.open('wb') as output:
                while chunk:=response.read(4*1024*1024):
                    written+=len(chunk)
                    if written>size: raise ValueError('Download exceeds pinned size')
                    output.write(chunk)
                output.flush();os.fsync(output.fileno())
            if written!=size or file_hash(partial)!=expected: raise ValueError('Download hash/size mismatch')
            partial.replace(target)
        if target.stat().st_size!=size or file_hash(target)!=expected: raise ValueError('Pinned runtime/model hash mismatch: '+name)
    binary=RUNTIME/'runtime/llama-b11552/llama-server'
    with tarfile.open(RUNTIME/'runtime/llama.tar.gz') as archive:
        if not binary.exists(): archive.extractall(RUNTIME/'runtime',filter='data')
        for member in archive.getmembers():
            if not member.isfile(): continue
            target=RUNTIME/'runtime'/member.name
            stream=archive.extractfile(member)
            expected=hashlib.file_digest(stream,'sha256').hexdigest()
            if not target.is_file() or file_hash(target)!=expected: raise ValueError('Extracted runtime file changed: '+member.name)
    version=subprocess.check_output([str(binary),'--version'],text=True,stderr=subprocess.STDOUT).strip()
    receipt={'passed':True,'runtime_version':version,'binary_sha256':file_hash(binary),
             'model_sha256':FILES[1][2],'model_revision':'90862c4b9d2787eaed51d12237eafdfe7c5f6077',
             'context_tokens':4096,'parallel':1,'threads':4,'api_spend_usd':0,
             'runtime_bytes':sum(p.stat().st_size for p in RUNTIME.rglob('*') if p.is_file() and not p.is_symlink()),
             'free_bytes':shutil.disk_usage(RUNTIME).free}
    output=ROOT/'evidence/build003/runtime-verification.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    return binary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');args=parser.parse_args()
    binary=setup()
    if args.serve:
        os.chdir(ROOT)
        argv=[str(binary),'--model',str(RUNTIME/'models/Qwen3-1.7B-Q8_0.gguf'),'--host','127.0.0.1','--port','8130',
              '--ctx-size','4096','--parallel','1','--threads','4','--n-predict','1024','--jinja','--no-webui']
        os.execv(argv[0],argv)
    print('Pinned model, binary and extracted runtime files verified. Use --serve to start port 8130.')

if __name__=='__main__': main()
