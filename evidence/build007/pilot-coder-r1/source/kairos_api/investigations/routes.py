"""Scoped investigation commands and read-only published evidence."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from kairos_api.model_runtime import canonical, digest


class CreateInvestigation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    task_id:str
    configuration:Literal['loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5','loop-v6','baseline-v6','loop-v7','baseline-v7']='loop-v3'


class ForkInvestigation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    configuration:Literal['loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5','loop-v6','baseline-v6','loop-v7','baseline-v7']='loop-v3'


def create_investigation_router(tenant,key,admin,repository):
    router=APIRouter()

    @router.get('/api/investigations/cases')
    def cases(_tenant=Depends(tenant),repo=Depends(repository)):
        return {'cases':repo.registry.cases()}

    @router.get('/api/investigations')
    def listing(workspace=Depends(tenant),repo=Depends(repository),limit:int=Query(25,ge=1,le=100),cursor:str|None=Query(None,max_length=1024)):
        return repo.page(workspace,limit=limit,cursor=cursor)

    @router.post('/api/investigations',status_code=202)
    def create(command:CreateInvestigation,workspace=Depends(tenant),identity=Depends(key),repo=Depends(repository)):
        return repo.enqueue(workspace,identity,command.task_id,command.configuration)

    @router.get('/api/investigations/{identifier}')
    def detail(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        return repo.read(identifier,workspace)

    @router.post('/api/investigations/{identifier}/cancel')
    def cancel(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        return repo.cancel(identifier,workspace)

    @router.post('/api/investigations/{identifier}/fork',status_code=202)
    def fork(identifier:str,command:ForkInvestigation,workspace=Depends(tenant),identity=Depends(key),repo=Depends(repository)):
        parent=repo.read(identifier,workspace)
        return repo.enqueue(workspace,identity,parent['task_id'],command.configuration,identifier)

    @router.post('/api/investigations/{identifier}/publish')
    def publish(identifier:str,workspace=Depends(admin),repo=Depends(repository)):
        return repo.publish(identifier,workspace)

    @router.get('/api/investigations/{identifier}/replay')
    def replay(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        record=repo.read(identifier,workspace)
        if not record['integrity']['verified']: raise HTTPException(409,'Capture integrity mismatch')
        return {'mode':'recorded-playback','network_calls':0,'tool_executions':0,'investigation':record}

    @router.get('/api/public/investigations')
    def public_listing(repo=Depends(repository),limit:int=Query(25,ge=1,le=100),cursor:str|None=Query(None,max_length=1024)):
        return repo.page(public=True,limit=limit,cursor=cursor)

    @router.get('/api/public/investigations/{identifier}')
    def public_detail(identifier:str,repo=Depends(repository)):
        return repo.read(identifier,public=True)

    def download(record,identifier,kind):
        if not record['integrity']['verified']: raise HTTPException(409,'Capture integrity mismatch')
        headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store'}
        if kind=='bundle':
            headers['Content-Disposition']=f'attachment; filename="kairos-{identifier}.json"'
            return Response(canonical(record),media_type='application/json',headers=headers)
        patches=[s for s in record['steps'] if s['name']=='propose_patch' and s['state']=='captured' and 'error' not in s['result']['body']]
        selection=next((s['result']['body'].get('selected_patch_digest') for s in reversed(record['steps']) if s['name']=='draft_selection' and s['state']=='captured'),None)
        if selection: patches=[s for s in patches if digest(s['result']['body'].get('patch',''))==selection]
        if not patches: raise HTTPException(404,'No accepted patch in this investigation')
        headers['Content-Disposition']=f'attachment; filename="kairos-{identifier}.patch"'
        return Response(patches[-1]['result']['body'].get('patch',patches[-1]['request']['body'].get('patch','')),media_type='text/plain',headers=headers)

    @router.get('/api/investigations/{identifier}/progress')
    def progress(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        return repo.progress(identifier,workspace)

    @router.get('/api/investigations/{identifier}/bundle')
    def private_bundle(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        return download(repo.read(identifier,workspace),identifier,'bundle')

    @router.get('/api/investigations/{identifier}/patch')
    def private_patch(identifier:str,workspace=Depends(tenant),repo=Depends(repository)):
        return download(repo.read(identifier,workspace),identifier,'patch')

    @router.get('/api/public/investigations/{identifier}/bundle')
    def bundle(identifier:str,repo=Depends(repository)):
        return download(repo.read(identifier,public=True),identifier,'bundle')

    @router.get('/api/public/investigations/{identifier}/patch')
    def patch(identifier:str,repo=Depends(repository)):
        return download(repo.read(identifier,public=True),identifier,'patch')

    return router
