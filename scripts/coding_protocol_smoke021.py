"""Bounded base/adapter protocol sanity on two known training examples, not evaluation."""
import argparse
from contextlib import nullcontext
import importlib.metadata
import json
import os
import re
import shutil
from pathlib import Path
import time

from scripts.coding_inference020 import BASE, REVISION, paired_run, tokenize_cases, publish, sha
from scripts.coding_eval020 import GENERATION
from scripts.coding_train014 import admitted_inputs, read_bound, safe_path, verify_checkpoint
from scripts.source_edit_protocol021 import VERSION, training_messages


def package(corpus):
    if len(corpus['train']) != 2 or corpus.get('development') != []:
        raise ValueError('Protocol sanity requires exactly two admitted training examples')
    ids=[r['instance_id'] for r in corpus['train']]
    if len(set(ids)) != 2 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',name) for name in ids):
        raise ValueError('Distinct safe training identities required')
    return {'cases':[{'instance_id':r['instance_id'], 'messages':training_messages(r),
                     'source_handles':[s['source_id'] for s in r['input']['original_source']],
                     'context_available':True} for r in corpus['train']],
            'generation':GENERATION, 'scope':'Protocol sanity on known training examples only; not held-out evaluation or verified repair performance'}



def verify_inference_adapter(directory, receipt_sha, binding):
    """Verify exported inference bytes, never imply optimizer state is present."""
    receipt = read_bound(directory/'kairos-checkpoint.json', receipt_sha)
    if receipt.get('version') != 'coding-checkpoint014-v1' or receipt.get('binding') != binding:
        raise ValueError('Inference adapter training identity differs')
    names = {'adapter_config.json', 'adapter_model.safetensors'}
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('Inference adapter contains symlinks')
    observed = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if observed != names | {'kairos-checkpoint.json'}:
        raise ValueError('Inference adapter file set differs')
    for name in names:
        item = receipt.get('files', {}).get(name)
        path = safe_path(directory, name)
        if not item or path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('Inference adapter file bytes differ')
    return receipt


