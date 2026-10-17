"""Capture unittest outcomes directly, including wrapped descriptions and subtests."""
import json
from pathlib import Path
from scripts import qualify006

VERSION = 'structured-unittest014-v1'


def render_script014(expected, modules, runner_path='/workspace/tests/runtests.py'):
    prefix = 'EXPECTED = ' + repr(expected) + '\nARGV = ' + repr([runner_path, *modules, '--parallel=1', '--verbosity=2']) + '\n'
    return prefix + '''import json, runpy, sys, unittest
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/tests')
RESULTS = []
class CapturedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entries = []
        self.active = {}
        RESULTS.append(self)
    def startTest(self, test):
        super().startTest(test)
        cls = type(test)
        aliases = [test.id(), str(test), test._testMethodName + ' (' + cls.__module__ + '.' + cls.__qualname__ + ')']
        description = test.shortDescription()
        if description: aliases.append(description)
        entry = {'aliases': aliases, 'status': None, 'finished': False}
        self.entries.append(entry)
        self.active[id(test)] = entry
    def stopTest(self, test):
        self.active[id(test)]['finished'] = True
        super().stopTest(test)
    def mark(self, test, status):
        self.active[id(test)]['status'] = status
    def addSuccess(self, test):
        self.mark(test, 'ok'); super().addSuccess(test)
    def addFailure(self, test, err):
        self.mark(test, 'FAIL'); super().addFailure(test, err)
    def addError(self, test, err):
        self.mark(test, 'ERROR'); super().addError(test, err)
    def addSkip(self, test, reason):
        self.mark(test, 'skipped'); super().addSkip(test, reason)
    def addExpectedFailure(self, test, err):
        self.mark(test, 'expected_failure'); super().addExpectedFailure(test, err)
    def addUnexpectedSuccess(self, test):
        self.mark(test, 'unexpected_success'); super().addUnexpectedSuccess(test)
    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.mark(test, 'FAIL' if issubclass(err[0], test.failureException) else 'ERROR')
        super().addSubTest(test, subtest, err)
unittest.TextTestRunner.resultclass = CapturedResult
sys.argv = ARGV
code = 0
normal = False
try:
    runpy.run_path(ARGV[0], run_name='__main__')
    normal = True
except SystemExit as error:
    code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
    normal = True
finally:
    entries = [entry for result in RESULTS for entry in result.entries]
    tests_run = sum(result.testsRun for result in RESULTS)
    matched = {name: [entry for entry in entries if name in entry['aliases']] for name in EXPECTED}
    execution_complete = bool(normal and entries and len(entries) == tests_run and all(entry['finished'] and entry['status'] for entry in entries) and all(matched.values()))
    failed = [name for name, matches in matched.items() if any(e['status'] in ('FAIL', 'ERROR', 'unexpected_success') for e in matches)]
    passed = [name for name, matches in matched.items() if matches and all(e['status'] == 'ok' for e in matches)]
    complete = execution_complete and code == 0 and len(passed) == len(EXPECTED)
    print('KAIROS_VERIFIER_RESULT ' + json.dumps({'tests_run': tests_run, 'execution_complete': execution_complete, 'complete': complete, 'regression_failed': failed, 'regression_passed': passed, 'protocol': 'structured-unittest014-v1'}))
sys.exit((0 if complete else code or 1) if execution_complete else 126)
'''


def verifier(row, source):
    if row['repo'] != 'django/django':
        raise ValueError('Structured unittest revision applies only to Django')
    modules = [n[6:-3].replace('/', '.') for n in qualify006.test_paths(row) if n.startswith('tests/') and not n.endswith('__init__.py')]
    expected = json.loads(row['FAIL_TO_PASS'])
    if not modules or not expected:
        raise ValueError('Registered Django modules and declared regressions required')
    return render_script014(expected, modules), {'test_modules': modules, 'declared_regressions': expected,
        'omissions': [], 'completion': 'All declared regression identities, completed unittest lifecycle and runner exit required', 'protocol': VERSION}
