"""Pinned local inference adapter with measured context selection."""
import json
import os
from pathlib import Path
from kairos_api.model_runtime import digest
from urllib.parse import urlparse
import httpx
from kairos_api.investigations.contracts import Action, GENERATION, SYSTEM


class LocalInvestigator:
    def __init__(self):
        self.endpoint=os.environ.get('KAIROS_INVESTIGATION_MODEL_URL','http://127.0.0.1:8130')
        parsed=urlparse(self.endpoint)
        if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.query or parsed.fragment:
            raise ValueError('Investigations require a configured loopback model endpoint')

    def verify_profile(self):
        manifest_path=Path(os.environ.get('KAIROS_INVESTIGATION_MODEL_MANIFEST',Path(__file__).resolve().parents[2]/'evidence/build003/inference-runtime.json'))
        manifest=json.loads(manifest_path.read_text())
        expected=next(Path(file['path']).name for file in manifest['files'] if file['path'].endswith('.gguf'))
        with httpx.Client(timeout=10,trust_env=False) as client:
            response=client.get(self.endpoint+'/v1/models');response.raise_for_status()
            models=response.json()['data']
        if len(models)!=1 or Path(models[0]['id']).name!=expected: raise ValueError('Loaded inference model differs from pinned profile')
        self.profile_attestation={'model_id':models[0]['id'],'profile_digest':digest(manifest),'scope':'Trusted local runtime identity; endpoint does not attest remote weight bytes'}
        return self.profile_attestation

    def prepare(self,case,configuration,observations,budgets):
        if configuration.endswith('-v4'): return self.prepare_v4(case,configuration,observations,budgets)
        value={'issue':case['issue'][:4500],'source_revision':case['revision'],'approved_source':case['approved_prefix'],
               'budgets':budgets,'observations':observations[-4:],
               'latest_verification': next((str(o['result'])[-2000:] for o in reversed(observations) if o['action']=='run_checks'),None)}
        system=SYSTEM
        if configuration.startswith('baseline-'): system+=' This is a single-call baseline. Choose propose_patch or final_result now.'
        omitted=list(range(max(0,len(observations)-4)))
        with httpx.Client(timeout=10,trust_env=False) as client:
            while True:
                text=json.dumps(value,ensure_ascii=False)
                response=client.post(self.endpoint+'/tokenize',json={'content':system+'\n'+text,'add_special':True})
                response.raise_for_status();count=len(response.json()['tokens'])
                if count<=2750: break
                if value['observations']:
                    # Drop oldest evidence first, preserving issue/budgets. Record the choice.
                    omitted.append(max(0,len(observations)-len(value['observations'])))
                    if len(value['observations'])==1:
                        encoded=json.dumps(value['observations'][0],ensure_ascii=False)
                        value['observations'][0]={'excerpt':encoded[:max(300,len(encoded)//2)],'truncated':True}
                        if len(encoded)<=350: raise ValueError('Context cannot fit pinned token budget')
                    else: value['observations'].pop(0)
                elif len(value['issue'])>600: value['issue']=value['issue'][:len(value['issue'])//2]
                else: raise ValueError('Context cannot fit pinned token budget')
        request={'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(value,ensure_ascii=False)}],
                 **GENERATION,'response_format':{'type':'json_schema','json_schema':{'name':'investigation_action','strict':True,'schema':Action.json_schema()}}}
        return request,{'input_tokens_before_chat_template':count,'reserved_template_tokens':322,'output_tokens':1024,
                        'omitted_observation_indices':sorted(set(omitted)), 'issue_truncated':value['issue']!=case['issue'],
                        'selection':value}

    def __call__(self,request,seconds=120):
        with httpx.Client(timeout=httpx.Timeout(min(120,float(seconds)),connect=5),trust_env=False) as client:
            with client.stream('POST',self.endpoint+'/v1/chat/completions',json=request) as response:
                response.raise_for_status()
                body=bytearray()
                for chunk in response.iter_bytes():
                    if len(body)+len(chunk)>1000000: raise ValueError('Model response exceeds capture limit')
                    body.extend(chunk)
                return json.loads(body)

    def prepare_v4(self,case,configuration,observations,budgets):
        from kairos_api.investigations.contracts import ActionV4, SYSTEM_V4
        system=SYSTEM_V4
        if configuration.startswith(('baseline-','drafts-')): system+=' This is an independent single draft. Choose propose_patch or final_result now.'
        latest=next((o['result'] for o in reversed(observations) if o['action']=='run_checks'),None)
        verification=None if latest is None else {k:latest[k] for k in ('passed','environment_error','returncode','patch_digest') if k in latest}
        if latest:
            verification['stdout_lines']=str(latest.get('stdout','')).splitlines()[-12:]
            verification['stderr_lines']=str(latest.get('stderr','')).splitlines()[-12:]
        chosen=list(enumerate(observations[-4:],start=max(0,len(observations)-4)))
        omissions=[{'observation_index':i,'reason':'Outside latest four observations'} for i in range(max(0,len(observations)-4))]
        value={'issue':case['issue'],'source_revision':case['revision'],'approved_source':case['approved_prefix'],
               'budgets':budgets,'observations':[o for _,o in chosen],'latest_verification':verification}
        with httpx.Client(timeout=10,trust_env=False) as client:
            while True:
                messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(value,ensure_ascii=False)}]
                rendered=client.post(self.endpoint+'/apply-template',json={'messages':messages,'add_generation_prompt':True,'chat_template_kwargs':GENERATION['chat_template_kwargs']})
                rendered.raise_for_status();prompt=rendered.json()['prompt']
                tokens=client.post(self.endpoint+'/tokenize',json={'content':prompt,'add_special':True});tokens.raise_for_status();count=len(tokens.json()['tokens'])
                if count+GENERATION['max_tokens']+32<=4096: break
                if chosen:
                    index,_=chosen.pop(0);omissions.append({'observation_index':index,'reason':'Complete region omitted to fit rendered context'})
                    value['observations']=[o for _,o in chosen]
                elif verification and (verification.get('stdout_lines') or verification.get('stderr_lines')):
                    # Keep verdict and patch identity; drop complete output lines only.
                    verification['stdout_lines']=[];verification['stderr_lines']=[]
                    omissions.append({'field':'verification_output','reason':'Output lines omitted; verdict retained'})
                else: raise ValueError('Complete issue and required context exceed the 4096-token profile')
        request={'messages':messages,**GENERATION,'response_format':{'type':'json_schema','json_schema':{'name':'snapshot_action_v1','strict':True,'schema':ActionV4.json_schema()}}}
        if hasattr(self,'profile_attestation'): request['model']=self.profile_attestation['model_id']
        return request,{'runtime_profile':getattr(self,'profile_attestation',None),'rendered_input_tokens':count,'output_tokens':1024,'reserve_tokens':32,'omissions':omissions,'selection':value,'context_version':'complete-regions-v1'}
