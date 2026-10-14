"""Issue-only source localization and compact, auditable context for protocol v5."""
import ast
import re
import warnings

from kairos_api.investigations.patches import source_path


def initial_sources(workspace):
    """Select source using public issue symbols and registered entry points only.

    No reference patch, verification file or test material is consulted. Functions
    matching issue identifiers rank first; deterministic path/line ordering breaks
    ties. Large functions use a bounded registered source window instead.
    """
    case = workspace.case
    root = workspace.registry.directory(case) / 'source'
    issue = case['issue']
    symbols = set(re.findall(r'[A-Za-z_]\w{2,}', issue))
    issue_arguments = set(re.findall(r'\b([A-Za-z_]\w*)\s*=', issue))
    candidates = []
    parsed = {}
    for path in sorted((root / case['approved_prefix']).rglob('*.py')):
        name = str(path.relative_to(root))
        try:
            target = source_path(root, case['approved_prefix'], name)
            if not target.is_file() or target.stat().st_size > 250000:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse(target.read_text())
        except (ValueError, UnicodeError, SyntaxError, OSError):
            continue
        parsed[name] = tree
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            usage = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
            usage.update(child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute))
            cited = {name for name in symbols & usage if '_' in name and not name.startswith('__')}
            arguments = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
            argument_match = bool(arguments & issue_arguments)
            named = node.name in symbols
            if not named and not cited and not argument_match: continue
            explicit = bool(re.search(r'(?:\.|`)' + re.escape(node.name) + r'\b|\b' + re.escape(node.name) + r'\s*\(', issue))
            if named and '_' not in node.name and not explicit and not cited and not argument_match:
                continue
            start = min([node.lineno] + [n.lineno for n in node.decorator_list])
            end = node.end_lineno
            if end - start + 1 > 80:
                # Use a bounded original-source region around the cited symbol.
                # The issue supplies the symbol; no reference repair is read.
                occurrences = [child.lineno for child in ast.walk(node)
                               if (isinstance(child, ast.Name) and child.id in cited) or
                                  (isinstance(child, ast.Attribute) and child.attr in cited)]
                if not occurrences: continue
                start = max(node.lineno, min(occurrences) - 15)
                end = min(node.end_lineno, start + 59)
            # Exact issue identifiers are evidence, not a repository-specific hint.
            score = 10 + 4 * explicit + 12 * bool(cited) + 16 * argument_match + 100 * int(name in case['entry_files'])
            candidates.append((-score, name, start, end))
    selected = []
    for _, name, start, end in sorted(candidates):
        if any(item['reference']['path'] == name and
               item['reference']['start_line'] <= start <= item['reference']['end_line']
               for item in selected):
            continue
        result = workspace.read_original(name, start, end)
        result['selection_reason'] = 'Original source region matching a public issue identifier; registered entry files prioritized'
        selected.append(result)
        if len(selected) == 2:
            return selected
    for name in case['entry_files']:
        if any(item['reference']['path'] == name for item in selected):
            continue
        line = case.get('entry_lines', {}).get(name, 1)
        containing = [node for node in ast.walk(parsed.get(name, ast.Module(body=[], type_ignores=[])))
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                      node.lineno <= line <= node.end_lineno and
                      node.end_lineno - node.lineno + 1 <= 80]
        if containing:
            node = min(containing, key=lambda item: item.end_lineno - item.lineno)
            result = workspace.read_original(name, node.lineno, node.end_lineno)
            result['selection_reason'] = 'Complete function containing the registered entry line'
        else:
            result = workspace.read_original(name, line)
            result['selection_reason'] = 'Registered entry window; no bounded issue-symbol function found'
        selected.append(result)
        if len(selected) == 2:
            break
    if not selected:
        raise ValueError('No actionable original source region is available')
    return selected


def compact_issue(issue, limit=2000):
    """Keep complete leading lines, recording exactly which original bytes are omitted."""
    if len(issue) <= limit:
        return issue, []
    lines = issue.splitlines(keepends=True)
    chosen = []
    length = 0
    for line in lines:
        if length + len(line) > limit:
            break
        chosen.append(line)
        length += len(line)
    if not chosen:
        # A pathological single line cannot be cut into pretend complete evidence.
        return '', [{'field': 'issue', 'start_character': 0, 'end_character': len(issue),
                     'reason': 'Leading issue line exceeds the compact issue limit; full issue remains in the task snapshot'}]
    return ''.join(chosen), [{'field': 'issue', 'start_character': length,
                             'end_character': len(issue),
                             'reason': 'Complete trailing issue lines omitted; full issue remains in the task snapshot'}]


def source_handle(reference):
    return 'S' + reference['excerpt_id'][:12]


def source_block(result):
    reference = result['reference']
    return {'source_id': source_handle(reference), 'path': reference['path'],
            'start_line': reference['start_line'], 'end_line': reference['end_line'],
            'original_source': ''.join(re.sub(r'^\d+: ', '', line, count=1)
                                       for line in result['text'].splitlines(keepends=True)),
            'origin': result.get('selection_reason', 'Captured original source read')}
