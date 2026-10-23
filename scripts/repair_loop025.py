"""Bounded SEARCH/REPLACE repair loop: edit, validate, check, feed the result back as its own message.

Design 025 (docs/REPAIR_REDESIGN_025.md). Each rejection or failed check becomes a new user turn after
the model's own reply (Aider reflection, mini-swe-agent observation), with at most three corrections.
The original snapshot is only read; a failed candidate is rolled back with ``workspace.reset``.
"""
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import PurePosixPath

from kairos_api.investigations.patches import source_path
from scripts.search_replace025 import apply_blocks, parse_blocks

SYSTEM = """You repair Python source. Before editing you may gather evidence, one action per reply and nothing else:
FIND text  (lines containing text in the source and the repository tests)
READ path start-end  (at most 80 lines of a source or test file; tests are read-only)
RUN followed by a ```python block  (runs your script in the repository and shows its output)
Before your first edit, RUN a short script that reproduces the issue, alone in its reply: it must fail
while the bug is present (assert the expected behaviour) and exit 0 once it is fixed. For Django, settings
are already configured (sqlite in memory) and every model your script defines gets its table. After an
edit, your script runs again on the edited code.
Then think briefly and emit one or more edit blocks in exactly this form:

django/forms/widgets.py
<<<<<<< SEARCH
exact existing lines, copied verbatim with their indentation
=======
replacement lines
>>>>>>> REPLACE

The first line is the file's path exactly as shown in Source (django/forms/widgets.py is only an example).
Copy SEARCH lines with their full indentation. Write code directly; no ``` fences inside blocks.
SEARCH must match the file exactly once. To insert, SEARCH a nearby line and repeat it in REPLACE with
the new lines. Keep imports and names other code still uses. Never write line numbers in blocks."""

# Forms the 14B produced in F025 run 3: `READ path:a-b`, `FIND: "x"`, `FIND text: `x``, `RUN ```python` on one line.
_READ = re.compile(r'^\s*READ:?\s+(\S+?)(?::|\s+)(\d+)-(\d+)\s*$', re.M)
_FIND = re.compile(r'^\s*FIND:?[ \t]+(\S.*?)[ \t]*$', re.M)
_RUN = re.compile(r'^\s*RUN:?[ \t]*\n*```(?:python|py)?[ \t]*\n(.*?)^```', re.M | re.S)
_RUN_INSIDE = re.compile(r'^```(?:python|py)?[ \t]*\nRUN:?[ \t]*\n(.*?)^```', re.M | re.S)  # F025 run 5


def _find_arg(raw):
    """The literal inside the first quoted or backticked span, after an optional `text:` prefix."""
    raw = re.sub(r'^text\b\s*:?\s*', '', raw.strip(), flags=re.I)
    quoted = re.search(r'`([^`]+)`|"([^"]+)"|\'([^\']+)\'', raw)
    return next(g for g in quoted.groups() if g) if quoted else raw


RUN_TIMEOUT = 30
_FRAME = re.compile(r'^  File "(.*?)", line \d+', re.M)
NOTES = {'fails': 'It fails on the original code, so it reproduces the issue. After your edit it runs again and must exit 0.',
         'passes': 'It exits 0 on the original code, so it does not show the bug. Make it fail while the bug is present '
                   '(assert the expected behaviour) and RUN it again, or edit now.',
         'script_error': "The error is in your script's own code, not in the repository. Fix the script and RUN it again, or edit now."}


def _verdict(code_, output):
    """'fails' (a reproduction), 'passes', 'script_error' (raised in the script's own lines) or None (no exit)."""
    if code_ is None:
        return None
    if code_ == 0:
        return 'passes'
    frames, last = _FRAME.findall(output), (output.strip().splitlines() or [''])[-1]
    own = frames and frames[-1] == '<string>' and not last.startswith('AssertionError')
    return 'script_error' if own else 'fails'


def render(issue, workspace, regions):
    parts = [f'Issue:\n{issue}\n\nSource:']
    for region in regions:
        path, start, end = region['path'], region['start_line'], region['end_line']
        parts.append(f'{path} lines {start}-{end}\n```python\n{_plain(workspace, path, start, end)}```')
    return '\n\n'.join(parts)


def _plain(workspace, path, start, end):
    text = workspace.read_original(path, start, end)['text']
    return re.sub(r'^\d+: ', '', text, flags=re.M)  # numbered lines get copied into edits (F024)


def _visible(workspace, path):
    """An original-snapshot file the model may see: approved source, or a .py file under a visible test root.

    Fairness: test roots hold the base-commit tests already in the repository; the hidden evaluation
    test patch is never present. Read-only here; edits still pass only the source_path gate.
    """
    root = workspace.registry.directory(workspace.case) / 'source'
    pure = PurePosixPath(path)
    if not any(path.startswith(r) for r in workspace.case.get('test_roots', ())):
        target = source_path(root, workspace.case['approved_prefix'], path)
    elif pure.is_absolute() or '..' in pure.parts or '\\' in path or not path.endswith('.py'):
        raise ValueError('Path is outside visible test files')
    else:
        target = root.joinpath(*pure.parts)
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file() or target.stat().st_size > 250000:
        raise ValueError('File missing, escapes the snapshot or exceeds 250KB')
    return target


