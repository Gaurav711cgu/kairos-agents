"""Real Keycloak and PostgreSQL browser journey in a disposable client/schema."""
import json,os,secrets
from pathlib import Path
from uuid import uuid4
import httpx,psycopg,uvicorn
from psycopg import sql
from psycopg.conninfo import make_conninfo
from kairos_api.identity import IdentityRepository
from kairos_api.app import create_app
ROOT=Path(__file__).resolve().parents[1]
def main():
    for line in (ROOT/'.env.kairos.local').read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ[key]=value
    credentials=json.loads((ROOT/'.runtime/identity.local.json').read_text())
    url=os.environ['TEST_DATABASE_URL'];schema='browser_'+uuid4().hex;client_id='kairos-browser-'+uuid4().hex;client_uuid=None
    with psycopg.connect(url,autocommit=True) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    with httpx.Client(timeout=20,trust_env=False) as client:
        response=client.post('http://127.0.0.1:8088/realms/master/protocol/openid-connect/token',data={'grant_type':'password','client_id':'admin-cli','username':'kairos-admin','password':credentials['admin_password']});response.raise_for_status()
        client.headers['Authorization']='Bearer '+response.json()['access_token'];base='http://127.0.0.1:8088/admin/realms/kairos/clients';secret=secrets.token_urlsafe(40)
        try:
            response=client.post(base,json={'clientId':client_id,'enabled':True,'protocol':'openid-connect','publicClient':False,'secret':secret,'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'redirectUris':['http://127.0.0.1:8106/api/auth/callback'],'webOrigins':['http://127.0.0.1:3105'],'attributes':{'pkce.code.challenge.method':'S256'}});response.raise_for_status()
            client_uuid=client.get(base,params={'clientId':client_id}).json()[0]['id']
            database=make_conninfo(url,options='-c search_path='+schema)
            from kairos_api.migrations import apply
            apply(database)
            repo=IdentityRepository(database);repo.initialize()
            with repo.connect() as c:
                for account in credentials['accounts']:
                    if account.get('role'):c.execute('INSERT INTO kairos_memberships(subject,tenant_id,role) VALUES (%s,%s,%s)',(account['subject'],account['tenant_id'],account['role']))
            os.environ.update(DATABASE_URL=database,KAIROS_ENV='development',KAIROS_IDENTITY_MODE='oidc',KAIROS_OIDC_ISSUER='http://127.0.0.1:8088/realms/kairos',KAIROS_OIDC_CLIENT_ID=client_id,KAIROS_OIDC_CLIENT_SECRET=secret,KAIROS_OIDC_CALLBACK='http://127.0.0.1:8106/api/auth/callback',KAIROS_WEB_ORIGIN='http://127.0.0.1:3105',KAIROS_CORS_ORIGINS='http://127.0.0.1:3105',KAIROS_BLOB_DIR=str(ROOT/'.runtime/browser004/blobs'))
            uvicorn.run(create_app(),host='127.0.0.1',port=8106,access_log=False,log_level='warning')
        finally:
            if client_uuid:client.delete(base+'/'+client_uuid)
            with psycopg.connect(url,autocommit=True) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
if __name__=='__main__':main()
