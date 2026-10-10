"""Run precommitted full suite; preserve every output and failure."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kairos_api.evaluation import evaluate,EvaluationRepository,task_suite,VERSION
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=['null-calibration','planted-regression','reference-repair','model'],default='null-calibration')
parser.add_argument('--split',choices=['development','holdout'],default='holdout')
parser.add_argument('--output',required=True)
parser.add_argument('--publish',action='store_true')
parser.add_argument('--tenant',default='local-studio')
parser.add_argument('--save-db',action='store_true')
args=parser.parse_args()
report=evaluate(args.mode,args.split,os.getenv('KAIROS_MODEL_URL'))
path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n')
if args.save_db:
 repo=EvaluationRepository(os.environ['DATABASE_URL']);repo.initialize();repo.save(args.tenant,report,args.publish)
print(json.dumps({'id':report['id'],'mode':args.mode,'n':report['gate']['n'],'verdict':report['gate']['verdict'],'candidate_passes':report['candidate_passes'],'provider_failures':report['provider_failures']}))
