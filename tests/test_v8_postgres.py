"""Real PostgreSQL acceptance for the new profile; no model or Docker execution."""
from pathlib import Path
from uuid import uuid4
import shutil
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest
from kairos_api import migrations
from kairos_api.investigations.contracts import CONFIGURATIONS
from kairos_api.investigations.worker import InvestigationWorker
from test_investigations import registry,repository,expire
from test_migrations007 import database
from test_v5_postgres import FixtureChecks,context_for,response_for
from test_v7_postgres import LineProvider


@pytest.mark.parametrize('configuration,seconds,lease',[('loop-v7',600,660),('baseline-v8',600,660),('loop-v8',900,960)])
def test_registered_profile_deadline_and_lease_use_database_clock(repository,configuration,seconds,lease):
    record=repository.enqueue('tenant-a','deadline-'+configuration,'fixture',configuration)
    claimed=repository.claim('first-worker')
    assert abs((claimed['deadline_at']-claimed['started_at']).total_seconds()-seconds)<.1
    assert abs((claimed['lease_expires_at']-claimed['started_at']).total_seconds()-lease)<.1
    expire(repository,record['id'])
    recovered=repository.claim('replacement-worker')
    assert recovered['deadline_at']==claimed['deadline_at']
    assert recovered['started_at']==claimed['started_at'] and recovered['claims']==2


def test_long_profile_counters_are_transactionally_enforced(repository):
    record=repository.enqueue('tenant-a','counters-v8','fixture','loop-v8')
    job=repository.claim('counter-worker')
    for index in range(10):
        seq=repository.begin(job,'model','dispatch',{'fixture_call':index})
        repository.capture(job,seq,{})
    with pytest.raises(ValueError):repository.begin(job,'model','dispatch',{})
    for index in range(4):
        seq=repository.begin(job,'tool','propose_patch',{'fixture_candidate':index})
        repository.capture(job,seq,{'patch':'fixture-'+str(index)})
        seq=repository.begin(job,'tool','run_checks',{})
        repository.capture(job,seq,{'passed':False})
    with pytest.raises(ValueError):repository.begin(job,'tool','run_checks',{})
    seq=repository.begin(job,'tool','propose_patch',{'fixture_candidate':4})
    with pytest.raises(ValueError):repository.capture(job,seq,{'patch':'forbidden-fifth'})
    saved=repository.read(record['id'],'tenant-a')
    assert (saved['model_calls'],saved['patch_count'],saved['check_count'])==(10,4,4)


def test_pending_v8_dispatch_is_unknown_after_expiry_and_never_retried(repository):
    record=repository.enqueue('tenant-a','unknown-v8','fixture','loop-v8')
    job=repository.claim('first-worker')
    repository.begin(job,'model','dispatch',{'captured_intent':True})
    expire(repository,record['id'])
    assert repository.claim('replacement-worker') is None
    saved=repository.read(record['id'],'tenant-a')
    assert saved['outcome']=='unknown_dispatch' and saved['model_calls']==1
    with pytest.raises(RuntimeError):repository.capture(job,1,{'stale':True})


def test_duplicate_v8_candidate_does_not_repeat_independent_check(repository):
    repository.enqueue('tenant-a','duplicate-v8','fixture','loop-v8')
    provider=LineProvider([2,2,3])
    result=InvestigationWorker(repository,provider,FixtureChecks).run_once()
    assert result['outcome']=='verified_repair'
    assert (result['model_calls'],result['patch_count'],result['check_count'])==(3,2,2)


def prefix_migrations(destination,head):
    destination.mkdir()
    for _,path,_ in migrations.revisions()[:head]:shutil.copyfile(path,destination/path.name)


def test_v8_expansion_then_validation_preserves_historical_records_and_checks_new_writes(database,tmp_path):
    first=tmp_path/'before-v8';prefix_migrations(first,4)
    assert migrations.apply(database,first)['head']==4
    identifier=uuid4()
    with psycopg.connect(database,row_factory=dict_row) as connection:
        before=connection.execute("SELECT 'kairos_investigations'::regclass::oid AS oid").fetchone()['oid']
        connection.execute('''INSERT INTO kairos_investigations(id,tenant_id,command_key,command_digest,task_id,
            task_snapshot,task_digest,configuration,config_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (identifier,'migration-fixture','historical','frozen','fixture',Jsonb({'old':True}),
             'frozen','baseline-v7',Jsonb({'old_budget':True})))
    expanded=tmp_path/'expanded';prefix_migrations(expanded,5)
    assert migrations.apply(database,expanded)['head']==5
    with psycopg.connect(database,row_factory=dict_row) as connection:
        checked=connection.execute("SELECT convalidated FROM pg_constraint WHERE conrelid='kairos_investigations'::regclass AND conname='kairos_investigations_configuration_check'").fetchone()
        assert checked['convalidated'] is False
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute('UPDATE kairos_investigations SET configuration=%s WHERE id=%s',('unknown-profile',identifier))
        connection.rollback()
        connection.execute('UPDATE kairos_investigations SET configuration=%s WHERE id=%s',('baseline-v8',identifier))
        connection.rollback()
    assert migrations.apply(database)['head']==6
    with psycopg.connect(database,row_factory=dict_row) as connection:
        assert before==connection.execute("SELECT 'kairos_investigations'::regclass::oid AS oid").fetchone()['oid']
        saved=connection.execute('SELECT configuration,task_snapshot,config_snapshot FROM kairos_investigations WHERE id=%s',(identifier,)).fetchone()
        assert saved=={'configuration':'baseline-v7','task_snapshot':{'old':True},'config_snapshot':{'old_budget':True}}
        assert connection.execute("SELECT convalidated FROM pg_constraint WHERE conrelid='kairos_investigations'::regclass AND conname='kairos_investigations_configuration_check'").fetchone()['convalidated'] is True
    assert migrations.apply(database)['applied']==[]
