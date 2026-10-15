"""Public-issue localization and exact, offset-bearing failure excerpts for v7."""
import ast
import re
import warnings

from kairos_api.investigations.context_v5 import source_handle
from kairos_api.investigations.patches import source_path


def initial_sources(workspace, *, use_entry_hints=True):
    """Prefer explicitly cited functions, then include direct same-file callees.

    Only the public issue and approved original source are inspected. Reference
    fixes, hidden tests and candidate source never participate in localization.
    """
    case = workspace.case
    entry_files = case['entry_files'] if use_entry_hints else []
    root = workspace.registry.directory(case) / 'source'
    symbols = set(re.findall(r'[A-Za-z_]\w{2,}', case['issue']))
    arguments = set(re.findall(r'\b([A-Za-z_]\w*)\s*=', case['issue']))
    functions = {}
    candidates = []
    for path in sorted((root / case['approved_prefix']).rglob('*.py')):
        name = path.relative_to(root).as_posix()
        try:
            target = source_path(root, case['approved_prefix'], name)
            if not target.is_file() or target.stat().st_size > 250000:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse(target.read_text())
        except (ValueError, UnicodeError, SyntaxError, OSError):
            continue
        nodes = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        functions[name] = nodes
        for node in nodes:
            explicit = bool(re.search(r'(?:\.|`)' + re.escape(node.name) + r'\b|\b' +
                                      re.escape(node.name) + r'\s*\(', case['issue']))
            usage = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
            usage.update(child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute))
            cited = {symbol for symbol in symbols & usage if '_' in symbol and not symbol.startswith('__')}
            argument_match = bool(arguments & {arg.arg for arg in node.args.args + node.args.kwonlyargs})
            named = node.name in symbols
            if not (explicit or named or cited or argument_match):
                continue
            if named and '_' not in node.name and not (explicit or cited or argument_match):
                continue
            # Explicit issue names outrank indirect identifier occurrences.
            rank = 0 if explicit else (1 if named else (2 if argument_match else 3))
            candidates.append((rank, name not in entry_files, name, node.lineno, node))

    selected = []
    selected_nodes = []

    def capture(name, node, reason):
        start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
        end = node.end_lineno
        if end - start + 1 > 80:
            # This is an explicit bounded window, never a pretend complete function.
            end = start + 79
            reason += '; function exceeds 80 lines, so its leading original window is retained'
        if any(item['reference']['path'] == name and
               item['reference']['start_line'] <= start <= end <= item['reference']['end_line']
               for item in selected):
            return
        try:
            result = workspace.read_original(name, start, end)
        except ValueError:
            # Oversized complete regions are excluded without cutting a source line.
            return
        result['selection_reason'] = reason
        selected.append(result)
        selected_nodes.append((name, node))

    for _, _, name, _, node in sorted(candidates, key=lambda item: item[:4]):
        capture(name, node, 'Public issue function ranking; explicit function citations precede indirect usage')
        if len(selected) == 2:
            break
    for name, node in list(selected_nodes):
        called = {call.func.id for call in ast.walk(node)
                  if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
        called.update(call.func.attr for call in ast.walk(node)
                      if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                      and isinstance(call.func.value, ast.Name) and call.func.value.id in {'self', 'cls'})
        for helper in sorted(functions.get(name, []), key=lambda item: item.lineno):
            if helper.name in called:
                capture(name, helper, 'Direct same-file callee of a public-issue source region')
                if len(selected) == 4:
                    break
        if len(selected) == 4:
            break
    if not selected:
        for name in entry_files[:2]:
            result = workspace.read_original(name, case.get('entry_lines', {}).get(name, 1))
            result['selection_reason'] = 'Registered original-source fallback; no bounded issue function found'
            selected.append(result)
    if not selected:
        if not use_entry_hints:
            return []
        raise ValueError('No actionable original source region is available')
    selected[0]['localization'] = {
        'version': 'public-issue-functions-and-callees-v1',
        'eligible_functions': len(candidates), 'selected_regions': len(selected),
        'maximum_primary_regions': 2, 'maximum_total_regions': 4,
        'omission_policy': 'Lower-ranked functions and callees outside four regions are omitted; no hidden material inspected',
    }
    return selected


def source_block(result):
    reference = result['reference']
    return {'source_id': source_handle(reference), 'path': reference['path'],
            'start_line': reference['start_line'], 'end_line': reference['end_line'],
            'numbered_original_source': result['text'],
            'origin': result.get('selection_reason', 'Captured original source read')}


def failure_feedback(result, maximum_bytes=4200):
    """Select complete captured output lines, preserving exact UTF-8 byte offsets."""
    feedback = {key: result[key] for key in ('passed', 'environment_error', 'returncode',
                'patch_digest', 'verification_complete', 'tests_run') if key in result}
    excerpts = []
    omissions = []
    remaining = maximum_bytes
    for field in ('stdout', 'stderr'):
        text = str(result.get(field, ''))
        lines = text.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line.encode()))
        ranked = []
        for index, line in enumerate(lines):
            if re.search(r'^\s*(?:E\s+|>\s*|assert\b|AssertionError\b)', line):
                rank = 0
            elif re.search(r'Traceback|File "[^\"]+", line|(?:Error|Exception):', line):
                rank = 1
            elif re.search(r'^(?:FAIL(?:ED)?|ERROR|KAIROS_VERIFIER_RESULT)|^_{3,}', line):
                rank = 2
            else:
                continue
            ranked.append((rank, index))
        covered = set()
        for _, index in sorted(ranked):
            if index in covered:
                continue
            start, end = max(0, index - 2), min(len(lines), index + 4)
            # Never cut source lines or serialized verifier records to fit a budget.
            raw = ''.join(lines[start:end])
            size = len(raw.encode())
            if size > remaining:
                continue
            excerpts.append({'field': field, 'start_line': start + 1, 'end_line': end,
                             'byte_start': offsets[start], 'byte_end': offsets[end], 'text': raw})
            covered.update(range(start, end))
            remaining -= size
            if len(excerpts) == 8:
                break
        index = 0
        while index < len(lines):
            if index in covered:
                index += 1
                continue
            start = index
            while index < len(lines) and index not in covered:
                index += 1
            omissions.append({'field': field, 'start_line': start + 1, 'end_line': index,
                              'byte_start': offsets[start], 'byte_end': offsets[index],
                              'reason': 'Output outside bounded assertion/frame excerpts; full captured output retained'})
    feedback['excerpts'] = excerpts
    feedback['scope'] = 'Exact complete captured lines; surrounding output may be omitted'
    return feedback, omissions
