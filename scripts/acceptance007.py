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
              'tests/test_package_release007.py','tests/test_check_capture007.py','tests/test_free_model_pilot.py',
              'tests/test_feedback010.py','tests/test_codex_context010.py','tests/test_codex_transport010.py',
              'tests/test_unresolved_registry010.py','tests/test_unresolved_integration010.py',
              'tests/test_study010.py','tests/test_verify_repair010.py',
              'tests/test_retrieval011.py','tests/test_retrieval_study011.py',
              'tests/test_encoder011.py','tests/test_verify_retrieval011.py','tests/test_faiss_worker011.py','tests/test_retrieval_cli011.py',
              'tests/test_protocol_v8.py','tests/test_output_supervisor011.py',
              'tests/test_v8_postgres.py','tests/test_retrieval_loop012.py',
              'tests/test_retrieval_integration012.py','tests/test_retrieval_admission012.py','tests/test_study012.py','tests/test_verify_loop012.py', 'tests/test_pilot013.py', 'tests/test_repair_report013.py',
              'tests/test_training_bundle013.py', 'tests/test_cohort013.py', 'tests/test_verify_evaluation013.py','tests/test_audit_training013.py', 'tests/test_qualify_chain014.py', 'tests/test_verifier_unittest014.py', 'tests/test_verify_measurement014.py', 'tests/test_trained_encoder014.py','tests/test_batch_comparison014.py', 'tests/test_comparison014.py', 'tests/test_encoding014.py', 'tests/test_functions014.py', 'tests/test_independent_drafts014.py', 'tests/test_qualify014.py', 'tests/test_qualify_revision014.py', 'tests/test_retrieval_adapter014.py', 'tests/test_source_variants014.py', 'tests/test_export_qualification014.py', 'tests/test_report_comparison014.py', 'tests/test_prepare_comparison_site014.py', 'tests/test_reproduce_repair014.py', 'tests/test_audit_training014.py', 'tests/test_coding_data014.py', 'tests/test_coding_gpu014.py', 'tests/test_coding_verifier014.py', 'tests/test_coding_qualify014.py', 'tests/test_coding_actions014.py', 'tests/test_coding_context014.py', 'tests/test_coding_context_v3_014.py', 'tests/test_coding_context_v4_014.py', 'tests/test_coding_train014.py', 'tests/test_coding_admission014.py', 'tests/test_coding_context_v5_014.py', 'tests/test_coding_conversion_v6_014.py', 'tests/test_coding_public100014.py', 'tests/test_coding_resource014.py'}
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
