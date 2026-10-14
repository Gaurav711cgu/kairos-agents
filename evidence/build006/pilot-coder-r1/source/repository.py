"""Durable investigation commands and fenced per-step capture."""
import os
import base64
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb
from kairos_api.jobs_repository import public_value
from kairos_api.model_runtime import BlobStore, digest
from kairos_api.investigations.contracts import CONFIGURATIONS, generation_for
from kairos_api.investigations.registry import CaseRegistry


class InvestigationRepository:
    def __init__(self,database_url=None,blob_root=None,registry=None,pooled=False):
        self.database_url=database_url or os.environ['DATABASE_URL']
        self.blobs=BlobStore(blob_root)
        self.registry=registry or CaseRegistry()
        self.pool=ConnectionPool(self.database_url,min_size=1,max_size=8,max_waiting=32,timeout=5,open=True,
            kwargs={'row_factory':dict_row,'connect_timeout':5},check=ConnectionPool.check_connection) if pooled else None

    def connect(self):
        return self.pool.connection() if self.pool else psycopg.connect(self.database_url,row_factory=dict_row,connect_timeout=5)

    def close(self):
        if self.pool: self.pool.close()

    def initialize(self):
        with self.connect() as connection:
            if connection.execute('SHOW fsync').fetchone()['fsync']!='on':
                raise RuntimeError('Durable capture requires fsync')
            connection.execute(Path(__file__).with_name('schema.sql').read_text())
            for row in connection.execute('SELECT id,config_snapshot FROM kairos_investigations WHERE config_digest IS NULL').fetchall():
                connection.execute('UPDATE kairos_investigations SET config_digest=%s WHERE id=%s',(digest(row['config_snapshot']),row['id']))

    def _row(self,connection,identifier,tenant=None,public=False,lock=False):
        try: UUID(str(identifier))
        except ValueError: raise HTTPException(404,'Investigation not found') from None
        query='SELECT * FROM kairos_investigations WHERE id=%s';params=[identifier]
        if public: query+=' AND published=true'
        elif tenant is not None: query+=' AND tenant_id=%s';params.append(tenant)
        row=connection.execute(query+(' FOR UPDATE' if lock else ''),params).fetchone()
        if not row: raise HTTPException(404,'Investigation not found')
        return row

    def enqueue(self,tenant,key,task_id,configuration='loop-v3',parent_id=None):
        if configuration not in CONFIGURATIONS: raise HTTPException(422,'Unknown configuration')
        case=self.registry.get(task_id)
        command_hash=digest({'task_id':task_id,'configuration':configuration,'parent_id':parent_id})
        identifier=str(uuid4())
        config={'version':configuration,'budgets':CONFIGURATIONS[configuration],'generation':generation_for(configuration),
                'model_manifest_digest':self._model_digest()}
        with self.connect() as connection:
            connection.execute('SET LOCAL synchronous_commit=on')
            connection.execute('SELECT pg_advisory_xact_lock(796342193)')
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('investigations:'+tenant,))
            existing=connection.execute('SELECT id,command_digest FROM kairos_investigations WHERE tenant_id=%s AND command_key=%s',(tenant,key)).fetchone()
            if existing:
                if existing['command_digest']!=command_hash: raise HTTPException(409,'Request key already binds another investigation')
                identifier=str(existing['id'])
            else:
                if parent_id:
                    parent=self._row(connection,parent_id,tenant,lock=True)
                    if parent['task_id']!=task_id or parent['task_digest']!=self.registry.fingerprint(case):
                        raise HTTPException(409,'Fork requires identical source and verification provenance')
                count=connection.execute("SELECT count(*) AS n FROM kairos_investigations WHERE tenant_id=%s AND status IN ('queued','running')",(tenant,)).fetchone()['n']
                if count>=6: raise HTTPException(429,'Active investigation quota reached')
                global_count=connection.execute("SELECT count(*) AS n FROM kairos_investigations WHERE status IN ('queued','running')").fetchone()['n']
                if global_count>=24: raise HTTPException(429,'Global investigation queue capacity reached')
                connection.execute('''INSERT INTO kairos_investigations
                    (id,tenant_id,command_key,command_digest,task_id,task_snapshot,task_digest,configuration,config_snapshot,parent_id,config_digest,registry_version)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (identifier,tenant,key,command_hash,task_id,Jsonb(case),self.registry.fingerprint(case),configuration,Jsonb(config),parent_id,digest(config),self.registry.manifest()['version']))
        return self.read(identifier,tenant)

    def _model_digest(self):
        # Runtime is configurable for isolated tests and deployments; explicit manifest wins.
        path=Path(os.environ.get('KAIROS_INVESTIGATION_MODEL_MANIFEST',Path(__file__).resolve().parents[2]/'evidence/build003/inference-runtime.json'))
        return digest(__import__('json').loads(path.read_text())) if path.exists() else None

    def read(self,identifier,tenant=None,public=False):
        with self.connect() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            row=self._row(connection,identifier,tenant,public)
            steps=connection.execute('SELECT * FROM kairos_investigation_steps WHERE investigation_id=%s ORDER BY seq',(identifier,)).fetchall()
            artifacts=connection.execute('SELECT sha256,bytes FROM kairos_investigation_artifacts WHERE investigation_id=%s',(identifier,)).fetchall()
        valid=True
        normalized=public_value(steps)
        for index,step in enumerate(normalized,1):
            valid=valid and step['seq']==index
            for field in ['request','result']:
                capture=step[field]
                if capture is None: continue
                try: valid=valid and self.blobs.get(capture['sha256'])==capture['body'] and digest(capture['body'])==capture['sha256']
                except (OSError,ValueError,KeyError): valid=False
        result=public_value(row)
        for key in ['tenant_id','command_key','command_digest','lease_owner','lease_token','lease_expires_at']:
            result.pop(key,None)
        valid=valid and digest({'case':row['task_snapshot'],'registry_version':row['registry_version']})==row['task_digest']
        valid=valid and digest(row['config_snapshot'])==row['config_digest']
        result.update(steps=normalized,artifacts=public_value(artifacts),integrity={'verified':bool(valid),'scope':'Stored snapshots and content-addressed captures; not immutable history'})
        return result

    def page(self,tenant=None,public=False,limit=25,cursor=None):
        if not 1<=limit<=100: raise HTTPException(422,'Page size must be between 1 and 100')
        scope=digest({'tenant':None if public else tenant,'public':public})
        where='published=true' if public else 'tenant_id=%s'
        params=[] if public else [tenant]
        if cursor:
            try:
                if len(cursor)>1024: raise ValueError()
                value=json.loads(base64.urlsafe_b64decode(cursor+'='*(-len(cursor)%4)))
                if value['version']!=1 or value['scope']!=scope: raise ValueError()
                stamp=datetime.fromisoformat(value['created_at'])
                if stamp.tzinfo is None: raise ValueError()
                identifier=str(UUID(value['id']))
            except (ValueError,KeyError,TypeError,UnicodeError):
                raise HTTPException(422,'Invalid listing cursor') from None
            where+=' AND (created_at,id)<(%s,%s::uuid)';params.extend([stamp,identifier])
        params.append(limit+1)
        with self.connect() as connection:
            rows=connection.execute("""SELECT id,task_id,task_snapshot->>'title' AS title,configuration,status,outcome,
                       summary,created_at,updated_at,model_calls,patch_count,check_count,parent_id,published
                       FROM kairos_investigations WHERE """+where+' ORDER BY created_at DESC,id DESC LIMIT %s',params).fetchall()
        records=public_value(rows[:limit]);next_cursor=None
        if len(rows)>limit:
            last=records[-1]
            token={'version':1,'scope':scope,'created_at':last['created_at'],'id':last['id']}
            next_cursor=base64.urlsafe_b64encode(json.dumps(token,separators=(',',':')).encode()).decode().rstrip('=')
        return {'investigations':records,'next_cursor':next_cursor}

    def list(self,tenant=None,public=False):
        # Compatibility for local scripts; HTTP lists use explicit cursor pages.
        return self.page(tenant,public,100)['investigations']

    def progress(self,identifier,tenant):
        with self.connect() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            row=self._row(connection,identifier,tenant)
            latest=connection.execute('SELECT seq,kind,name,state FROM kairos_investigation_steps WHERE investigation_id=%s ORDER BY seq DESC LIMIT 1',(identifier,)).fetchone()
        phase=row['status']
        if row['status']=='running':
            if not latest: phase='preparing_workspace'
            elif latest['kind']=='model' and latest['state']=='pending': phase='model_dispatch_pending'
            elif latest['name']=='run_checks' and latest['state']=='pending': phase='verification_running'
            elif latest['state']=='pending': phase='tool_running'
            else: phase='result_captured'
        result={key:row[key] for key in ('id','status','outcome','model_calls','patch_count','check_count','updated_at')}
        result.update(phase=phase,latest_sequence=latest['seq'] if latest else 0)
        return public_value(result)

    def cancel(self,identifier,tenant):
        with self.connect() as connection:
            row=self._row(connection,identifier,tenant,lock=True)
            if row['status'] in {'queued','running'}:
                connection.execute("UPDATE kairos_investigations SET cancel_requested=true,status='cancelled',outcome='cancelled',lease_token=lease_token+1,lease_owner=NULL,lease_expires_at=NULL,updated_at=clock_timestamp() WHERE id=%s",(identifier,))
        return self.read(identifier,tenant)

    def publish(self,identifier,tenant):
        record=self.read(identifier,tenant)
        if not record['integrity']['verified']: raise HTTPException(409,'Corrupt investigation cannot be published')
        if record['status'] in {'queued','running'}: raise HTTPException(409,'Publish only terminal investigations')
        with self.connect() as connection:
            self._row(connection,identifier,tenant,lock=True)
            connection.execute('UPDATE kairos_investigations SET published=true WHERE id=%s',(identifier,))
        return self.read(identifier,tenant)

    def claim(self,owner):
        with self.connect() as connection:
            connection.execute('SELECT pg_advisory_xact_lock(796342193)')
            expired=connection.execute("SELECT * FROM kairos_investigations WHERE status='running' AND lease_expires_at<=clock_timestamp() FOR UPDATE").fetchall()
            for row in expired:
                unknown=connection.execute("SELECT 1 FROM kairos_investigation_steps WHERE investigation_id=%s AND kind='model' AND state='pending'",(row['id'],)).fetchone()
                status='unknown' if unknown else 'queued'
                if not unknown and row['claims']>=3: status='failed'
                if not unknown and row['deadline_at'] and connection.execute('SELECT %s::timestamptz<=clock_timestamp() AS expired',(row['deadline_at'],)).fetchone()['expired']: status='timed_out'
                connection.execute('UPDATE kairos_investigations SET status=%s,outcome=%s,lease_token=lease_token+1,lease_owner=NULL,lease_expires_at=NULL WHERE id=%s',(status,'unknown_dispatch' if unknown else ('timeout' if status=='timed_out' else ('claim_budget_exhausted' if status=='failed' else None)),row['id']))
            if connection.execute("SELECT 1 FROM kairos_investigations WHERE status='running'").fetchone(): return None
            row=connection.execute("SELECT * FROM kairos_investigations WHERE status='queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED").fetchone()
            if not row: return None
            return connection.execute("""UPDATE kairos_investigations SET status='running',claims=claims+1,lease_token=lease_token+1,
                    lease_owner=%s,lease_expires_at=clock_timestamp()+interval '660 seconds',started_at=coalesce(started_at,clock_timestamp()),
                    deadline_at=coalesce(deadline_at,clock_timestamp()+interval '600 seconds'),updated_at=clock_timestamp()
                    WHERE id=%s RETURNING *""",(owner,row['id'])).fetchone()

    def fenced(self,connection,job):
        row=self._row(connection,job['id'],lock=True)
        expired=connection.execute('SELECT %s::timestamptz<=clock_timestamp() AS expired',(row['lease_expires_at'],)).fetchone()['expired']
        if row['status']!='running' or row['lease_token']!=job['lease_token'] or row['lease_owner']!=job['lease_owner'] or expired:
            raise RuntimeError('Stale investigation lease rejected')
        return row

    def remaining(self,job):
        with self.connect() as connection:
            row=self.fenced(connection,job)
            return max(0,connection.execute('SELECT extract(epoch FROM (%s::timestamptz-clock_timestamp())) AS seconds',(row['deadline_at'],)).fetchone()['seconds'])

    def _capture(self,connection,job,value):
        blob=self.blobs.put(value)
        connection.execute('INSERT INTO kairos_investigation_artifacts VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(job['id'],blob['sha256'],blob['bytes']))
        return {'sha256':blob['sha256'],'body':value}

    def begin(self,job,kind,name,request):
        with self.connect() as connection:
            connection.execute('SET LOCAL synchronous_commit=on');row=self.fenced(connection,job)
            if self._expired(connection,row): raise TimeoutError('Investigation deadline exhausted')
            pending=connection.execute("SELECT * FROM kairos_investigation_steps WHERE investigation_id=%s AND state='pending' ORDER BY seq DESC LIMIT 1",(job['id'],)).fetchone()
            if pending:
                if pending['kind']=='model': raise RuntimeError('Unknown model dispatch cannot be repeated')
                if pending['kind']==kind and pending['name']==name and pending['request']['body']==request: return pending['seq']
                raise RuntimeError('Pending step requires recovery')
            counter={'model':'model_calls','propose_patch':'patch_count','run_checks':'check_count'}.get(kind if kind=='model' else name)
            if counter=='patch_count' and row['configuration'].endswith(('-v4','-v5')): counter=None
            if counter:
                limit={'model_calls':'max_calls','patch_count':'max_patches','check_count':'max_checks'}[counter]
                if row[counter]>=row['config_snapshot']['budgets'][limit]: raise ValueError('Investigation '+limit+' exhausted')
                connection.execute(f'UPDATE kairos_investigations SET {counter}={counter}+1 WHERE id=%s',(job['id'],))
            seq=connection.execute('SELECT coalesce(max(seq),0)+1 AS seq FROM kairos_investigation_steps WHERE investigation_id=%s',(job['id'],)).fetchone()['seq']
            capture=self._capture(connection,job,request)
            connection.execute('INSERT INTO kairos_investigation_steps (investigation_id,seq,kind,name,state,request) VALUES (%s,%s,%s,%s,\'pending\',%s)',(job['id'],seq,kind,name,Jsonb(capture)))
        return seq

    def capture(self,job,seq,result):
        with self.connect() as connection:
            connection.execute('SET LOCAL synchronous_commit=on');self.fenced(connection,job)
            row=self.fenced(connection,job)
            step=connection.execute('SELECT name FROM kairos_investigation_steps WHERE investigation_id=%s AND seq=%s',(job['id'],seq)).fetchone()
            if row['configuration'].endswith(('-v4','-v5')) and step and step['name']=='propose_patch' and 'error' not in result:
                if row['patch_count']>=row['config_snapshot']['budgets']['max_patches']: raise ValueError('Applied patch budget exhausted')
                connection.execute('UPDATE kairos_investigations SET patch_count=patch_count+1 WHERE id=%s',(job['id'],))
            capture=self._capture(connection,job,result)
            updated=connection.execute("UPDATE kairos_investigation_steps SET state='captured',result=%s,captured_at=clock_timestamp() WHERE investigation_id=%s AND seq=%s AND state='pending' RETURNING seq",(Jsonb(capture),job['id'],seq)).fetchone()
            if not updated: raise RuntimeError('Step is not pending')
            connection.execute('UPDATE kairos_investigations SET updated_at=clock_timestamp() WHERE id=%s',(job['id'],))

    def _expired(self,connection,row):
        return connection.execute('SELECT %s::timestamptz<=clock_timestamp() AS expired',(row['deadline_at'],)).fetchone()['expired']

    def finish(self,job,outcome,summary=''):
        with self.connect() as connection:
            row=self.fenced(connection,job)
            if self._expired(connection,row) and outcome!='unknown_dispatch': outcome='timeout'
            status={'unknown_dispatch':'unknown','timeout':'timed_out','environment_failure':'failed','invalid_response':'failed'}.get(outcome,'completed')
            connection.execute('''UPDATE kairos_investigations SET status=%s,outcome=%s,summary=%s,lease_owner=NULL,
                    lease_expires_at=NULL,updated_at=clock_timestamp() WHERE id=%s''',(status,outcome,summary[:2000],job['id']))
        return self.read(str(job['id']),job['tenant_id'])
