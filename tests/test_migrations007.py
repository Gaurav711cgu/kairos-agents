"""Real PostgreSQL migration adoption, lock bounds and read-only startup."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import subprocess
import sys
import time
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from kairos_api import migrations
from kairos_api.investigations.repository import InvestigationRepository


@pytest.fixture
def database():
    url=os.environ.get('TEST_DATABASE_URL')
    if not url:pytest.skip('TEST_DATABASE_URL required')
    schema='migration007_'+uuid4().hex
    with psycopg.connect(url,autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    isolated=make_conninfo(url,options='-c search_path='+schema)
    try:yield isolated
    finally:
        with psycopg.connect(url,autocommit=True) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_revision_files_have_contiguous_checksums():
    rows=migrations.revisions()
    assert [row[0] for row in rows]==list(range(1, len(rows) + 1))
    assert all(len(row[2])==64 for row in rows)


def test_revision_gap_rejected(tmp_path):
    (tmp_path/'0002_wrong.sql').write_text('SELECT 1;')
    with pytest.raises(RuntimeError,match='contiguous'):migrations.revisions(tmp_path)


def test_fresh_apply_repeat_preserves_constraint_ids(database):
    assert migrations.apply(database)['head']==len(migrations.revisions())
    with psycopg.connect(database,row_factory=dict_row) as connection:
        before=connection.execute('SELECT oid FROM pg_constraint WHERE conrelid=%s::regclass ORDER BY oid',('kairos_investigations',)).fetchall()
    assert migrations.apply(database)['applied']==[]
    InvestigationRepository(database).initialize()
    with psycopg.connect(database,row_factory=dict_row) as connection:
        assert before==connection.execute('SELECT oid FROM pg_constraint WHERE conrelid=%s::regclass ORDER BY oid',('kairos_investigations',)).fetchall()


def test_build006_adoption_does_not_recreate_tables(database):
    with psycopg.connect(database,row_factory=dict_row) as connection:
        connection.execute((migrations.DIRECTORY/'0001_build006_baseline.sql').read_text())
        before=connection.execute("SELECT 'kairos_investigations'::regclass::oid AS oid").fetchone()['oid']
    result=migrations.apply(database)
    assert result['applied'][0]['origin']=='adopted-build006'
    with psycopg.connect(database,row_factory=dict_row) as connection:
        assert before==connection.execute("SELECT 'kairos_investigations'::regclass::oid AS oid").fetchone()['oid']


def test_unrecognized_catalog_refuses_adoption(database):
    with psycopg.connect(database) as connection:connection.execute('CREATE TABLE kairos_runs(id integer)')
    with pytest.raises(RuntimeError,match='Unrecognized legacy catalog'):migrations.apply(database)
    assert not migrations.status(database)['managed']


def test_startup_refuses_pending_migrations(database):
    with pytest.raises(RuntimeError,match='migrations pending'):InvestigationRepository(database).initialize()


def test_concurrent_migrators_apply_each_revision_once(database):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:migrations.apply(database),range(2)))
    assert sum(len(row['applied']) for row in results)==len(migrations.revisions())


def test_checksum_drift_rejected_before_changes(database,tmp_path):
    migrations.apply(database)
    for path in migrations.DIRECTORY.glob('*.sql'):(tmp_path/path.name).write_bytes(path.read_bytes())
    path=tmp_path/'0002_configuration_v7_expand.sql';path.write_text(path.read_text()+'\n-- changed\n')
    with pytest.raises(RuntimeError,match='checksum'):migrations.apply(database,tmp_path)


def test_catalog_drift_rejected(database):
    migrations.apply(database)
    with psycopg.connect(database) as connection:connection.execute('ALTER TABLE kairos_investigations ADD COLUMN unexpected text')
    with pytest.raises(RuntimeError,match='catalog differs'):InvestigationRepository(database).initialize()


def test_table_lock_timeout_rolls_back_revision(database,tmp_path):
    migrations.apply(database)
    for path in migrations.DIRECTORY.glob('*.sql'):(tmp_path/path.name).write_bytes(path.read_bytes())
    (tmp_path/f'{len(migrations.revisions())+1:04d}_lock_probe.sql').write_text('ALTER TABLE kairos_investigations ADD COLUMN lock_probe text;')
    with psycopg.connect(database) as blocker:
        blocker.execute('LOCK TABLE kairos_investigations IN ACCESS EXCLUSIVE MODE')
        with pytest.raises(psycopg.errors.LockNotAvailable):migrations.apply(database,tmp_path)
    assert migrations.status(database)['pending']==[]
    with psycopg.connect(database,row_factory=dict_row) as connection:
        assert 'lock_probe' not in [row['name'] for row in migrations.catalog(connection)['kairos_investigations']['columns']]


def test_killed_migrator_rolls_back_then_resumes(database,tmp_path):
    migrations.apply(database)
    for path in migrations.DIRECTORY.glob('*.sql'):(tmp_path/path.name).write_bytes(path.read_bytes())
    revision=tmp_path/f'{len(migrations.revisions())+1:04d}_interruption.sql'
    revision.write_text('CREATE TABLE kairos_interruption_probe(id integer); SELECT pg_sleep(8);')
    code='from kairos_api.migrations import apply; import os; apply(os.environ["MIGRATION_TEST_URL"],os.environ["MIGRATION_TEST_DIRECTORY"])'
    env={**os.environ,'MIGRATION_TEST_URL':database,'MIGRATION_TEST_DIRECTORY':str(tmp_path)}
    process=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        found=False
        for _ in range(100):
            with psycopg.connect(database) as connection:
                found=bool(connection.execute("SELECT 1 FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND query LIKE 'CREATE TABLE kairos_interruption_probe%%' AND state='active'").fetchone())
            if found:break
            if process.poll() is not None:pytest.fail('Migrator exited before interruption boundary')
            time.sleep(.05)
        assert found
        process.kill();process.wait(timeout=5)
        # PostgreSQL observes socket loss at its next interrupt/check boundary.
        time.sleep(8.2)
        with psycopg.connect(database) as connection:
            assert connection.execute("SELECT to_regclass('kairos_interruption_probe')").fetchone()[0] is None
            assert connection.execute('SELECT max(version) FROM kairos_schema_migrations').fetchone()[0]==len(migrations.revisions())
        assert migrations.apply(database,tmp_path)['head']==len(migrations.revisions())+1
        assert migrations.apply(database,tmp_path)['applied']==[]
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)


def test_runtime_role_can_verify_but_cannot_migrate(database):
    migrations.apply(database)
    role='runtime007_'+uuid4().hex
    with psycopg.connect(database,autocommit=True,row_factory=dict_row) as connection:
        schema=connection.execute('SELECT current_schema() AS schema').fetchone()['schema']
        connection.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
        connection.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
        connection.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
    restricted=make_conninfo(database,options=f'-c search_path={schema} -c role={role}')
    try:
        InvestigationRepository(restricted).initialize()
        with psycopg.connect(restricted) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):connection.execute('CREATE TABLE forbidden(id integer)')
    finally:
        with psycopg.connect(database,autocommit=True) as connection:
            connection.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            connection.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_explicit_backfill_batches_and_repeat_preserve_existing_values(database):
    from psycopg.types.json import Jsonb
    from kairos_api.model_runtime import digest
    migrations.apply(database)
    with psycopg.connect(database) as connection:
        for index in range(205):
            connection.execute('''INSERT INTO kairos_investigations(id,tenant_id,command_key,command_digest,task_id,
              task_snapshot,task_digest,configuration,config_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
              (uuid4(),'backfill',str(index),'fixture','fixture',Jsonb({}),'fixture','baseline-v7',Jsonb({'fixture':index})))
    receipt=migrations.backfill(database)
    assert receipt['investigation-config-digest-v2']['updated_rows']==205
    assert receipt['investigation-config-digest-v2']['completed'] is True
    with psycopg.connect(database,row_factory=dict_row) as connection:
        before=connection.execute('SELECT id,config_digest FROM kairos_investigations ORDER BY id').fetchall()
        assert all(row['config_digest'] for row in before)
    assert migrations.backfill(database)['investigation-config-digest-v2']['updated_rows']==205
    with psycopg.connect(database,row_factory=dict_row) as connection:
        assert before==connection.execute('SELECT id,config_digest FROM kairos_investigations ORDER BY id').fetchall()


def test_completed_backfill_refuses_changed_operation_semantics(database,monkeypatch):
    from kairos_api import backfill_operations
    migrations.apply(database);migrations.backfill(database)
    original=backfill_operations.OPERATIONS['investigation-config-digest-v2']
    monkeypatch.setitem(backfill_operations.OPERATIONS,'investigation-config-digest-v2',{**original,'algorithm':'changed-under-same-identity'})
    with pytest.raises(RuntimeError,match='Backfill identity differs'):
        migrations.backfill(database)
