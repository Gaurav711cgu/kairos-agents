"""Materialize frozen public study metadata from actual completed records; never infer a success."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/build004'
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
 selection=json.loads((OUT/'profile-selection.json').read_text());label=selection['selected'];study=OUT/('study-'+label);report=json.loads((study/'comparison.json').read_text())
 if not report['complete']:raise RuntimeError('Refuse a partial frozen comparison')
 attempts=report['attempts'];write(ROOT/'dashboard/lib/study004-cohort.json',{'version':'build004-evaluation','ids':[a['id'] for a in attempts],'complete':True,'incomplete_duration_ids':[a['id'] for a in attempts if a.get('elapsed_complete') is False],'task_by_id':{a['id']:a['task_id'] for a in attempts}})
 ledger={}
 for path in sorted(OUT.glob('study-*/**/attempts.json')):
  for row in json.loads(path.read_text()):
   ledger[row['id']]={**row,'phase':path.parent.name,'model_profile':path.parts[-3],'usage_scope':'Captured response tokens only; an unknown response has unknown consumption, not proven zero usage.'}
 write(OUT/'attempt-ledger.json',list(ledger.values()))
 public={key:value for key,value in report.items() if key!='attempts'};public.update(selected_profile=label,evaluation_cases=12,qualified_cases=18,api_spend_usd=0,model_context_tokens=4096,model_output_limit=1024)
 write(ROOT/'dashboard/lib/study004-results.json',public)
 directory=ROOT/'dashboard/public/study';directory.mkdir(exist_ok=True);write(directory/'results.json',public);write(directory/'attempts.json',list(ledger.values()))
 table='| Strategy | Verified / 12 | Calls | Captured tokens | Elapsed, seconds |\n|---|---:|---:|---:|---:|\n'
 for strategy,row in report['strategies'].items():table+=f"| {strategy} | {row['verified']} | {row['calls']} | {row['tokens']} | {row['elapsed_seconds']:.1f} |\n"
 (ROOT/'docs/REPAIR_STUDY_004.md').write_text('''# Build004 repair study

Eighteen new historical cases qualified: six Django, six pytest and six Requests. Two cases per repository were used for development; four were locked for evaluation. Selection followed instance-ID order with exclusions recorded before model execution. Source regions were human-localized using maintainer patch locations; this assistance is disclosed and means the task is not unrestricted repository localization. Public cases may be present in training data.

Both local model profiles were compared on the same six development cases. Selection used verified repairs, invalid responses and elapsed time, in that order. Model/profile hashes and scores are in `profile-selection.json`. The Lenovo was not connected or measured. Two development revisions were used; the selected configuration then froze before evaluation. Each of twelve evaluation cases was run once under each of three strategies.

'''+table+'''
Single call receives one draft and one check. The tool loop receives six calls, two applied patches and two checks with immediate feedback. Independent drafts receive six fresh-context calls, selecting the first two structurally valid candidates before either check. Every captured draft and rejected or unselected result remains in the ledger. Six is the ceiling; interrupted attempts may capture fewer. The two multi-call strategies share ceilings, not guaranteed equal actual compute. All strategies have a ten-minute limit.

'''+json.dumps(report['declared_quality_target'],indent=2)+'''

The quality target is reported, not guaranteed. Missing it does not erase engineering checks or justify tuning on evaluation cases. Paired differences and repository-stratified bootstrap intervals describe resampling of this small curated sample. They do not establish broad competence, model research, statistical superiority or a SWE-bench leaderboard result. Captured tokens exclude consumption from unknown responses. Duration sums exclude interrupted attempts whose stored timestamps do not capture recovery; consult the reboot receipt for that limitation.

Verification requires a reproduced baseline failure, passing regression and selected existing tests after the model patch, and a complete nonzero test-run marker. Candidate Python shares the verifier container environment with the checks. Adversarial test-forgery resistance is not established. Reference repairs were used only for qualification and never counted as agent results.

Inspect `attempt-ledger.json`, the frozen evaluation lock, original model actions, generated patches and check captures. Original build003 results and earlier failed pilots remain separate and unchanged.
''')
 print(json.dumps({'ledger_attempts':len(ledger),'evaluation_attempts':len(attempts),'selected':label,'quality_target':report['declared_quality_target']},indent=2))
if __name__=='__main__':main()
