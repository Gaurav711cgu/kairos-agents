"""Actual PostgreSQL v7 budgets and capture recovery; provider/checks are fixtures."""
from test_investigations import registry,repository
from test_v5_postgres import FixtureChecks,context_for,response_for
from kairos_api.investigations.worker import InvestigationWorker


class LineProvider:
    def __init__(self,values):self.values=values;self.calls=0
    def prepare(self,case,configuration,observations,budgets):
        context=context_for(observations);self.handle=next(iter(context['reference_bindings']))
        return {'fixture_only':True},context
    def __call__(self,request,seconds):
        value=self.values[self.calls];self.calls+=1
        return response_for({'action':'propose_patch','edits':[{'source_id':self.handle,'start_line':1,'end_line':1,'new':f'value = {value}\n'}]})


def test_duplicate_failed_candidate_does_not_spend_second_check(repository):
    repository.enqueue('tenant-a','duplicate-v7','fixture','loop-v7')
    provider=LineProvider([2,2,3])
    result=InvestigationWorker(repository,provider,FixtureChecks).run_once()
    assert result['outcome']=='verified_repair'
    assert result['model_calls']==3 and result['patch_count']==2 and result['check_count']==2
    duplicates=[step for step in result['steps'] if step['name']=='propose_patch' and step['result']['body'].get('duplicate_candidate')]
    assert len(duplicates)==1 and duplicates[0]['result']['body']['cached_verification']['passed'] is False


def test_two_identical_invalid_candidates_stop_without_checks(repository):
    repository.enqueue('tenant-a','invalid-v7','fixture','loop-v7')
    class InvalidProvider(LineProvider):
        def __call__(self,request,seconds):
            self.calls+=1
            return response_for({'action':'propose_patch','edits':[{'source_id':self.handle,'start_line':1,'end_line':999,'new':'value = 2\n'}]})
    provider=InvalidProvider([])
    result=InvestigationWorker(repository,provider,FixtureChecks).run_once()
    assert result['outcome']=='invalid_patch' and result['model_calls']==2
    assert result['patch_count']==0 and result['check_count']==0
    assert 'Two identical rejected candidates' in result['summary']
