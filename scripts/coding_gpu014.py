"""Read-only GPU inventory for a future coding-adapter resource pilot."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess

MODEL='Qwen/Qwen2.5-Coder-1.5B-Instruct'
REVISION='2e1fd397ee46e1388853d2af2c993145b0f1098a'


def gpu_rows(text):
    rows=[]
    for line in text.splitlines():
        fields=[field.strip() for field in line.split(',')]
        if len(fields)!=4 or not fields[0] or any(not fields[i].isdigit() for i in (1,2)):
            raise ValueError('Incomplete NVIDIA resource inventory')
        total,free=int(fields[1]),int(fields[2])
        if not 0<=free<=total or not total:raise ValueError('Invalid GPU memory measurements')
        rows.append({'name':fields[0],'total_memory_mib':total,'free_memory_mib':free,'driver':fields[3]})
    if not rows:raise ValueError('No GPU reported')
    return rows


def inventory(run=subprocess.run,disk=shutil.disk_usage):
    packages={}
    for name in ['torch','transformers','peft','trl','bitsandbytes','safetensors','accelerate']:
        try:packages[name]=metadata.version(name)
        except metadata.PackageNotFoundError:packages[name]=None
    try:
        result=run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,check=False)
        if result.returncode:raise ValueError('NVIDIA inventory command failed')
        gpus=gpu_rows(result.stdout);failure=None
    except (OSError,subprocess.SubprocessError,ValueError) as error:
        gpus=[];failure=type(error).__name__
    scratch=disk(Path.cwd())
    return {'version':'coding-gpu-inventory014-v1','python':platform.python_version(),
            'system':platform.system(),'architecture':platform.machine(),'packages':packages,'gpus':gpus,
            'gpu_inventory_failure_type':failure,'scratch_total_bytes':scratch.total,'scratch_free_bytes':scratch.free,
            'candidate_model':MODEL,'candidate_revision':REVISION,'weights_downloaded_by_this_command':False,
            'packages_installed_by_this_command':False,'dataset_uploaded_by_this_command':False,
            'training_started':False,'resource_fit_verified':False,'scratch_allocation_admitted':False,
            'next_gate':'Independently qualified training/development data, bounded scratch admission, then 20 actual forward/backward steps with measured 15% VRAM headroom and resume verification',
            'scope':'Hardware/package inventory only. Device capacity does not prove QLoRA fit, free-tier entitlement or repair improvement.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();value=inventory();raw=json.dumps(value,indent=2)+'\n'
    if args.output:
        with args.output.open('x') as stream:stream.write(raw)
    print(raw,end='')


if __name__=='__main__':main()
