"""Independent subprocess peers reproduce transport failures without model calls."""
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

import pytest

MODULE = Path(__file__).parents[1] / 'scripts/codesage_mcp_client.py'
spec = importlib.util.spec_from_file_location('transport020', MODULE)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def peer(tmp_path, behavior='normal'):
    root = tmp_path / 'repo with spaces'
    (root / 'bin').mkdir(parents=True)
    script = root / 'bin/run-mcp'
    code = '''import json,sys,time
mode=BEHAVIOR
ready=False
for line in sys.stdin:
 req=json.loads(line); method=req.get('method')
 if method=='initialize':
  if mode=='init_timeout':time.sleep(10)
  result={'protocolVersion':'bad' if mode=='version' else '2025-03-26','capabilities':{'tools':{}}}
 elif method=='notifications/initialized':
  ready=True
  continue
 elif method=='notifications/cancelled':continue
 else:
  assert ready
  if mode=='hang':time.sleep(10)
  if mode=='exit':sys.exit(2)
  if mode=='malformed':print('not-json',flush=True);continue
  if mode=='oversize':print('x'*4300000,flush=True);continue
  if mode=='stderr':sys.stderr.write('x'*1000000);sys.stderr.flush()
  if mode=='notification':print(json.dumps({'jsonrpc':'2.0','method':'notifications/progress','params':{}}),flush=True)
  result={'tools':[{'name':'example'}]}
  if mode=='tool_error':result={'isError':True,'content':[]}
 response={'jsonrpc':'2.0','id':req['id']+1 if mode=='wrong_id' and ready else req['id'],'result':result}
 raw=json.dumps(response)+'\\n'
 if mode=='partial':
  for part in (raw[:7],raw[7:]):sys.stdout.write(part);sys.stdout.flush()
 else:sys.stdout.write(raw);sys.stdout.flush()
'''.replace('BEHAVIOR', repr(behavior))
    script.write_text('#!' + sys.executable + '\n' + code)
    script.chmod(0o700)
    return root


@pytest.mark.parametrize('mode',['normal','notification','partial','stderr'])
def test_handshake_framing_and_notifications(tmp_path,mode):
    client=transport.CodeSageMCPClient(peer(tmp_path,mode),timeout=2)
    with client:
        assert client.list_tools()==[{'name':'example'}]
        child=client.process
    assert client.process is None and child.poll() is not None


@pytest.mark.parametrize('mode,error',[('hang',TimeoutError),('init_timeout',TimeoutError),
 ('wrong_id',RuntimeError),('version',RuntimeError),('exit',RuntimeError),
 ('malformed',json.JSONDecodeError),('oversize',RuntimeError)])
def test_transport_failure_is_bounded_and_reaps_owned_process(tmp_path,mode,error):
    client=transport.CodeSageMCPClient(peer(tmp_path,mode),timeout=.25 if mode=='init_timeout' else 2)
    if mode not in {'init_timeout','version'}:
        client.start()
        client.timeout=.75
    started=time.monotonic()
    with pytest.raises(error):client.list_tools()
    assert time.monotonic()-started<3
    assert client.process is None
    client.close()


def test_tool_error_cannot_be_success(tmp_path):
    client=transport.CodeSageMCPClient(peer(tmp_path,'tool_error'),timeout=1)
    with pytest.raises(RuntimeError,match='tool execution failed'):
        client._call_rpc('tools/call',{'name':'example'})
    assert client.process is None


@pytest.mark.parametrize('timeout',[0,-1,float('inf'),float('nan'),True])
def test_invalid_deadline_rejected(timeout):
    with pytest.raises(ValueError):transport.CodeSageMCPClient(timeout=timeout)


def test_missing_launcher_fails_without_starting_child(tmp_path):
    client=transport.CodeSageMCPClient(tmp_path)
    with pytest.raises(FileNotFoundError):client.start()
    assert client.process is None


def test_explicit_environment_checkout_is_resolved_without_laptop_fallback(tmp_path,monkeypatch):
    root=peer(tmp_path)
    monkeypatch.setenv('CODESAGE_DIR',str(root))
    with transport.CodeSageMCPClient(timeout=1) as client:
        assert client.codesage_root==root
        assert client.list_tools()
