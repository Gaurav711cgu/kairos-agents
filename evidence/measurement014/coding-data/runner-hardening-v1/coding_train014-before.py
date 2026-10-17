"""Offline QLoRA runner for an explicitly frozen, admitted coding corpus."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import shutil

MODELS={
 '7B':('unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit','4858886f896bd05db823557fc5cbc4ac28342af7'),
 '14B':('unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit','ecfc63c083900ce4f19daad695e711f38ab98fcf'),
}


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def safe_path(root,name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or name!=p.as_posix() or any(x in {'','..','.'} for x in name.split('/')) or '\\' in name:
        raise ValueError('Unsafe package path')
    path=root.joinpath(*p.parts)
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Package paths must not contain symlinks')
    return path


def read_bound(path,expected,maximum=16*1024**2):
    if any(p.is_symlink() for p in [path,*path.parents]) or not path.is_file() or path.stat().st_size>maximum or sha_file(path)!=expected:
        raise ValueError('Frozen input hash, size or path differs')
    return json.loads(path.read_bytes())


def admit_corpus(data):
    if data.get('version')!='coding-admitted-corpus014-v1' or data.get('training_ready') is not True:
        raise ValueError('An admitted, frozen coding corpus is required before fitting')
    if data.get('exposure_inventory_sha256')!='df992139ab624087f6141eb8401e78294ff6bcb203dfb76c3ab22e0bbfed6957':
        raise ValueError('Current frozen exposure inventory is required')
    rows=data['train'];development=data['development'];evaluation=data['locked_evaluation_families']
    if not 200<=len(rows)<=500 or len(development)!=6 or len(evaluation)!=30:
        raise ValueError('Corpus must contain 200-500 training repairs, six development and thirty locked evaluation families')
    repositories=Counter(row['repository'] for row in rows)
    if len(repositories)<5 or max(repositories.values())*4>len(rows):raise ValueError('Training repository diversity/cap fails')
    families=[];targets=set()
    for row in [*rows,*development]:
        if row.get('admission')!={'independent_checks':True,'rights_reviewed':True,'family_resolved':True,'near_deduplicated':True,'action_replayed':True}:
            raise ValueError('Every example requires complete offline admission')
        if not all(isinstance(row.get(k),str) and len(row[k])==64 and all(c in '0123456789abcdef' for c in row[k]) for k in ['qualification_receipt_sha256','rights_receipt_sha256','family_receipt_sha256']):
            raise ValueError('Admission receipt identities are missing')
        if set(row['input'])!={'issue','original_source','instruction'}:raise ValueError('Unexpected model input fields')
        blocks=row['input']['original_source']
        if not row['input']['issue'].strip() or not isinstance(blocks,list) or not 1<=len(blocks)<=4:
            raise ValueError('Complete original-source context is required')
        references={}
        for block in blocks:
            handle=block['source_id']
            if not re.fullmatch(r'S[a-f0-9]{12}',handle) or handle in references or not block['numbered_original_source']:
                raise ValueError('Invalid or duplicated captured source handle')
            safe_path(Path('/source'),block['path'])
            start,end=block['start_line'],block['end_line']
            if type(start) is not int or type(end) is not int or not 1<=start<=end<=start+79:
                raise ValueError('Captured source range is invalid')
            lines=block['numbered_original_source'].splitlines()
            if len(lines)!=end-start+1 or any(not line.startswith(str(n)+': ') for n,line in enumerate(lines,start)):
                raise ValueError('Captured original lines differ from their declared bounds')
            references[handle]=block
        if row['repository'] in {'psf/requests','sympy/sympy'}:raise ValueError('Evaluation repository leaked into training/development')
        from kairos_api.investigations.contracts import ActionV7
        ActionV7.validate_python(row['assistant_target'])
        if row['assistant_target']['action']!='propose_patch':raise ValueError('Only complete source-edit targets are admitted')
        for edit in row['assistant_target']['edits']:
            block=references.get(edit['source_id'])
            if block is None or not block['start_line']<=edit['start_line']<=edit['end_line']<=block['end_line']:
                raise ValueError('Training edit escapes captured source')
        signature=hashlib.sha256(encoded(row['assistant_target'])).hexdigest()
        if signature in targets:raise ValueError('Duplicate structured target')
        targets.add(signature);families.append(row['family_id'])
    if len(families)!=len(set(families)) or set(families)&set(evaluation) or len(set(evaluation))!=30:
        raise ValueError('Issue-family split overlap or duplication')
    return data


def tokenize_example(tokenizer,row,maximum=2048):
    """Mask the exact user/system prefix; reject truncation or template drift."""
    messages=[{'role':'system','content':'Repair Python source using captured original-source handles. Return one JSON edit action.'},
              {'role':'user','content':encoded(row['input']).decode()}]
    prefix=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
    full=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':encoded(row['assistant_target']).decode()}],tokenize=True,add_generation_prompt=False)
    if full[:len(prefix)]!=prefix or len(full)<=len(prefix):raise ValueError('Chat template does not preserve an exact supervised suffix')
    if len(full)>maximum:raise ValueError('Complete input and target exceed sequence budget; no truncation allowed')
    return {'input_ids':full,'attention_mask':[1]*len(full),'labels':[-100]*len(prefix)+full[len(prefix):]}


def checkpoint_receipt(directory,binding):
    files={}
    for path in sorted(directory.rglob('*')):
        if path.name=='kairos-checkpoint.json':continue
        if path.is_symlink():raise ValueError('Checkpoint must not contain symlinks')
        if path.is_file():files[path.relative_to(directory).as_posix()]={'sha256':sha_file(path),'bytes':path.stat().st_size}
    receipt={'version':'coding-checkpoint014-v1','binding':binding,'files':files}
    target=directory/'kairos-checkpoint.json'
    with target.open('xb') as stream:
        stream.write(encoded(receipt));stream.flush();os.fsync(stream.fileno())
    return receipt


def verify_checkpoint(directory,receipt_sha,binding):
    receipt=read_bound(directory/'kairos-checkpoint.json',receipt_sha)
    if receipt.get('version')!='coding-checkpoint014-v1' or receipt['binding']!=binding or not receipt['files']:
        raise ValueError('Checkpoint experiment identity differs')
    if any(p.is_symlink() for p in directory.rglob('*')):raise ValueError('Checkpoint contains symlinks')
    observed={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and p.name!='kairos-checkpoint.json'}
    if observed!=set(receipt['files']):raise ValueError('Checkpoint file set differs')
    for name,item in receipt['files'].items():
        path=safe_path(directory,name)
        if path.stat().st_size!=item['bytes'] or sha_file(path)!=item['sha256']:raise ValueError('Checkpoint file bytes differ')
    return receipt


def admit_pilot(pilot,binding):
    expected={k:v for k,v in binding.items() if k!='planned_steps'}
    if (pilot.get('version')!='coding-pilot-acceptance014-v1' or pilot.get('identity')!=expected
            or pilot.get('resource_fit_verified') is not True or pilot.get('resume_equivalence_verified') is not True
            or not re.fullmatch(r'[a-f0-9]{64}',str(pilot.get('comparison_receipt_sha256','')))):
        raise ValueError('Full training requires measured fit and verified checkpoint-resume equivalence')


def adapter_options():
    return {'r':8,'lora_alpha':16,'lora_dropout':0.05,'target_modules':['q_proj','v_proj'],'bias':'none','task_type':'CAUSAL_LM'}


def trainer_options(output,steps,learning_rate,*,fixture_cpu=False):
    """The CPU option is for tiny isolated tests; run() always requires CUDA."""
    return {'output_dir':str(output),'per_device_train_batch_size':1,'gradient_accumulation_steps':8,
            'max_steps':steps,'learning_rate':learning_rate,'fp16':not fixture_cpu,'use_cpu':fixture_cpu,
            'optim':'adamw_torch','gradient_checkpointing':True,'logging_steps':1,'logging_nan_inf_filter':False,
            'save_strategy':'steps','save_steps':10,'save_total_limit':None,'report_to':'none','push_to_hub':False,
            'seed':42,'data_seed':42,'dataloader_num_workers':0,'dataloader_pin_memory':False,
            'remove_unused_columns':False,'save_safetensors':True}


def run(args):
    # Admission and all byte checks precede CUDA allocation or model loading.
    corpus=admit_corpus(read_bound(args.corpus,args.corpus_sha256))
    model_manifest=read_bound(args.model_manifest,args.model_manifest_sha256)
    if (model_manifest.get('model'),model_manifest.get('revision'))!=MODELS[args.profile]:raise ValueError('Pinned model identity differs')
    if model_manifest.get('quantization')!='nf4-double-quant':raise ValueError('Reviewed NF4 derivative is required')
    observed={p.relative_to(args.model_directory).as_posix() for p in args.model_directory.rglob('*') if p.is_file()}
    if observed!=set(model_manifest['files']):raise ValueError('Model file set differs from the frozen manifest')
    for name,item in model_manifest['files'].items():
        path=safe_path(args.model_directory,name)
        if path.stat().st_size!=item['bytes'] or sha_file(path)!=item['sha256']:raise ValueError('Local model file differs')
    if not model_manifest['files'] or not any(n.endswith('.safetensors') for n in model_manifest['files']):raise ValueError('Safe model weights missing')
    if args.output.exists():raise ValueError('Output must be new; preserve previous attempts')
    if not args.model_directory.resolve().is_relative_to(args.scratch_root.resolve()) or not args.output.resolve().is_relative_to(args.scratch_root.resolve()):raise ValueError('Weights and output must be in counted cloud scratch')
    def scratch_guard():
        owned=sum(p.stat().st_size for p in args.scratch_root.rglob('*') if p.is_file() and not p.is_symlink())
        if owned>args.scratch_bytes or shutil.disk_usage(args.scratch_root).free<4*1024**3:raise ValueError('Cloud scratch limit or free-space reserve failed')
    scratch_guard()
    args.output.mkdir(parents=True,mode=0o700);args._owned_output_created=True
    (args.output/'intent.json').write_bytes(encoded({'version':'coding-training-intent014-v1','action':args.action,'profile':args.profile,'corpus_sha256':args.corpus_sha256,'model_manifest_sha256':args.model_manifest_sha256}))
    os.environ.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',WANDB_DISABLED='true',CUBLAS_WORKSPACE_CONFIG=':4096:8',
                      HF_HOME=str(args.scratch_root/'hf-cache'),TORCH_HOME=str(args.scratch_root/'torch-cache'),
                      XDG_CACHE_HOME=str(args.scratch_root/'xdg-cache'),CUDA_CACHE_PATH=str(args.scratch_root/'cuda-cache'))
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer,Trainer,TrainerCallback,TrainingArguments,DataCollatorForSeq2Seq,set_seed
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    if not torch.cuda.is_available():raise ValueError('Actual CUDA GPU required; no Mac/CPU training fallback')
    runtime={n:importlib.metadata.version(n) for n in ['torch','transformers','peft','accelerate','bitsandbytes']}
    if runtime!=model_manifest['training_environment']:raise ValueError('Frozen training environment differs')
    steps=20 if args.action=='fit' else min(500,len(tokenized)//8)
    binding={'corpus_sha256':args.corpus_sha256,'model_manifest_sha256':args.model_manifest_sha256,'profile':args.profile,'runtime':runtime,'runner_sha256':sha_file(Path(__file__)),'learning_rate':args.learning_rate,'planned_steps':steps,'seed':42,'max_sequence':2048,'gradient_accumulation':8,'gpu':torch.cuda.get_device_name(0),'cuda_runtime':torch.version.cuda,'compute_capability':list(torch.cuda.get_device_capability(0))}
    if args.resume_checkpoint:
        if not args.resume_receipt_sha256:raise ValueError('Resume requires the exact checkpoint receipt hash')
        verify_checkpoint(args.resume_checkpoint,args.resume_receipt_sha256,binding)
    if args.action=='train':
        pilot=read_bound(args.pilot_evidence,args.pilot_evidence_sha256)
        admit_pilot(pilot,binding)
    set_seed(42);torch.use_deterministic_algorithms(True)
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_directory),local_files_only=True,trust_remote_code=False)
    if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
    tokenized=[tokenize_example(tokenizer,row) for row in corpus['train']]
    # Load the already reviewed quantized artifact, without quantizing another base.
    model=AutoModelForCausalLM.from_pretrained(str(args.model_directory),local_files_only=True,trust_remote_code=False,use_safetensors=True,device_map={'':0},torch_dtype=torch.float16)
    quantization=getattr(model.config,'quantization_config',{})
    if not getattr(model,'is_loaded_in_4bit',False) or quantization.get('bnb_4bit_quant_type')!='nf4' or quantization.get('bnb_4bit_use_double_quant') is not True:raise ValueError('Actual quantized model differs from the frozen NF4 profile')
    for module in model.modules():
        if hasattr(module,'compute_dtype'):module.compute_dtype=torch.float16
    model.config.use_cache=False
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model=get_peft_model(model,LoraConfig(**adapter_options()))
    trainable=[(name,p) for name,p in model.named_parameters() if p.requires_grad]
    if not trainable or any('lora_' not in name for name,_ in trainable):raise ValueError('Only adapter weights may be trainable')
    measured=[]
    class Capture(TrainerCallback):
        def on_log(self,args_,state,control,logs=None,**kwargs):
            if logs:
                for key in ['loss','grad_norm']:
                    if key in logs and not math.isfinite(float(logs[key])):raise ValueError('Nonfinite training loss or gradient')
                measured.append({'step':state.global_step,**{k:float(logs[k]) for k in ['loss','grad_norm'] if k in logs}})
                with (args.output/'metrics.jsonl').open('a') as stream:stream.write(json.dumps(measured[-1])+'\n');stream.flush();os.fsync(stream.fileno())
        def on_save(self,args_,state,control,**kwargs):
            checkpoint_receipt(args.output/('checkpoint-'+str(state.global_step)),binding);scratch_guard()
        def on_step_end(self,args_,state,control,**kwargs):
            if args.stop_after and state.global_step>=args.stop_after:control.should_save=True;control.should_training_stop=True
            return control
    training_args=TrainingArguments(**trainer_options(args.output,steps,args.learning_rate))
    trainer=Trainer(model=model,args=training_args,train_dataset=tokenized,data_collator=DataCollatorForSeq2Seq(tokenizer,model=None,padding='max_length',max_length=2048,label_pad_token_id=-100),callbacks=[Capture()])
    torch.cuda.reset_peak_memory_stats();trainer.train(resume_from_checkpoint=str(args.resume_checkpoint) if args.resume_checkpoint else None)
    torch.cuda.synchronize();peak=torch.cuda.max_memory_reserved();total=torch.cuda.get_device_properties(0).total_memory
    complete=trainer.state.global_step==steps
    receipt={'version':'coding-training-run014-v1','binding':binding,'completed_steps':trainer.state.global_step,'planned_steps':steps,'run_complete':complete,'trainable_parameters':sum(p.numel() for _,p in trainable),'gpu':torch.cuda.get_device_name(0),'peak_reserved_bytes':peak,'gpu_total_bytes':total,'vram_headroom_fraction':1-peak/total,'finite_logged_loss':any('loss' in r for r in measured),'nonzero_logged_gradient':any(r.get('grad_norm',0)>0 for r in measured),'resource_fit_verified':False,'resume_equivalence_verified':False,'repair_effectiveness_verified':False}
    receipt['resource_fit_verified']=bool(complete and args.action=='fit' and receipt['finite_logged_loss'] and receipt['nonzero_logged_gradient'] and receipt['vram_headroom_fraction']>=0.15)
    (args.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');scratch_guard()
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['doctor','fit','train']);p.add_argument('--profile',choices=MODELS,default='14B')
    for name in ['corpus','model-manifest','model-directory','output','scratch-root','resume-checkpoint','pilot-evidence']:p.add_argument('--'+name,type=Path)
    for name in ['corpus-sha256','model-manifest-sha256','resume-receipt-sha256','pilot-evidence-sha256']:p.add_argument('--'+name)
    p.add_argument('--scratch-bytes',type=int);p.add_argument('--learning-rate',type=float,choices=[0.0001,0.00005],default=0.0001);p.add_argument('--stop-after',type=int)
    a=p.parse_args()
    if a.action=='doctor':
        print(json.dumps({'version':'coding-training-doctor014-v1','profile':a.profile,'model':MODELS[a.profile],'training_started':False,'ready':bool(a.corpus and a.corpus_sha256 and admit_corpus(read_bound(a.corpus,a.corpus_sha256))),'scope':'Read-only admission check; no CUDA, model download, login or training.'}));return
    if not all(getattr(a,n) for n in ['corpus','corpus_sha256','model_manifest','model_manifest_sha256','model_directory','output','scratch_root','scratch_bytes']):p.error('Fitting requires reviewed corpus/model hashes and explicit counted scratch admission')
    if not 0<a.scratch_bytes<=20*1024**3:p.error('Temporary cloud scratch ceiling is 20GiB')
    if a.stop_after is not None and not 1<=a.stop_after<=20:p.error('Interruption pilot must stop after one to twenty steps')
    if a.action=='train' and not (a.pilot_evidence and a.pilot_evidence_sha256):p.error('Full training requires frozen fit/resume acceptance evidence')
    try:print(json.dumps(run(a)))
    except Exception as error:
        if getattr(a,'_owned_output_created',False):
            with (a.output/'failure.json').open('x') as stream:json.dump({'version':'coding-training-failure014-v1','run_complete':False,'failure_type':type(error).__name__,'resource_fit_verified':False},stream)
        raise


if __name__=='__main__':main()
