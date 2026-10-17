"""Actual14B QLoRA resource pilot on synthetic fixtures; no repair-score claim."""
import os,json,hashlib,gc,math,shutil,time
from pathlib import Path
ROOT=Path(os.environ.get('KAIROS_PILOT_ROOT','/content/kairos14-resource014'));OUT=ROOT/'results';MODEL=ROOT/'model'
REPO='unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit';REV='ecfc63c083900ce4f19daad695e711f38ab98fcf'
WEIGHTS={'model-00001-of-00002.safetensors':('8fbefb1b257e9443b3b817b655449f1c2884afefcad1a5a6c33f9097169e383e',4998641583),'model-00002-of-00002.safetensors':('d5c3d547462b12bac817a5af131be0862220b67ec7a7114b07fdf810df6ac285',4933695760)}
os.environ.update(HF_HOME=str(ROOT/'hf-cache'),HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_XET='1',TORCH_HOME=str(ROOT/'torch-cache'),XDG_CACHE_HOME=str(ROOT/'cache'),CUDA_CACHE_PATH=str(ROOT/'cuda-cache'),WANDB_DISABLED='true',CUBLAS_WORKSPACE_CONFIG=':4096:8',TOKENIZERS_PARALLELISM='false',UNSLOTH_DISABLE_STATISTICS='1')
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def guard():
 size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink())
 if size>20*1024**3 or shutil.disk_usage(ROOT).free<4*1024**3:raise RuntimeError('20GiB pilot scratch or4GiB reserve exceeded')
 return size
def write(name,data):
 p=OUT/name
 with p.open('x') as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def tree_cpu(value):
 if torch.is_tensor(value):return value.detach().cpu().clone()
 if isinstance(value,dict):return {k:tree_cpu(v) for k,v in value.items()}
 if isinstance(value,list):return [tree_cpu(v) for v in value]
 if isinstance(value,tuple):return tuple(tree_cpu(v) for v in value)
 return value
def equal(a,b):
 if torch.is_tensor(a):return torch.is_tensor(b) and torch.equal(a,b)
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
 if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
 return a==b