def _find(workspace, literal, limit=20):
    root, hits = workspace.registry.directory(workspace.case) / 'source', []
    for top in [workspace.case['approved_prefix'], *workspace.case.get('test_roots', ())]:
        for path in sorted((root / top).rglob('*.py')):
            try:
                lines = _visible(workspace, path.relative_to(root).as_posix()).read_text().splitlines()
            except (ValueError, OSError, UnicodeError):
                continue
            hits += [f'{path.relative_to(root).as_posix()}:{n}: {line[:200]}' for n, line in enumerate(lines, 1) if literal in line]
            if len(hits) >= limit:
                return '\n'.join(hits[:limit]) + '\n(truncated)'
    return '\n'.join(hits) or f'FIND: no lines contain {literal!r}'


def _execute(code, root, timeout, python=None):
    """(exit code, or None on timeout; output tail) of ``code`` in a child ``python -I`` at ``root``."""
    with tempfile.TemporaryFile() as output:  # a file, so a chatty candidate cannot fill parent memory
        child = subprocess.Popen([python or sys.executable, '-I', '-c', code], cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True, env={'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'})
        try:
            code_ = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)  # grandchildren too
            child.wait()
            return None, f'timed out after {timeout}s'
        output.seek(max(0, output.seek(0, 2) - 1500))
        return code_, output.read().decode(errors='replace')


def subprocess_check(code, timeout=20):
    """Run visible check code against the candidate tree in a child interpreter.

    shortcut: no container, so only for synthetic tasks and disposable VMs (Colab); use the pinned
    Docker sandbox (``workspace.checks``) for model output on this host.
    """
    def check(workspace):
        code_, output = _execute("import sys; sys.path.insert(0, '.')\n" + code, workspace.root, timeout)
        return code_ == 0, output if code_ is not None else 'check ' + output
    return check


def _run_script(workspace, script, allow_run, exhausted):
    """(feedback, receipt kind, verdict) for a model RUN script in the case's pinned interpreter, after its prelude."""
    if not allow_run:
        return 'RUN refused: no disposable VM. Edit with the evidence you have.', 'run_refused', None
    if exhausted:
        return 'RUN refused: run budget exhausted. Edit with the evidence you have.', 'run_refused', None
    python = workspace.case.get('run_python')
    if python and not os.path.exists(python):
        return f'RUN unavailable: interpreter {python} is missing. Edit with the evidence you have.', 'run_refused', None
    paths = ['.', *workspace.case.get('python_paths', ())]
    prelude = 'import sys\n' + ''.join(f'sys.path.insert(0, {p!r})\n' for p in paths) + workspace.case.get('run_prelude', '')
    code_, output = _execute(prelude + script, workspace.root, RUN_TIMEOUT, python)  # the current candidate tree
    for root in sorted({str(workspace.root.resolve()), str(workspace.root)}, key=len, reverse=True):
        output = output.replace(root + '/./', '').replace(root + '/', '')  # traceback paths cost envelope tokens
    return (f'RUN exit {code_}:\n{output}' if code_ is not None else f'RUN {output}:\n'), 'run', _verdict(code_, output)