def run(args):
    if os.environ.get('KAIROS_PROTOCOL_SMOKE_GPU') != '1':
        raise RuntimeError('Protocol GPU execution requires explicit approval; no local fallback')
    if args.output.exists():
        raise RuntimeError('Prior smoke preserved; inspect it without redispatch')
    for path in [args.model_directory,args.adapter,args.output]:
        if path.is_symlink() or not path.resolve().is_relative_to(args.scratch_root.resolve()):
            raise ValueError('All GPU paths must stay in owned cloud scratch')
    owned=sum(p.stat().st_size for p in args.scratch_root.rglob('*') if p.is_file() and not p.is_symlink())
    if owned > 20*1024**3 or shutil.disk_usage(args.scratch_root).free < 4*1024**3:
        raise ValueError('Cloud scratch ceiling or free-space reserve failed')
    corpus, admission = admitted_inputs(args)
    train = read_bound(args.training_receipt,args.training_receipt_sha256)
    binding = train['binding']
    protocol_sha = sha(Path(__file__).with_name('source_edit_protocol021.py'))
    if (not train.get('run_complete') or binding.get('source_protocol') != VERSION
            or binding.get('source_protocol_sha256') != protocol_sha
            or binding.get('corpus_sha256') != args.corpus_sha256
            or binding.get('runner_sha256') != sha(Path(__file__).with_name('coding_train014.py'))
            or binding.get('model_manifest_sha256') != args.model_manifest_sha256):
        raise ValueError('Completed training/protocol binding differs')
    artifact_only = getattr(args, 'inference_artifact_only', False)
    verifier = verify_inference_adapter if artifact_only else verify_checkpoint
    verifier(args.adapter,args.checkpoint_receipt_sha256,binding)
    manifest = read_bound(args.model_manifest,args.model_manifest_sha256)
    if (manifest.get('model'),manifest.get('revision')) != (BASE,REVISION):
        raise ValueError('Pinned base model differs')
    observed={p.relative_to(args.model_directory).as_posix() for p in args.model_directory.rglob('*') if p.is_file()}
    if observed != set(manifest['files']): raise ValueError('Model file membership differs')
    for name,item in manifest['files'].items():
        p=safe_path(args.model_directory,name)
        if p.stat().st_size != item['bytes'] or sha(p) != item['sha256']:
            raise ValueError('Model file bytes differ')
    runtime={n:importlib.metadata.version(n) for n in ['torch','transformers','peft','accelerate','bitsandbytes']}
    if runtime != manifest['training_environment']: raise ValueError('Training/inference runtime differs')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM,set_seed
    from peft import PeftModel
    if not torch.cuda.is_available() or torch.cuda.get_device_properties(0).total_memory < 14*1024**3:
        raise RuntimeError('CUDA with at least 14GiB required; no CPU/Mac fallback')
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_directory),local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    study=package(corpus)
    cases=tokenize_cases(study,lambda messages:tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True))
    base=AutoModelForCausalLM.from_pretrained(str(args.model_directory),local_files_only=True,trust_remote_code=False,use_safetensors=True,device_map={'':0},torch_dtype=torch.float16,attn_implementation='sdpa')
    for p in base.parameters():
        if p.ndim==1 and p.dtype in (torch.float16,torch.bfloat16):p.data=p.data.to(torch.float32)
    model=PeftModel.from_pretrained(base,str(args.adapter),is_trainable=False,local_files_only=True,use_safetensors=True)
    model.eval();model.gradient_checkpointing_disable()
    if any(p.requires_grad or p.device.type!='cuda' for p in model.parameters()):
        raise RuntimeError('Trainable parameters or CPU offload outside the inference profile')
    identity={'version':'coding-protocol-smoke021-v1','source_protocol':VERSION,'source_protocol_sha256':protocol_sha,
              'runner_sha256':sha(__file__),'corpus_sha256':args.corpus_sha256,'training_receipt_sha256':args.training_receipt_sha256,
              'checkpoint_receipt_sha256':args.checkpoint_receipt_sha256,'admission':admission,'runtime':runtime,'generation':GENERATION,
              'scope':study['scope'],'maximum_calls':4,'inference_precision':'cuda-fp16-autocast021-v1','adapter_verification':'inference-artifact021-v1' if artifact_only else 'complete-checkpoint014-v1','error_diagnostics':'bounded-private021-v1','gpu':torch.cuda.get_device_name(0),
              'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,'cuda_runtime':torch.version.cuda}
    def generate(case,arm):
        set_seed(42);torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
        ids=torch.tensor([case['input_token_ids']],device='cuda');started=time.monotonic()
        # Match training autocast so FP32 norms can feed the FP16 output layer.
        with (model.disable_adapter() if arm=='base' else nullcontext()),torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):
            values=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),do_sample=False,max_new_tokens=1024,max_time=180,pad_token_id=tokenizer.pad_token_id,eos_token_id=tokenizer.eos_token_id,use_cache=True)
        tokens=values[0,ids.shape[1]:].tolist();eos=bool(tokens and tokens[-1]==tokenizer.eos_token_id)
        return {'text':tokenizer.decode(tokens,skip_special_tokens=True),'output_token_ids':tokens,'output_tokens':len(tokens),
                'ended_with_eos':eos,'stop_reason':'eos' if eos else 'budget_or_time_limit','generation_seconds':time.monotonic()-started,
                'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
    result=paired_run(study,cases,args.output,identity,generate,capture_error_details=True)
    publish(args.output/'scope.json',{'version':'protocol-sanity-scope021-v1','known_training_examples':True,'repair_effectiveness_verified':False,'maximum_calls':4})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['corpus','admission-directory','model-directory','model-manifest','adapter','training-receipt','scratch-root','output']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['corpus-sha256','admission-index-sha256','model-manifest-sha256','training-receipt-sha256','checkpoint-receipt-sha256']:p.add_argument('--'+name,required=True)
    p.add_argument('--inference-artifact-only',action='store_true',help='Verify only the exported adapter against its original checkpoint receipt; no training resume')
    a=p.parse_args();a.study='resource2';a.profile='14B';a.action='doctor';a.source_protocol='shared021'
    print(json.dumps(run(a)))


if __name__=='__main__':main()
