"""Bounded loop. Dispatch intent commits before local inference; recovery never guesses."""
import json
import time
import psycopg
from psycopg_pool import PoolTimeout
from uuid import uuid4
from pydantic import ValidationError
from kairos_api.investigations.contracts import Action, ActionV4, ActionV5
from kairos_api.investigations.model import LocalInvestigator
from kairos_api.investigations.repository import InvestigationRepository
from kairos_api.investigations.sandbox import Workspace
from kairos_api.model_runtime import digest, strict_json

ENTRY_LINES={'kairos_api/jobs_repository.py':245,'django/db/models/sql/compiler.py':320,
             'django/db/models/sql/query.py':1750,'django/conf/global_settings.py':275}


class InvestigationWorker:
    def __init__(self,repository=None,provider=None,workspace=Workspace):
        self.repository=repository or InvestigationRepository()
        self.provider=provider or LocalInvestigator()
        self.workspace_factory=workspace
        self.owner='investigator-'+uuid4().hex

    def run_once(self):
        job=self.repository.claim(self.owner)
        if not job: return None
        workspace=None
        try:
            case=self.repository.registry.get(job['task_id'])
            if self.repository.registry.fingerprint(case)!=job['task_digest']:
                raise ValueError('Registered case changed after enqueue')
            if job['config_snapshot']['model_manifest_digest']!=self.repository._model_digest():
                raise ValueError('Pinned model manifest changed after enqueue')
            if job['configuration'].endswith(('-v4','-v5')) and hasattr(self.provider,'verify_profile'): self.provider.verify_profile()
            workspace=self.workspace_factory(self.repository.registry,case)
            return self._run_drafts(job,workspace) if job['configuration'].startswith('drafts-') else self._run(job,workspace)
        except TimeoutError:
            return self.repository.finish(job,'timeout','Investigation deadline exhausted')
        except RuntimeError:
            # Cancellation and stale fencing cannot authorize a final write.
            return self.repository.read(str(job['id']),job['tenant_id'])
        except Exception as error:
            return self.repository.finish(job,'environment_failure',type(error).__name__+': '+str(error)[:500])
        finally:
            if workspace: workspace.close()

    def _record(self,job,kind,name,request,result):
        seq=self.repository.begin(job,kind,name,request)
        self.repository.capture(job,seq,result)
        return seq

    def _state(self,job,workspace):
        record=self.repository.read(str(job['id']),job['tenant_id'])
        if not record['integrity']['verified']: raise ValueError('Captured step integrity mismatch')
        if job['configuration'].endswith('-v5') and not any(
                step['kind']=='tool' and step['name'] in {'initial_source','read_file'} and
                step['state']=='captured' and step['result']['body'].get('reference')
                for step in record['steps']):
            from kairos_api.investigations.context_v5 import initial_sources
            # Localization is persisted before any dispatch. Recovery consumes the
            # captured source rather than selecting new, unrecorded case hints.
            for result in initial_sources(workspace):
                self._record(job,'tool','initial_source',{'origin':'public-issue-symbol-ast-v1'},result)
            record=self.repository.read(str(job['id']),job['tenant_id'])
        observations=[];patch='';verification=None;invalid=False
        for step in record['steps']:
            if step['kind']!='tool' or step['state']!='captured': continue
            request=step['request']['body'];result=step['result']['body']
            if job['configuration'].endswith(('-v4','-v5')) and step['name'] in {'read_file','initial_source'} and 'error' not in result: workspace.restore_reference(result)
            if step['name']=='propose_patch':
                invalid='error' in result
                if not invalid: patch=result.get('patch',request.get('patch',''));verification=None
            if step['name']=='run_checks' and result.get('patch_digest')==digest(patch): verification=result
            observations.append({'action':step['name'],'result':result})
        if job['configuration'].endswith(('-v4','-v5')):
            for step in record['steps']:
                if step['kind']=='context' and step['result']:
                    for observation in step['result']['body'].get('selection',{}).get('observations',[]):
                        if isinstance(observation.get('result'),dict): workspace.restore_reference(observation['result'])
                    if job['configuration'].endswith('-v5'):
                        for result in step['result']['body'].get('source_catalog',[]):
                            workspace.restore_reference(result)
        if patch: workspace.propose(patch)
        if not observations:
            for path in workspace.case['entry_files']:
                observations.append({'action':'initial_source','result':(workspace.read_original if job['configuration'].endswith('-v4') else workspace.read)(path,workspace.case.get('entry_lines',{}).get(path,ENTRY_LINES.get(path,1)))})
        return record,observations,patch,verification,invalid

    def _verify(self,job,workspace,patch,model_seq=None):
        seq=self.repository.begin(job,'tool','run_checks',{'action':'run_checks','model_seq':model_seq,'patch_digest':digest(patch)})
        result=workspace.checks(float(self.repository.remaining(job)))
        result['patch_digest']=digest(patch)
        self.repository.capture(job,seq,result)
        return result

    def _outcome(self,job,workspace,patch,verification,invalid,summary):
        if patch and verification is None:
            record=self.repository.read(str(job['id']),job['tenant_id'])
            if record['check_count']<job['config_snapshot']['budgets']['max_checks']:
                verification=self._verify(job,workspace,patch)
        if verification and verification.get('environment_error'): outcome='environment_failure'
        elif patch and verification and verification.get('passed'): outcome='verified_repair'
        elif patch: outcome='failed_checks'
        elif invalid: outcome='invalid_patch'
        else: outcome='no_patch'
        return self.repository.finish(job,outcome,summary)

    def _run_drafts(self,job,workspace):
        # All six fresh-context drafts are captured before any check result exists.
        observations=[{'action':'initial_source','result':workspace.read_original(path,workspace.case.get('entry_lines',{}).get(path,ENTRY_LINES.get(path,1)))} for path in workspace.case['entry_files']]
        while True:
            if self.repository.remaining(job)<=0: raise TimeoutError()
            record=self.repository.read(str(job['id']),job['tenant_id'])
            if not record['integrity']['verified']: raise ValueError('Captured step integrity mismatch')
            drafts=[s for s in record['steps'] if s['name']=='draft_candidate' and s['state']=='captured']
            handled={s['request']['body'].get('model_seq') for s in drafts}
            models=[s for s in record['steps'] if s['kind']=='model' and s['state']=='captured' and s['seq'] not in handled]
            if not models and record['model_calls']>=6: break
            if models: model=models[0];response=model['result']['body']
            else:
                request,context=self.provider.prepare(workspace.case,job['configuration'],observations,{'calls_remaining':1,'patches_remaining':1,'checks_remaining':1})
                # Deterministic distinct seeds; each draft gets only original evidence.
                request['seed']=73+record['model_calls']
                self._record(job,'context','selection',{'configuration':job['configuration'],'draft_index':record['model_calls']},context)
                seq=self.repository.begin(job,'model','dispatch',request)
                try: response=self.provider(request,float(self.repository.remaining(job)))
                except Exception as error: return self.repository.finish(job,'unknown_dispatch',type(error).__name__+': '+str(error)[:300])
                self.repository.capture(job,seq,response);model={'seq':seq}
            try:
                choice=response['choices'][0]
                if choice['finish_reason']!='stop': raise ValueError('Draft response truncated')
                action=ActionV4.validate_python(strict_json(choice['message']['content'])).model_dump()
                if action['action']!='propose_patch': raise ValueError('Independent draft did not propose a patch')
                result=workspace.propose_snapshot_edits(action['edits'])
                result['selected']=sum(bool(s['result']['body'].get('selected')) for s in drafts)<2
            except (ValueError,ValidationError,KeyError,IndexError,TypeError,OSError) as error:
                result={'error':str(error)[:1000],'selected':False}
            self._record(job,'tool','draft_candidate',{'model_seq':model['seq'],'selection_policy':'first-two-valid-before-checks'},result)
        record=self.repository.read(str(job['id']),job['tenant_id'])
        candidates=[s for s in record['steps'] if s['name']=='draft_candidate' and s['state']=='captured' and s['result']['body'].get('selected')]
        checked=[]
        for candidate in candidates:
            patch=candidate['result']['body']['patch'];patch_hash=digest(patch)
            record=self.repository.read(str(job['id']),job['tenant_id'])
            proposals=[s for s in record['steps'] if s['name']=='propose_patch' and s['state']=='captured' and s['result']['body'].get('draft_seq')==candidate['seq']]
            workspace.propose(patch)
            if not proposals:
                self._record(job,'tool','propose_patch',{'draft_seq':candidate['seq']},{'patch':patch,'draft_seq':candidate['seq'],'construction':'Selected independent draft'})
            checks=[s for s in record['steps'] if s['name']=='run_checks' and s['state']=='captured' and s['result']['body'].get('patch_digest')==patch_hash and s['request']['body'].get('model_seq')==candidate['seq']]
            verification=checks[-1]['result']['body'] if checks else self._verify(job,workspace,patch,candidate['seq'])
            checked.append({'draft_seq':candidate['seq'],'patch_digest':patch_hash,'verification':verification})
        winner=next((c for c in checked if c['verification'].get('passed')),checked[-1] if checked else None)
        if winner and winner['verification'].get('passed'): outcome='verified_repair'
        elif checked and any(c['verification'].get('environment_error') for c in checked): outcome='environment_failure'
        elif checked: outcome='failed_checks'
        else: outcome='invalid_patch'
        record=self.repository.read(str(job['id']),job['tenant_id'])
        if not any(s['name']=='draft_selection' and s['state']=='captured' for s in record['steps']):
            self._record(job,'tool','draft_selection',{'policy':'first-two-valid-before-checks'},{'selected_patch_digest':winner['patch_digest'] if winner else None,'candidates':checked,'outcome':outcome})
        return self.repository.finish(job,outcome,'Six independent drafts captured before checking the first two valid candidates')

    def _run(self,job,workspace):
        while True:
            if self.repository.remaining(job)<=0: raise TimeoutError()
            record,observations,patch,verification,invalid=self._state(job,workspace)
            if job['configuration'].endswith(('-v4','-v5')) and patch and verification is None and record['check_count']<job['config_snapshot']['budgets']['max_checks']:
                self._verify(job,workspace,patch);continue
            if job['configuration'].endswith(('-v4','-v5')) and verification and verification.get('passed'):
                return self._outcome(job,workspace,patch,verification,invalid,'Independent checks passed')
            if job['configuration'].endswith('-v5') and verification and verification.get('environment_error'):
                return self._outcome(job,workspace,patch,verification,invalid,'Verification environment failed; no additional inference dispatched')
            if job['configuration'].endswith('-v5') and verification and (
                    record['check_count']>=job['config_snapshot']['budgets']['max_checks'] or
                    record['patch_count']>=job['config_snapshot']['budgets']['max_patches']):
                return self._outcome(job,workspace,patch,verification,invalid,'Candidate verification budget reached')
            handled={s['request']['body'].get('model_seq') for s in record['steps'] if s['kind']=='tool' and s['state']=='captured'}
            models=[s for s in record['steps'] if s['kind']=='model' and s['state']=='captured' and s['seq'] not in handled]
            if models:
                model=models[-1]
                response=model['result']['body']
            else:
                if record['model_calls']>=job['config_snapshot']['budgets']['max_calls']:
                    return self._outcome(job,workspace,patch,verification,invalid,'Model call budget reached')
                pinned = {'generation_snapshot':job['config_snapshot']['generation']} if job['configuration'].endswith('-v5') and isinstance(self.provider,LocalInvestigator) and 'generation' in job['config_snapshot'] else {}
                request,context=self.provider.prepare(workspace.case,job['configuration'],observations,
                    {'calls_remaining':job['config_snapshot']['budgets']['max_calls']-record['model_calls'],
                     'patches_remaining':job['config_snapshot']['budgets']['max_patches']-record['patch_count'],
                     'checks_remaining':job['config_snapshot']['budgets']['max_checks']-record['check_count']},**pinned)
                self._record(job,'context','selection',{'configuration':job['configuration']},context)
                seq=self.repository.begin(job,'model','dispatch',request)
                try: response=self.provider(request,float(self.repository.remaining(job)))
                except Exception as error:
                    # Transport uncertainty is not evidence that the provider did no work.
                    return self.repository.finish(job,'unknown_dispatch',type(error).__name__+': '+str(error)[:300])
                self.repository.capture(job,seq,response)
                model={'seq':seq}
            try:
                choice=response['choices'][0]
                if choice['finish_reason']!='stop': raise ValueError('Model response truncated or interrupted')
                parsed=strict_json(choice['message']['content'])
                adapter=ActionV5 if job['configuration'].endswith('-v5') else (ActionV4 if job['configuration'].endswith('-v4') else Action)
                action=adapter.validate_python(parsed).model_dump()
            except (ValueError,ValidationError,KeyError,IndexError,TypeError) as error:
                return self.repository.finish(job,'invalid_response',str(error)[:500])
            name=action['action']
            dispatch_context=None
            if job['configuration'].endswith('-v5'):
                captured=self.repository.read(str(job['id']),job['tenant_id'])
                contexts=[step for step in captured['steps'] if step['kind']=='context' and
                          step['state']=='captured' and step['seq']<model['seq']]
                if not contexts:
                    return self.repository.finish(job,'invalid_response','V5 dispatch has no captured context authority')
                dispatch_context=max(contexts,key=lambda step:step['seq'])['result']['body']
                if name not in dispatch_context.get('allowed_actions',[]):
                    return self.repository.finish(job,'invalid_response','Action is outside the captured dispatch phase')
            if job['configuration'].startswith('baseline-') and name not in {'propose_patch','final_result'}:
                return self.repository.finish(job,'invalid_response','Single-call baseline requires a patch or final result')
            if name=='final_result':
                return self._outcome(job,workspace,patch,verification,invalid,action['summary'])
            request={**action,'model_seq':model['seq']}
            try:
                if name=='run_checks':
                    self._verify(job,workspace,patch,model['seq']);continue
                seq=self.repository.begin(job,'tool',name,request)
            except ValueError:
                return self._outcome(job,workspace,patch,verification,invalid,'Tool budget exhausted')
            try:
                if name=='search': result=(workspace.search_original if job['configuration'].endswith(('-v4','-v5')) else workspace.search)(action['query'])
                elif name=='read_file': result=(workspace.read_original if job['configuration'].endswith(('-v4','-v5')) else workspace.read)(action['path'],action['start_line'])
                elif job['configuration'].endswith('-v5'):
                    if record['patch_count']>=job['config_snapshot']['budgets']['max_patches']: raise ValueError('Applied patch budget exhausted')
                    result=workspace.propose_handle_edits(action['edits'],dispatch_context.get('reference_bindings',{}))
                elif job['configuration'].endswith('-v4'):
                    if record['patch_count']>=job['config_snapshot']['budgets']['max_patches']: raise ValueError('Applied patch budget exhausted')
                    result=workspace.propose_snapshot_edits(action['edits'])
                else: result=workspace.propose_edits(action['edits'])
            except (ValueError,OSError) as error: result={'error':str(error)[:1000]}
            self.repository.capture(job,seq,result)


def serve(worker,sleep=time.sleep):
    failures=0
    while True:
        try:
            result=worker.run_once()
            failures=0
            if result: print(json.dumps({'id':result['id'],'task_id':result['task_id'],'outcome':result['outcome']}),flush=True)
            else: sleep(1)
        except (psycopg.OperationalError,psycopg.InterfaceError,PoolTimeout) as error:
            # Do not retry a dispatch here. The next database claim uses the durable
            # intent and lease fence to recover captured work or mark uncertainty.
            failures+=1
            delay=min(30,2**min(failures,5))
            print(json.dumps({'event':'database_unavailable','error_type':type(error).__name__,'retry_seconds':delay}),flush=True)
            sleep(delay)


def main():
    repository=InvestigationRepository();repository.initialize()
    serve(InvestigationWorker(repository))

if __name__=='__main__': main()
