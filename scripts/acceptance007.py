"""One release acceptance inventory shared by local reviewer commands and CI."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BACKEND_PATTERNS=('test_*.py',)
FRONTEND_COMMANDS=('test:boundary','test:client','test:recorded','lint','typecheck','build')
BROWSER_CONFIGURATIONS=('playwright.config.ts','playwright.recorded.config.ts','playwright.reviewer.config.ts')


def backend_files(root=ROOT):
    files=sorted(str(path.relative_to(root)) for path in (root/'tests').glob('test_*.py'))
    required={'tests/test_context_v5.py','tests/test_edits_v5.py','tests/test_v5_postgres.py',
              'tests/test_reviewer_evidence.py','tests/test_package_release006.py','tests/test_protocol_v7.py',
              'tests/test_migrations007.py','tests/test_study007.py','tests/test_v7_postgres.py',
              'tests/test_package_release007.py','tests/test_check_capture007.py','tests/test_free_model_pilot.py'}
    if not required.issubset(files): raise RuntimeError('Required release tests are missing')
    return files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['inventory','backend','recorded-browser','live-browser'])
    args=parser.parse_args()
    if args.action=='inventory':
        print(json.dumps({'backend':backend_files(),'frontend':FRONTEND_COMMANDS,'browser':BROWSER_CONFIGURATIONS},indent=2));return
    if args.action=='backend': command=[sys.executable,'-m','pytest',*backend_files(),'-q','--tb=short']
    else:
        config='playwright.recorded.config.ts' if args.action=='recorded-browser' else 'playwright.reviewer.config.ts'
        command=[str(ROOT/'dashboard/node_modules/.bin/playwright'),'test','--config',config]
    raise SystemExit(subprocess.call(command,cwd=ROOT if args.action=='backend' else ROOT/'dashboard'))


if __name__=='__main__': main()