def main():
 global torch
 import platform
 if platform.system()!='Linux':raise RuntimeError('Use an isolated Linux GPU runtime; never train this model on the Mac')
 ROOT.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
 with (ROOT/'pilot.started').open('x') as f:f.write('No automatic rerun after an interrupted dispatch. Preserve results/checkpoints.\n')
 try:
  guard()
  # Import Unsloth before Transformers so its documented memory patches apply.
  from unsloth import FastLanguageModel
  import torch,importlib.metadata
  from huggingface_hub import snapshot_download
  from transformers import Trainer,TrainerCallback,TrainingArguments,DataCollatorForSeq2Seq,set_seed
  from peft import get_peft_model_state_dict,set_peft_model_state_dict
  if not torch.cuda.is_available():raise RuntimeError('CUDA GPU required; no CPU or smaller-model fallback')
  runtime={n:importlib.metadata.version(n) for n in ['unsloth','unsloth_zoo','torch','transformers','peft','accelerate','bitsandbytes']}
  if torch.cuda.get_device_capability(0)<(7,5):raise RuntimeError('This reviewed pilot requires CUDA compute capability7.5 or newer')
  write('intent.json',{'version':'gpu14-resource-intent014-v1','model':REPO,'revision':REV,'runtime':runtime,'device':torch.cuda.get_device_name(0),'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,'synthetic_fixture_only':True,'repair_training_corpus_admitted':False,'planned_optimizer_updates':40,'conditions':'Full20, interrupted10, resumed10 additional updates','context_tokens':2048,'microbatch':1,'gradient_accumulation':8,'adapter_rank':8,'adapter_dropout':0.0,'adapter_targets':['q_proj','v_proj'],'learning_rate':0.0001,'quantization':'NF4 prequantized derivative','checkpointing':'Unsloth memory-efficient checkpointing','spend':'No API, subscription purchase or paid endpoint','script_sha256':sha(Path(__file__))})
  print('Downloading pinned14B NF4 weights,9,932,337,343bytes; no credentials required.',flush=True)
  snapshot_download(REPO,revision=REV,local_dir=str(MODEL),allow_patterns=['*.json','*.safetensors','*.model','*.txt','*.jinja'],token=False,max_workers=1)
  for name,(expected,size) in WEIGHTS.items():
   p=MODEL/name
   if p.stat().st_size!=size or sha(p)!=expected:raise RuntimeError('Pinned model weight bytes differ')
  guard();write('weight-receipt.json',{'model':REPO,'revision':REV,'weights':{n:{'sha256':h,'bytes':s} for n,(h,s) in WEIGHTS.items()},'files':{p.relative_to(MODEL).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in MODEL.rglob('*') if p.is_file() and '.cache' not in p.parts}})
  os.environ['HF_HUB_OFFLINE']='1';set_seed(42);torch.use_deterministic_algorithms(True)
  model,tokenizer=FastLanguageModel.from_pretrained(model_name=str(MODEL),max_seq_length=2048,dtype=torch.float16,load_in_4bit=True,local_files_only=True,trust_remote_code=False)
  model=FastLanguageModel.get_peft_model(model,r=8,target_modules=['q_proj','v_proj'],lora_alpha=16,lora_dropout=0.0,bias='none',use_gradient_checkpointing='unsloth',random_state=42,use_rslora=False,loftq_config=None)
  if any('lora_' not in n for n,p in model.named_parameters() if p.requires_grad):raise RuntimeError('Non-adapter parameter is trainable')
  if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
  tokenizer.padding_side='right';initial=tree_cpu(get_peft_model_state_dict(model));data=[]
  for i in range(160):
   value=i%20+1;original=f'def value():\n    return {value-1}\n';handle='S'+hashlib.sha256(original.encode()).hexdigest()[:12]
   prompt=json.dumps({'issue':f'value() must return {value}.','original_source':[{'source_id':handle,'path':'package/value.py','start_line':1,'end_line':2,'numbered_original_source':'1: def value():\n2:     return '+str(value-1)+'\n'}]},sort_keys=True)
   target=json.dumps({'action':'propose_patch','edits':[{'source_id':handle,'start_line':2,'end_line':2,'new':f'    return {value}\n'}]},sort_keys=True)
   messages=[{'role':'system','content':'Return one source-handle JSON edit action.'},{'role':'user','content':prompt}]
   prefix=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
   full=tokenizer.apply_chat_template(messages+[{'role':'assistant','content':target}],tokenize=True,add_generation_prompt=False)
   if full[:len(prefix)]!=prefix or len(full)>2048:raise RuntimeError('Exact target mask or sequence budget failed')
   data.append({'input_ids':full,'attention_mask':[1]*len(full),'labels':[-100]*len(prefix)+full[len(prefix):]})
  collator=DataCollatorForSeq2Seq(tokenizer,model=None,padding='max_length',max_length=2048,label_pad_token_id=-100)
  class Capture(TrainerCallback):
   def __init__(self,name,stop):self.name=name;self.stop=stop;self.logs=[]
   def on_log(self,args,state,control,logs=None,**kwargs):
    if logs:
     item={'step':state.global_step,**{k:float(logs[k]) for k in ['loss','grad_norm'] if k in logs}}
     if any(not math.isfinite(v) for k,v in item.items()):raise RuntimeError('Nonfinite loss/gradient')
     self.logs.append(item)
     with (OUT/(self.name+'-metrics.jsonl')).open('a') as f:f.write(json.dumps(item)+'\n');f.flush();os.fsync(f.fileno())
     print(self.name,item,flush=True)
   def on_step_end(self,args,state,control,**kwargs):
    if self.stop and state.global_step>=self.stop:control.should_save=True;control.should_training_stop=True
    return control
   def on_save(self,args,state,control,**kwargs):
    folder=Path(args.output_dir)/('checkpoint-'+str(state.global_step))
    manifest={p.relative_to(folder).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in folder.rglob('*') if p.is_file()}
    (folder/'checkpoint-files.json').write_text(json.dumps(manifest,indent=2));guard()
  def training(name,stop=None,resume=None):
   set_seed(42);set_peft_model_state_dict(model,initial);FastLanguageModel.for_training(model)
   callback=Capture(name,stop);folder=OUT/name
   args=TrainingArguments(output_dir=str(folder),max_steps=20,per_device_train_batch_size=1,gradient_accumulation_steps=8,learning_rate=0.0001,fp16=True,bf16=False,optim='adamw_torch',logging_steps=1,logging_nan_inf_filter=False,save_strategy='no',report_to='none',push_to_hub=False,seed=42,data_seed=42,dataloader_num_workers=0,dataloader_pin_memory=False,remove_unused_columns=False,disable_tqdm=True)
   if resume:
    captured=json.loads((resume/'checkpoint-files.json').read_text())
    for path,item in captured.items():
     if '..' in Path(path).parts or Path(path).is_absolute():raise RuntimeError('Unsafe checkpoint path')
     if sha(resume/path)!=item['sha256']:raise RuntimeError('Resume checkpoint changed')
   torch.cuda.reset_peak_memory_stats();started=time.monotonic()
   trainer=Trainer(model=model,args=args,train_dataset=data,data_collator=collator,callbacks=[callback]);trainer.train(resume_from_checkpoint=str(resume) if resume else None);torch.cuda.synchronize()
   result={'adapter':tree_cpu(get_peft_model_state_dict(model)),'optimizer':tree_cpu(trainer.optimizer.state_dict()),'scheduler':tree_cpu(trainer.lr_scheduler.state_dict()),'cpu_rng':torch.get_rng_state().clone(),'cuda_rng':torch.cuda.get_rng_state(0).clone(),'steps':trainer.state.global_step,'seconds':time.monotonic()-started,'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'logs':callback.logs}
   target=folder/'final-adapter';model.save_pretrained(str(target),safe_serialization=True)
   for config in target.glob('adapter_config.json'):
    d=json.loads(config.read_text());d['base_model_name_or_path']=REPO;d['revision']=REV;config.write_text(json.dumps(d,indent=2)+'\n')
   write(name+'-receipt.json',{k:v for k,v in result.items() if k not in ['adapter','optimizer','scheduler','cpu_rng','cuda_rng','logs']})
   del trainer;gc.collect();torch.cuda.empty_cache();guard();return result
  print('Starting actual14B adapter updates on explicitly synthetic resource fixtures.',flush=True)
  full=training('full');partial=training('interrupted',stop=10);del partial;gc.collect();torch.cuda.empty_cache()
  resumed=training('resumed',resume=OUT/'interrupted/checkpoint-10')
  checks={k:equal(full[k],resumed[k]) for k in ['adapter','optimizer','scheduler','cpu_rng','cuda_rng']}
  peak=max(full['peak_reserved_bytes'],resumed['peak_reserved_bytes']);total=torch.cuda.get_device_properties(0).total_memory
  checks.update(adapter_updated=not equal(initial,full['adapter']),twenty_steps_completed=full['steps']==resumed['steps']==20,nonzero_gradient=any(x.get('grad_norm',0)>0 for x in full['logs']),vram_headroom=1-peak/total>=0.15)
  write('receipt.json',{'version':'gpu14-resource-result014-v1','model':REPO,'revision':REV,'runtime':runtime,'checks':checks,'passed':all(checks.values()),'peak_reserved_bytes':peak,'gpu_total_bytes':total,'headroom_fraction':1-peak/total,'trainable_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad),'synthetic_fixture_only':True,'repair_quality_verified':False,'full_repair_training_complete':False,'scope':'Actual pretrained14B adapter updates and resume on synthetic source-edit fixtures. No independent repair-effectiveness or qualified-corpus training claim.'})
  print('GPU14_RESOURCE_RESULT',json.dumps(json.loads((OUT/'receipt.json').read_text())),flush=True)
 except BaseException as error:
  if not (OUT/'failure.json').exists():write('failure.json',{'version':'gpu14-resource-failure014-v1','failure_type':type(error).__name__,'message':str(error)[:1000],'repair_quality_verified':False,'full_repair_training_complete':False})
  raise

if __name__=='__main__':main()
