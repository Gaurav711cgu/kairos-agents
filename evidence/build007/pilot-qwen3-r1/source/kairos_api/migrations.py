"""Explicit, checksummed PostgreSQL migrations; runtime initialization is read-only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

DIRECTORY = Path(__file__).with_suffix('')
LEDGER = 'kairos_schema_migrations'


def revisions(directory=DIRECTORY):
    files = sorted(Path(directory).glob('[0-9][0-9][0-9][0-9]_*.sql'))
    numbers = [int(path.name[:4]) for path in files]
    if not files or numbers != list(range(1, len(files) + 1)):
        raise RuntimeError('Migration revisions must be contiguous from 0001')
    return [(number, path, hashlib.sha256(path.read_bytes()).hexdigest())
            for number, path in zip(numbers, files)]


def catalog(connection, schema=None):
    """Normalize owned catalog definitions, ignoring physical IDs and column order."""
    schema = schema or connection.execute('SELECT current_schema() AS name').fetchone()['name']
    tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s AND tablename LIKE 'kairos_%%' AND tablename<>%s ORDER BY tablename", (schema, LEDGER)).fetchall()
    result = {}
    def normalized(value):
        return value.replace('"' + schema + '".', '').replace(schema + '.', '') if value else value
    for table in tables:
        name = table['tablename']
        columns = connection.execute('''SELECT a.attname AS name, format_type(a.atttypid,a.atttypmod) AS type,
          a.attnotnull AS required, pg_get_expr(d.adbin,d.adrelid) AS default
          FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
          LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
          WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attname''', (schema,name)).fetchall()
        constraints = connection.execute('''SELECT conname AS name, contype AS type, convalidated AS validated,
          pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
          JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s AND t.relname=%s ORDER BY conname''', (schema,name)).fetchall()
        indexes = connection.execute('SELECT indexname AS name,indexdef AS definition FROM pg_indexes WHERE schemaname=%s AND tablename=%s ORDER BY indexname',(schema,name)).fetchall()
        result[name] = {key:[{k:normalized(v) if isinstance(v,str) else v for k,v in row.items()} for row in rows]
                        for key,rows in [('columns',columns),('constraints',constraints),('indexes',indexes)]}
    return result


def catalog_digest(connection):
    return hashlib.sha256(json.dumps(catalog(connection),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def applied(connection):
    if not connection.execute('SELECT to_regclass(%s) AS name',(LEDGER,)).fetchone()['name']:
        return []
    return connection.execute(sql.SQL('SELECT * FROM {} ORDER BY version').format(sql.Identifier(LEDGER))).fetchall()


def verify_chain(rows, files):
    if [row['version'] for row in rows] != list(range(1,len(rows)+1)):
        raise RuntimeError('Migration ledger has a missing revision')
    if len(rows)>len(files):
        raise RuntimeError('Database contains an unknown future migration')
    for row,(version,path,checksum) in zip(rows,files):
        if (row['version'],row['name'],row['sha256']) != (version,path.name,checksum):
            raise RuntimeError('Applied migration checksum or name changed')


def verify(connection, directory=DIRECTORY):
    """Verify head and durability without executing DDL, backfills or SET commands."""
    if connection.execute('SHOW fsync').fetchone()['fsync'] != 'on':
        raise RuntimeError('Durable capture requires PostgreSQL fsync=on')
    files=revisions(directory); rows=applied(connection); verify_chain(rows,files)
    if len(rows)!=len(files):
        raise RuntimeError('Database migrations pending; run python3 -m scripts.migrate apply with migration credentials')
    if catalog_digest(connection)!=rows[-1]['schema_digest']:
        raise RuntimeError('Database catalog differs from applied migration head')


def status(database_url, directory=DIRECTORY):
    with psycopg.connect(database_url,row_factory=dict_row,connect_timeout=5) as connection:
        rows=applied(connection); files=revisions(directory); verify_chain(rows,files)
        return {'applied':[row['name'] for row in rows], 'pending':[path.name for _,path,_ in files[len(rows):]],
                'managed':bool(rows),'schema_matches':bool(rows) and catalog_digest(connection)==rows[-1]['schema_digest']}


def adopt_baseline(connection, baseline):
    actual=catalog(connection)
    if not actual:
        connection.execute(baseline.read_text()); return 'fresh'
    schema=connection.execute('SELECT current_schema() AS name').fetchone()['name']
    temporary='kairos_adoption_' + hashlib.sha256(str(time.monotonic_ns()).encode()).hexdigest()[:12]
    connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(temporary)))
    connection.execute(sql.SQL('SET LOCAL search_path TO {},pg_catalog').format(sql.Identifier(temporary)))
    connection.execute(baseline.read_text())
    expected=catalog(connection,temporary)
    connection.execute(sql.SQL('SET LOCAL search_path TO {},pg_catalog').format(sql.Identifier(schema)))
    connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(temporary)))
    if actual!=expected:
        differing=sorted(name for name in set(actual)|set(expected) if actual.get(name)!=expected.get(name))
        raise RuntimeError('Unrecognized legacy catalog; refusing baseline adoption: '+', '.join(differing))
    return 'adopted-build006'


def apply(database_url, directory=DIRECTORY, lock_seconds=10):
    files=revisions(directory); results=[]
    with psycopg.connect(database_url,row_factory=dict_row,connect_timeout=5,autocommit=True) as connection:
        connection.execute("SET lock_timeout='2s'; SET statement_timeout='60s'")
        identity=connection.execute('SELECT current_database() AS database,current_schema() AS schema').fetchone()
        key=int.from_bytes(hashlib.sha256((identity['database']+':'+identity['schema']).encode()).digest()[:8], 'big',signed=True)
        deadline=time.monotonic()+lock_seconds
        while not connection.execute('SELECT pg_try_advisory_lock(%s) AS acquired',(key,)).fetchone()['acquired']:
            if time.monotonic()>=deadline: raise TimeoutError('Migration advisory lock deadline exceeded')
            time.sleep(min(.1,max(0,deadline-time.monotonic())))
        try:
            if connection.execute('SHOW fsync').fetchone()['fsync']!='on': raise RuntimeError('PostgreSQL fsync must be on')
            rows=applied(connection); verify_chain(rows,files)
            if rows and catalog_digest(connection)!=rows[-1]['schema_digest']:
                raise RuntimeError('Database catalog differs from migration ledger')
            for version,path,checksum in files[len(rows):]:
                started=time.monotonic()
                with connection.transaction():
                    connection.execute("SET LOCAL lock_timeout='2s'; SET LOCAL statement_timeout='60s'; SET LOCAL synchronous_commit=on")
                    origin=adopt_baseline(connection,path) if version==1 else 'migration'
                    if version!=1: connection.execute(path.read_text())
                    connection.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
                      version integer PRIMARY KEY, name text NOT NULL, sha256 text NOT NULL,
                      applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),duration_ms integer NOT NULL,
                      schema_digest text NOT NULL, origin text NOT NULL)''').format(sql.Identifier(LEDGER)))
                    elapsed=round((time.monotonic()-started)*1000)
                    connection.execute(sql.SQL('INSERT INTO {}(version,name,sha256,duration_ms,schema_digest,origin) VALUES(%s,%s,%s,%s,%s,%s)').format(sql.Identifier(LEDGER)),(version,path.name,checksum,elapsed,catalog_digest(connection),origin))
                results.append({'version':version,'name':path.name,'duration_ms':elapsed,'origin':origin})
            verify(connection,directory)
        finally:
            connection.execute('SELECT pg_advisory_unlock(%s)',(key,))
    return {'passed':True,'applied':results,'head':files[-1][0]}


def backfill(database_url, batch_size=200):
    """Explicit resumable legacy data operation; never executed by startup."""
    from kairos_api.jobs_repository import input_snapshot
    from kairos_api.model_runtime import digest
    from psycopg.types.json import Jsonb
    names=('investigation-config-digest-v1','job-input-snapshot-v1')
    totals={}
    for name in names:
        checksum=hashlib.sha256(name.encode()).hexdigest()
        while True:
            with psycopg.connect(database_url,row_factory=dict_row,connect_timeout=5) as connection:
                verify(connection)
                connection.execute("SET LOCAL lock_timeout='2s'; SET LOCAL statement_timeout='60s'; SET LOCAL synchronous_commit=on")
                connection.execute('INSERT INTO kairos_data_backfills(name,checksum) VALUES(%s,%s) ON CONFLICT DO NOTHING',(name,checksum))
                state=connection.execute('SELECT * FROM kairos_data_backfills WHERE name=%s FOR UPDATE',(name,)).fetchone()
                if state['checksum']!=checksum: raise RuntimeError('Backfill identity differs')
                if state['completed']: totals[name]=state; break
                table='kairos_investigations' if name==names[0] else 'kairos_jobs'
                missing='config_digest' if name==names[0] else 'input_snapshot'
                rows=connection.execute(sql.SQL('SELECT * FROM {} WHERE {} IS NULL AND (%s::uuid IS NULL OR id>%s::uuid) ORDER BY id LIMIT %s FOR UPDATE').format(sql.Identifier(table),sql.Identifier(missing)),(state['cursor_id'],state['cursor_id'],batch_size)).fetchall()
                updated=skipped=0
                for row in rows:
                    value=digest(row['config_snapshot']) if name==names[0] else input_snapshot(row['scenario_id'],row['policy'],row['context_blocks'])
                    if name!=names[0] and digest(value)!=row['input_digest']: skipped+=1; continue
                    connection.execute(sql.SQL('UPDATE {} SET {}=%s WHERE id=%s AND {} IS NULL').format(sql.Identifier(table),sql.Identifier(missing),sql.Identifier(missing)),(value if name==names[0] else Jsonb(value),row['id']))
                    updated+=1
                connection.execute('UPDATE kairos_data_backfills SET cursor_id=coalesce(%s,cursor_id),updated_rows=updated_rows+%s,skipped_rows=skipped_rows+%s,completed=%s,updated_at=clock_timestamp() WHERE name=%s',(rows[-1]['id'] if rows else None,updated,skipped,len(rows)<batch_size,name))
    return {name:{key:str(value) if key in ('cursor_id','updated_at') else value for key,value in state.items()} for name,state in totals.items()}
