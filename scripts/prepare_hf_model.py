"""Verify a frozen training export and prepare a minimal adapter release.

No weights are loaded and no network request is made. The original export stays
unchanged; a new output directory records hashes for its derived public files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUT=ROOT/'dist/kairos-14b-qlora'
ARCHIVE_SHA256='55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b'
BASE_MODEL='unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
PREFIX='runs/public100/checkpoint-40/'
PUBLIC_FILES={'adapter_model.safetensors','adapter_config.json','README.md'}
MODEL_CARD_TEMPLATE='''---
base_model: unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit
library_name: peft
pipeline_tag: text-generation
tags:
- qlora
- repository-analysis
---

# Kairos coding adapter

This release contains a QLoRA adapter over a frozen Qwen2.5-Coder-14B base,
trained for 40 optimizer updates on 100 public issue/patch examples. The base
revision is ecfc63c083900ce4f19daad695e711f38ab98fcf; 6,291,456 adapter
parameters were trainable. Source and derived artifact identities are recorded
in release-manifest.json. The base weights and private account state are not
included.

## Evaluation scope

The historical 15-case graph diagnostic used annotated caller seeds and an
index not bound to case base revisions. It is not an end-to-end repair score.
The development grounding narrative conflicts with its scored fields and is
not used as an effectiveness claim. This adapter has no established repair
improvement on the untouched evaluation set. The 100 public training examples
must not be described as 100 independently reproduced repairs.

A separate two-example resource pilot recorded matching checkpoint state after
interruption/resumption. That result applies to its tested recipe and does not
establish general fault tolerance or an energy-efficiency result.

## Use

Load with PEFT over the pinned quantized base in a compatible GPU runtime.
Supply repository context and validate emitted actions and patches before
execution. This package is an experimental research artifact, not a guarantee
of correct edits. Do not execute model-generated code outside the verification
sandbox. No model is loaded or inference run by the packaging command.
'''


def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def verify_export(path, expected):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not re.fullmatch('[a-f0-9]{64}',expected):
        raise ValueError('Unsafe archive or digest')
    if path.stat().st_size>100*1024**2 or sha(path)!=expected:
        raise ValueError('Training export size or digest differs')
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();names=[e.filename for e in entries]
        if len(entries)>512 or len(names)!=len(set(names)) or sum(e.file_size for e in entries)>256*1024**2:
            raise ValueError('Export membership or decompression bound exceeded')
        for e in entries:
            p=PurePosixPath(e.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in e.filename or e.is_dir() or stat.S_ISLNK(e.external_attr>>16):
                raise ValueError('Unsafe export member')
        if archive.getinfo('manifest.json').file_size>1024**2:raise ValueError('Oversized export manifest')
        manifest=json.loads(archive.read('manifest.json'))
        if (manifest.get('version')!='coding-real-train014-full100-export-v1'
                or manifest.get('contains_base_weights') is not False
                or manifest.get('full_corpus_training_complete') is not True
                or manifest.get('training_rows')!=100 or manifest.get('training_steps')!=40
                or set(names)!=set(manifest['files'])|{'manifest.json'}):
            raise ValueError('Unexpected training export identity')
        for name,item in manifest['files'].items():
            if archive.getinfo(name).file_size!=item['bytes']:raise ValueError('Member size differs')
            with archive.open(name) as source:
                if hashlib.file_digest(source,'sha256').hexdigest()!=item['sha256']:raise ValueError('Member hash differs')
        required={PREFIX+'adapter_model.safetensors',PREFIX+'adapter_config.json','runs/public100/receipt.json'}
        if not required<=set(names):raise ValueError('Trained adapter or receipt missing')
        receipt=json.loads(archive.read('runs/public100/receipt.json'))
        if receipt.get('completed_steps')!=40 or receipt.get('run_complete') is not True or receipt.get('adapter_updated') is not True:
            raise ValueError('Training completion receipt is invalid')
        return manifest


def verify_bundle(directory):
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('Unsafe bundle directory')
    manifest_path=directory/'release-manifest.json'
    if manifest_path.is_symlink():raise ValueError('Unsafe bundle manifest')
    manifest=json.loads(manifest_path.read_text())
    if manifest.get('version')!='coding-adapter-release020-v1' or set(manifest.get('files',{}))!=PUBLIC_FILES:
        raise ValueError('Unexpected release manifest')
    if {p.name for p in directory.iterdir()}!=PUBLIC_FILES|{'release-manifest.json'}:
        raise ValueError('Bundle contains unselected files')
    for name,item in manifest['files'].items():
        path=directory/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
            raise ValueError('Release artifact changed')
    config=json.loads((directory/'adapter_config.json').read_text())
    if config.get('base_model_name_or_path')!=BASE_MODEL:raise ValueError('Base model identity differs')
    return manifest


def prepare_bundle(zip_path, out_dir, repo_id='username/kairos-14b-qlora', *, expected_sha256=ARCHIVE_SHA256):
    zip_path,out_dir=Path(zip_path),Path(out_dir)
    if out_dir.exists():raise ValueError('Preserve existing release directory; choose a new output')
    verify_export(zip_path,expected_sha256)
    out_dir.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        # Update adapter_config.json to reference canonical base model
        config=json.loads(archive.read(PREFIX+'adapter_config.json'))
        config['base_model_name_or_path']=BASE_MODEL
        (out_dir/'adapter_config.json').write_text(json.dumps(config,indent=2)+'\n')
        with archive.open(PREFIX+'adapter_model.safetensors') as source, (out_dir/'adapter_model.safetensors').open('xb') as target:
            while data:=source.read(1024**2):target.write(data)
    # Write Model Card README.md
    (out_dir/'README.md').write_text(MODEL_CARD_TEMPLATE)
    manifest={'version':'coding-adapter-release020-v1','source_archive_sha256':expected_sha256,
        'base_model':BASE_MODEL,'base_revision':'ecfc63c083900ce4f19daad695e711f38ab98fcf',
        'derived_config_change':'base_model_name_or_path replaced with pinned public model identifier',
        'repair_effectiveness_verified':False,'published':False,
        'files':{name:{'bytes':(out_dir/name).stat().st_size,'sha256':sha(out_dir/name)} for name in sorted(PUBLIC_FILES)}}
    (out_dir/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    verify_bundle(out_dir)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip-path',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    result=prepare_bundle(args.zip_path,args.out_dir)
    print(json.dumps({'prepared':True,'published':False,'files':sorted(result['files'])}))


if __name__=='__main__':main()
