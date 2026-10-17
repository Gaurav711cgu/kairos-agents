"""Generate a registered, complete selected-suite verifier for training qualification."""
import json
from pathlib import PurePosixPath
from scripts.coding_data014 import selectors


def test_ids(row):
    regressions=selectors(row['FAIL_TO_PASS']);existing=selectors(row['PASS_TO_PASS'])
    if not regressions or len(regressions)+len(existing)>2000:raise ValueError('Regression missing or suite exceeds bound')
    if set(regressions)&set(existing):raise ValueError('Regression/existing declarations overlap')
    for name in [*regressions,*existing]:
        path=name.split('::',1)[0]
        if not name or '\\' in path or PurePosixPath(path).is_absolute() or any(p in {'','.', '..'} for p in path.split('/')) or not path.endswith('.py'):
            raise ValueError('Invalid registered test selector')
    return sorted(set(regressions)),sorted(set(existing))


def verifier(row):
    regressions,existing=test_ids(row);selected=sorted(set(regressions+existing))
    script='''import json,sys
import pytest
class Capture:
    def __init__(self):
        self.collected=set();self.passed=set();self.failed=set();self.finished=set();self.skipped=set();self.errors=[]
    def pytest_collection_finish(self,session):self.collected={item.nodeid for item in session.items}
    def pytest_collectreport(self,report):
        if report.failed:self.errors.append(report.nodeid)
    def pytest_runtest_logreport(self,report):
        if report.when=='call' and report.passed:self.passed.add(report.nodeid)
        if report.failed:self.failed.add(report.nodeid)
        if report.skipped:self.skipped.add(report.nodeid)
        if report.when=='teardown':self.finished.add(report.nodeid)
'''
    script+=f'regression={regressions!r}\nexisting={existing!r}\nselected={selected!r}\n'
    script+='''capture=Capture()
code=pytest.main(['-q','-p','no:cacheprovider','-o','addopts=',*selected],plugins=[capture])
def matches(selector,node):return node==selector or node.startswith(selector+'[')
def covered(selector,observed):
    nodes={node for node in capture.collected if matches(selector,node)}
    return bool(nodes) and nodes.issubset(observed)
seen=all(covered(selector,capture.collected) for selector in selected)
finished=bool(capture.collected) and capture.collected.issubset(capture.finished) and not capture.errors and seen
regression_failed=sorted(node for node in capture.failed if any(matches(s,node) for s in regression))
complete=finished and code==0 and not capture.failed and not capture.skipped and all(covered(s,capture.passed) for s in selected)
summary={'tests_run':len(capture.finished),'collected':len(capture.collected),'execution_complete':finished,'complete':complete,'regression_failed':regression_failed,'regression_passed':[s for s in regression if covered(s,capture.passed)],'existing_passed':[s for s in existing if covered(s,capture.passed)],'existing_required':len(existing),'skipped':sorted(capture.skipped),'collection_errors':capture.errors,'failed':sorted(capture.failed)}
print('KAIROS_VERIFIER_RESULT '+json.dumps(summary),flush=True)
sys.exit(0 if complete else int(code) or 126)
'''
    return script,{'version':'coding-selected-suite014-v1','selected':selected,'regressions':regressions,'existing':existing,'omissions':[],'completion':'Every declared selected test must collect, finish and pass after reference repair; skips and xfails are not passes'}


def qualifies(baseline,reference):
    from scripts.qualify006 import summary
    before,after=summary(baseline),summary(reference)
    raw=all(v.get('raw_output',{}).get('complete') is True and not v.get('output_limit_exceeded') and not v.get('environment_error') for v in [baseline,reference])
    complete=all(v.get('execution_complete') is True and v.get('tests_run',0)>0 and not v.get('skipped') for v in [before,after])
    baseline_regression=bool(before.get('regression_failed')) and baseline.get('passed') is False and baseline.get('returncode')==1
    existing=before.get('existing_required') is not None and len(before.get('existing_passed',[]))==before['existing_required']
    return bool(raw and complete and baseline_regression and existing and reference.get('passed') is True and reference.get('returncode')==0 and after.get('complete') is True)
