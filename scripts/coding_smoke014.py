"""Tiny random-weight CPU adapter fixture; never a pretrained coding-model result."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from scripts.coding_train014 import adapter_options,trainer_options,checkpoint_receipt,verify_checkpoint,sha_file


def run(output):
    import torch
    from transformers import Qwen2Config,Qwen2ForCausalLM,Trainer,TrainerCallback,TrainingArguments,default_data_collator,set_seed
    from peft import LoraConfig,get_peft_model,get_peft_model_state_dict
    if output.exists():raise ValueError('Fixture output must be new')
    output.mkdir(parents=True,mode=0o700)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    configuration={'vocab_size':32,'hidden_size':32,'intermediate_size':64,'num_hidden_layers':2,'num_attention_heads':4,'num_key_value_heads':2,'max_position_embeddings':32,'attention_dropout':0.0,'use_cache':False}
    binding={'version':'tiny-random-qwen-fixture014-v1','runner_sha256':sha_file(Path(__file__).with_name('coding_train014.py')),'configuration':configuration,'steps':20,'seed':42,'device':'cpu','pretrained_weights':False}
    generator=torch.Generator().manual_seed(85)
    tokens=torch.randint(0,32,(160,8),generator=generator).tolist()
    dataset=[{'input_ids':v,'attention_mask':[1]*8,'labels':[-100]*4+v[4:]} for v in tokens]
    class Capture(TrainerCallback):
        def __init__(self,stop=None):self.stop=stop;self.logs=[]
        def on_step_end(self,args,state,control,**kwargs):
            if self.stop and state.global_step>=self.stop:control.should_save=True;control.should_training_stop=True
            return control
        def on_log(self,args,state,control,logs=None,**kwargs):
            if logs:self.logs.append({k:float(logs[k]) for k in ['loss','grad_norm'] if k in logs})
        def on_save(self,args,state,control,**kwargs):checkpoint_receipt(Path(args.output_dir)/('checkpoint-'+str(state.global_step)),binding)
    def training(name,stop=None,resume=None):
        set_seed(42)
        model=get_peft_model(Qwen2ForCausalLM(Qwen2Config(**configuration)),LoraConfig(**adapter_options()))
        model.enable_input_require_grads()
        originals={n:p.detach().clone() for n,p in model.named_parameters() if not p.requires_grad}
        initial={n:t.detach().clone() for n,t in get_peft_model_state_dict(model).items()}
        capture=Capture(stop)
        args=TrainingArguments(**trainer_options(output/name,20,0.0001,fixture_cpu=True),disable_tqdm=True,full_determinism=True)
        trainer=Trainer(model=model,args=args,train_dataset=dataset,data_collator=default_data_collator,callbacks=[capture])
        trainer.train(resume_from_checkpoint=str(resume) if resume else None)
        final={n:t.detach().cpu().clone() for n,t in get_peft_model_state_dict(model).items()}
        base_unchanged=all(torch.equal(originals[n],p.detach()) for n,p in model.named_parameters() if n in originals)
        return {'adapter':final,'changed':any(not torch.equal(initial[n],t) for n,t in final.items()),'base_unchanged':base_unchanged,'optimizer':trainer.optimizer.state_dict(),'scheduler':trainer.lr_scheduler.state_dict(),'rng':torch.get_rng_state().clone(),'logs':capture.logs,'steps':trainer.state.global_step}
    def equal(a,b):
        if torch.is_tensor(a):return torch.is_tensor(b) and torch.equal(a,b)
        if type(a)!=type(b):return False
        if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
        if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
        return a==b
    full=training('full');split=training('interrupted',stop=10)
    checkpoint=output/'interrupted/checkpoint-10';verify_checkpoint(checkpoint,sha_file(checkpoint/'kairos-checkpoint.json'),binding)
    resumed=training('resumed',resume=checkpoint)
    checks={'full_twenty_steps':full['steps']==20,'interrupted_at_ten':split['steps']==10,'resumed_twenty_steps':resumed['steps']==20,'adapter_weights_changed':full['changed'],'base_weights_unchanged':all(r['base_unchanged'] for r in [full,split,resumed]),'adapter_equal':equal(full['adapter'],resumed['adapter']),'optimizer_equal':equal(full['optimizer'],resumed['optimizer']),'scheduler_equal':equal(full['scheduler'],resumed['scheduler']),'torch_rng_equal':equal(full['rng'],resumed['rng']),'finite_loss_and_gradient':all(math.isfinite(v) for run in [full,split,resumed] for log in run['logs'] for v in log.values()),'nonzero_gradient':any(log.get('grad_norm',0)>0 for log in full['logs'])}
    receipt={'version':'coding-adapter-cpu-fixture014-v1','passed':all(checks.values()),'checks':checks,'binding':binding,'runtime':{n:importlib.metadata.version(n) for n in ['torch','transformers','peft','accelerate']},'scope':'Isolated random-weight tiny Qwen2 CPU fixture. Real adapter gradients and resume mechanics only; no pretrained7B/14B weights, NF4 GPU fit, coding-model training corpus or repair effectiveness claim.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--fixture-only',action='store_true',required=True);args=parser.parse_args()
    result=run(args.output);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
