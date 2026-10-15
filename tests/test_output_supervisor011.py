"""No Docker is needed to verify the fresh-process output guard."""
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import Mock
import pytest

from kairos_api.investigations import output_supervisor
from test_check_capture007 import workspace,VERDICT


def test_fresh_process_exec_keeps_exact_small_output_and_exit_status():
    helper=Path(output_supervisor.__file__)
    for status in (0,7):
        result=subprocess.run([sys.executable,str(helper),'1024','--',sys.executable,'-c',
            'import sys; print("exact output λ"); sys.exit('+str(status)+')'],capture_output=True,timeout=5)
        assert result.stdout=='exact output λ\n'.encode()
        assert result.returncode==status


def test_fresh_process_output_file_is_limited_without_touching_parent_limits():
    import resource
    before=resource.getrlimit(resource.RLIMIT_FSIZE)
    with tempfile.TemporaryFile() as output:
        result=subprocess.run([sys.executable,str(Path(output_supervisor.__file__)),'1024','--',
            sys.executable,'-c','import os; os.write(1,b"x"*2048); os.write(1,b"y"*2048)'],
            stdout=output,stderr=subprocess.DEVNULL,timeout=5)
        output.seek(0);raw=output.read()
        assert len(raw)==1024 and raw==b'x'*1024
        assert result.returncode!=0
    assert resource.getrlimit(resource.RLIMIT_FSIZE)==before


@pytest.mark.parametrize('arguments',[[],['1'],['1','--'],['0','--','command'],
    ['1048577','--','command'],['invalid','--','command'],['2','other','command']])
def test_invalid_launcher_args_do_not_exec(monkeypatch,arguments):
    executable=Mock();monkeypatch.setattr(output_supervisor.os,'execvp',executable)
    with pytest.raises(ValueError):output_supervisor.main(arguments)
    executable.assert_not_called()


def test_verifier_uses_trusted_argv_wrapper_and_never_preexec(workspace,monkeypatch):
    observed=[]
    def run(argv,**kwargs):
        if argv[:2]==['docker','rm']:
            observed.append('cleanup');return subprocess.CompletedProcess(argv,0)
        assert argv[:2]==[sys.executable,str(Path(output_supervisor.__file__))]
        assert argv[2:5]==['1048576','--','docker']
        assert '--network=none' in argv and '--read-only' in argv
        assert 'preexec_fn' not in kwargs and kwargs['timeout']<=120
        kwargs['stdout'].write(VERDICT);observed.append('verification')
        return subprocess.CompletedProcess(argv,0)
    monkeypatch.setattr('kairos_api.investigations.sandbox.subprocess.run',run)
    assert workspace.checks()['passed'] is True
    assert observed==['verification','cleanup']
