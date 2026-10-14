"""Rehearse migrations against a preserved build006 database/object snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from kairos_api import migrations
from kairos_api.investigations.repository import InvestigationRepository
from scripts.study007_runtime import ROOT,save,sha
from scripts.verify_operations import _restore_blob_archive,_blob_bytes


def row_fingerprints(database):
    with psycopg.connect(database) as connection:
        names=[row[0] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'kairos_%%' AND tablename NOT IN ('kairos_schema_migrations','kairos_data_backfills') ORDER BY tablename")]
        result={}
        for name in names:
            rows=connection.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text').format(sql.Identifier(name))).fetchall()
            result[name]={'rows':len(rows),'sha256':hashlib.sha256('\n'.join(row[0] for row in rows).encode()).hexdigest()}
        return result


def verify(environment,dump,objects,expected,container):
    data=json.loads(Path(environment).read_text());url=data['DATABASE_URL']
    reference=json.loads(Path(expected).read_text())
    assert sha(dump)==reference['database_backup_sha256'],'Preserved dump differs'
    assert sha(objects)==reference['object_archive_sha256'],'Preserved object archive differs'
    database='adoption007_'+uuid4().hex
    subprocess.run(['docker','exec',container,'createdb','-U','study007',database],capture_output=True,check=True)
    target=make_conninfo(url,dbname=database)
    try:
        with Path(dump).open('rb') as source:
            subprocess.run(['docker','exec','-i',container,'pg_restore','-U','study007','-d',database,'--exit-on-error','--no-owner','--no-privileges'],stdin=source,capture_output=True,check=True)
        before=row_fingerprints(target);result=migrations.apply(target)
        assert result['applied'][0]['origin']=='adopted-build006'
        after=row_fingerprints(target);assert before==after,'Historical rows changed during schema migration'
        with psycopg.connect(target) as connection:
            references={row[0] for row in connection.execute('SELECT sha256 FROM kairos_investigation_artifacts')}
            investigations=connection.execute('SELECT id,tenant_id FROM kairos_investigations ORDER BY id').fetchall()
        with tempfile.TemporaryDirectory(prefix='kairos-adoption007-objects-') as temporary:
            blobs=Path(temporary)/'blobs'
            restored=_restore_blob_archive(Path(objects),blobs,references)
            assert restored==references
            repository=InvestigationRepository(target,blobs)
            for _ in range(2):repository.initialize()
            for identifier,tenant in investigations:
                assert repository.read(str(identifier),tenant)['integrity']['verified']
            for key in references:_blob_bytes(blobs,key)
        assert before==row_fingerprints(target)
        assert sha(dump)==reference['database_backup_sha256'] and sha(objects)==reference['object_archive_sha256']
        receipt={'release':'build007','passed':True,'method':'Restore preserved consistent build006 dump and object archive into a fresh isolated database; adopt, verify twice and compare every original row hash',
                 'investigations_verified':len(investigations),'objects_verified':len(references),'historical_rows_unchanged':True,
                 'source_dump_unchanged':True,'source_archive_unchanged':True,'migration_receipt':result,
                 'table_fingerprints':before,'limits':['Same-host local rehearsal; no offsite recovery or production migration claim.','Private snapshot/session rows are never exported in this receipt.']}
        save(ROOT/'evidence/build007/adoption-restoration.json',receipt)
        print(json.dumps({key:receipt[key] for key in ('passed','investigations_verified','objects_verified','historical_rows_unchanged')}))
        return receipt
    finally:
        subprocess.run(['docker','exec',container,'dropdb','-U','study007',database],capture_output=True,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('environment','dump','objects','expected','container'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();verify(args.environment,args.dump,args.objects,args.expected,args.container)


if __name__=='__main__':main()
