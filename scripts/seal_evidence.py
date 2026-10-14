"""Fingerprint the reviewable working tree and local receipts; not a signed attestation."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence/build002'

def fingerprint(path):
    data=path.read_bytes()
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}

def main():
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    sources={}
    prefixes=('kairos_api/','dashboard/','scripts/','tests/','.github/','docs/')
    root_files={'README.md','ARCHITECTURE.md','BRAIN.md','DESIGN.md','PLAN.md','PLAN_BUILD_002.md','Dockerfile.api','Dockerfile.web','.dockerignore','.gitignore','compose.production.yaml','compose.yaml','requirements-api.txt','requirements-api.lock'}
    for name in sorted(set(names)):
        path=ROOT/name
        if path.is_file() and (name.startswith(prefixes) or name in root_files):sources[name]=fingerprint(path)
    files={str(path.relative_to(ROOT)):fingerprint(path) for path in sorted(EVIDENCE.rglob('*')) if path.is_file() and path.name!='manifest.json'}
    audit=json.loads((EVIDENCE/'npm-audit-all-final.json').read_text())
    python_audit=json.loads((EVIDENCE/'python-audit.json').read_text())
    containers=json.loads((EVIDENCE/'docker-smoke.json').read_text())
    log=(EVIDENCE/'backend-tests-final.txt').read_text()
    assert '169 passed' in log and 'failed' not in log
    assert audit['metadata']['vulnerabilities']['total']==0
    assert all(not dependency.get('vulns') for dependency in python_audit['dependencies'])
    assert containers['passed'] and all(containers['checks'].values())
    report={'build':'002','generated_at':datetime.now(timezone.utc).isoformat(),'repository_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'Active working-tree implementation and local build002 evidence. Changes are not committed or published by this sealing script.','validation':{'backend_passed':169,'backend_dependency_warnings':2,'frontend_boundary_passed':4,'frontend_lint':'pass','frontend_types':'pass','npm_known_findings':0,'api_lock_known_findings':0,'container_smoke':'pass','model_release':'blocked','hosted_ci':'not_run','public_https_deployment':'not_run','outside_user_adoption':'not_measured'},'tested_images':{key:containers[key] for key in ('api_image_id','web_image_id','api_uid','web_uid')},'sources':sources,'evidence':files,'limits':['Local SHA256 fingerprints do not prove immutable history or signed provenance.','Tests and model observations describe recorded revisions and local conditions only.','Historical build001 artifacts remain separate; old published build002 reports preserve earlier source digests.','A calibration pass does not qualify the configured model.']}
    output=EVIDENCE/'manifest.json';output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Sealed {len(sources)} source files and {len(files)} evidence files; model release blocked.')

if __name__=='__main__':main()
