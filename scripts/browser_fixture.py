"""Test-only identity fixture on a separate loopback port; never used by main API."""
from fastapi import FastAPI, Request, HTTPException
import uvicorn
import json
from pathlib import Path
from fastapi.responses import Response
ROOT=Path(__file__).resolve().parents[1]
# Genuine public captures support current and historical comparisons. Identity
# remains an explicitly isolated fixture; no test record is a new model result.
manifest=json.loads((ROOT/'dashboard/evidence/manifest.json').read_text())
RECORDS={identifier:json.loads((ROOT/'dashboard/evidence'/entry['path']).read_text())
         for identifier,entry in manifest['records'].items()}
app=FastAPI()
READS=[]
@app.post("/testing/reset-reads")
def reset_reads():
    READS.clear();return {"ok":True}
@app.get("/testing/reads")
def reads():
    return {"ids":list(READS)}
@app.get('/api/auth/me')
def me(request:Request):
    session=request.cookies.get('kairos_session','')
    if not session.startswith('fixture-'): raise HTTPException(401)
    return {'subject':'isolated-browser','tenant_id':'browser-fixture','role':session.removeprefix('fixture-')}
@app.get('/api/public/investigations')
def listing():
    keys=('id','task_id','configuration','status','outcome','summary','created_at','updated_at','model_calls','patch_count','check_count','parent_id','published')
    return {'investigations':[{**{key:row[key] for key in keys},'title':row['task_snapshot']['title']} for row in RECORDS.values()],'next_cursor':None}
@app.get('/api/public/investigations/{identifier}')
def detail(identifier:str):
    if identifier not in RECORDS:raise HTTPException(404)
    READS.append(identifier)
    return RECORDS[identifier]
@app.get('/api/public/investigations/{identifier}/{kind}')
def download(identifier:str,kind:str):
    row=detail(identifier)
    if kind=='bundle':return Response(json.dumps(row),media_type='application/json',headers={'Content-Disposition':'attachment; filename="recorded-fixture.json"'})
    if kind=='patch':
        patches=[step['result']['body']['patch'] for step in row['steps'] if step['name']=='propose_patch' and step['result'] and 'patch' in step['result']['body']]
        if not patches:raise HTTPException(404)
        return Response(patches[-1],media_type='text/x-diff',headers={'Content-Disposition':'attachment; filename="recorded-fixture.patch"'})
    raise HTTPException(404)
if __name__=='__main__': uvicorn.run(app,host='127.0.0.1',port=8195,access_log=False)
