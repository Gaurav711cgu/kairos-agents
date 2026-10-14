"""Explicit database migration entry point. Credentials are never printed."""
import argparse
import json
import os
from kairos_api import migrations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','apply'])
    parser.add_argument('--backfill',action='store_true',help='Run resumable missing-value backfills after applying schema')
    args=parser.parse_args()
    database=os.environ.get('KAIROS_MIGRATION_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not database: parser.error('Set KAIROS_MIGRATION_DATABASE_URL or DATABASE_URL privately')
    if args.backfill and args.action!='apply': parser.error('--backfill requires apply')
    result=migrations.status(database) if args.action=='status' else migrations.apply(database)
    if args.backfill: result['backfills']=migrations.backfill(database)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