def run_loop(model, workspace, issue, regions, check, receipts, max_corrections=3, max_reads=4, max_runs=3, allow_run=False,
             stop=(), self_test=False):
    """``allow_run`` executes model-written RUN scripts without a container: only in a disposable VM.

    ``self_test`` is for static-only checks (dev cases, F025 run 5): a passing edit is not final while a
    reproduction script is on record and a run is left. The script reruns on the candidate and the model
    replies DONE or revises; the reviewed candidate stays the answer unless a revision passes too, also
    when the corrections run out or a ``stop`` exception (call or token cap) comes from ``model``.
    """
    regions = [dict(r) for r in regions]
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': render(issue, workspace, regions)}]
    previous, last_reply, calls, failures, reads, runs = None, None, 0, 0, 0, 0
    script, pending = None, None  # last RUN that failed on the original tree; (reply, patch) under self_test

    def execute(source):
        nonlocal runs, script
        feedback, kind, verdict = _run_script(workspace, source, allow_run, runs >= max_runs)
        runs += kind == 'run'
        if pending is None and verdict in NOTES:  # the tree is the original only while nothing is under review
            feedback += '\n' + NOTES[verdict]
            script = source if verdict == 'fails' else script
        return feedback, kind

    def record(kind, reply, feedback=None, patch=None):
        nonlocal previous
        entry = {'step': calls, 'kind': kind, 'previous': previous,
                 'reply_sha256': hashlib.sha256(reply.encode()).hexdigest(), 'feedback': feedback,
                 'patch_sha256': patch and hashlib.sha256(patch.encode()).hexdigest()}
        entry['sha256'] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        previous = entry['sha256']
        with open(receipts, 'a') as handle:
            handle.write(json.dumps(entry, sort_keys=True) + '\n')

    def accept(reply, patch):
        record('accepted', reply, None, patch)
        return {'status': 'accepted', 'patch': patch, 'calls': calls, 'messages': messages, 'regions': regions}

    while True:
        try:
            reply = model(messages)
        except stop:
            if pending is None:
                raise
            return accept(*pending)
        calls += 1
        if reply == last_reply:
            if pending:
                return accept(*pending)
            record('repeated', reply)
            return {'status': 'repeated', 'patch': None, 'calls': calls, 'messages': messages, 'regions': regions}
        last_reply = reply
        blocks = parse_blocks(reply)
        run = _RUN.search(reply) or _RUN_INSIDE.search(reply)
        read, find = (None, None) if blocks or run else (_READ.search(reply), _FIND.search(reply))
        run_note = ''
        if run and blocks:  # RC5: the script runs first (original tree); its output rides with the edit verdict
            feedback, kind = execute(run[1])
            record(kind, reply, feedback)
            run_note = feedback + '\n\n'
            run = None
        if run:
            feedback, kind = execute(run[1])
        elif (read or find) and reads >= max_reads:
            feedback, kind = 'READ refused: read budget exhausted. Edit with the source you have.', 'read_refused'
        elif find:
            feedback, kind, reads = _find(workspace, _find_arg(find[1])), 'find', reads + 1
        elif read:
            path, start, end = read[1], int(read[2]), int(read[3])
            try:
                if any(path.startswith(r) for r in workspace.case.get('test_roots', ())):
                    lines = _visible(workspace, path).read_text().splitlines(True)
                    if not 1 <= start <= len(lines):
                        raise ValueError('Line is outside the file')
                    end = min(end, len(lines), start + 79)
                    feedback = f'{path} lines {start}-{end}\n```python\n{"".join(lines[start - 1:end])[:8000]}```'
                else:
                    end = min(end, workspace.read_original(path, start)['total_lines'], start + 79)  # clamp, never refuse, an overlong range
                    feedback = f'{path} lines {start}-{end}\n```python\n{_plain(workspace, path, start, end)}```'
                    regions.append({'path': path, 'start_line': start, 'end_line': end})  # tests never become edit regions
                reads, kind = reads + 1, 'read'
            except (ValueError, OSError, UnicodeError) as error:
                feedback, kind = f'READ refused: {error}', 'read_refused'
        if run or read or find:
            record(kind, reply, feedback)
            messages += [{'role': 'assistant', 'content': reply}, {'role': 'user', 'content': feedback}]
            continue
        if pending and not blocks:  # DONE, or anything that is not a revision, keeps the reviewed candidate
            return accept(*pending)
        if pending:
            workspace.reset()  # a revision is applied to the original, never on top of the reviewed candidate
        patch = None
        if not blocks:
            kind, feedback = 'rejected', run_note + 'No SEARCH/REPLACE blocks found. Reply with edit blocks in the required format.'
        else:
            verdict = apply_blocks(workspace, blocks, regions)
            if not verdict['accepted']:
                kind, feedback = 'rejected', f'{run_note}Edit rejected: {verdict["reason"]}'
            else:
                patch = verdict['patch']
                ok, output = check(workspace)
                if ok and self_test and script is not None and allow_run and runs < max_runs:
                    output, _, verdict = _run_script(workspace, script, allow_run, False)
                    runs += 1
                    if verdict == 'passes':  # its own reproduction now passes: final, so no review can undo it
                        record('self_test', reply, output, patch)
                        return accept(reply, patch)
                    pending = (reply, patch)
                    feedback = (f'{run_note}Edit applied, but your reproduction still fails on the edited code:\n{output}\n'
                                'Send corrected edit blocks against the original file, or reply DONE to keep this edit.')
                    record('self_test', reply, feedback, patch)
                    messages += [{'role': 'assistant', 'content': reply}, {'role': 'user', 'content': feedback}]
                    continue
                if ok:
                    return accept(reply, patch)
                workspace.reset()
                kind, feedback = 'check_failed', f'{run_note}Edit applied, but the visible check failed:\n{output}'
        record(kind, reply, feedback, patch)
        failures += 1
        if failures > max_corrections:
            if pending:
                return accept(*pending)
            return {'status': 'exhausted', 'patch': None, 'calls': calls, 'messages': messages, 'regions': regions}
        messages += [{'role': 'assistant', 'content': reply},
                     {'role': 'user', 'content': feedback + '\nRevise: send corrected edit blocks against the original file.'}]
