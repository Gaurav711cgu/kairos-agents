"""Bounded original-source context with class links and explicit import regions.

This policy does not open reference patches, verifier files or entry-file hints.
Revision two remains available unchanged for historical reproduction.
"""
import ast
import re
import warnings

from kairos_api.investigations.context_v7 import initial_sources
from kairos_api.investigations.patches import source_path

VERSION = 'issue-linked-source-and-imports014-v3'
MAX_REGIONS = 4
MAX_LINES = 80


def _implementation_ranges(node):
    """Keep short definitions intact; group long-class members by original lines."""
    start = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
    if node.end_lineno - start + 1 <= 72:
        return [(start, node.end_lineno)]
    body = list(getattr(node, 'body', []))
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    groups = []
    for member in body:
        begin = min([member.lineno] + [d.lineno for d in getattr(member, 'decorator_list', [])])
        end = member.end_lineno
        if groups and end - groups[-1][0] + 1 <= 72:
            groups[-1] = (groups[-1][0], end)
        else:
            groups.append((begin, end))
    return groups or [(start, node.end_lineno)]


def select(workspace):
    """Capture at most four regions before any caller reads target material."""
    issue = workspace.case['issue']
    symbols = set(re.findall(r'[A-Za-z_]\w*', issue))
    root = workspace.registry.directory(workspace.case) / 'source'
    files = {}
    classes = []
    functions = []
    omissions = []
    for path in sorted((root / workspace.case['approved_prefix']).rglob('*.py')):
        name = path.relative_to(root).as_posix()
        try:
            target = source_path(root, workspace.case['approved_prefix'], name)
            if not target.is_file() or target.stat().st_size > 250000:
                continue
            text = target.read_text()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree = ast.parse(text)
        except (ValueError, OSError, UnicodeError, SyntaxError):
            continue
        files[name] = (tree, text.splitlines())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append((name, node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('__'):
                functions.append((name, node))

    cited = [(name, node) for name, node in functions if name in issue and node.name in symbols]
    named_classes = [(name, node) for name, node in classes if node.name in symbols]
    named_functions = [(name, node) for name, node in functions if node.name in symbols]
    primary = cited or named_classes or named_functions
    primary_names = {node.name for _, node in primary}
    class_names = {node.name for _, node in named_classes}
    related = []
    for name, node in classes:
        if (name, node) in primary:
            continue
        doc = ast.get_docstring(node) or ''
        if any(re.search(r'\b' + re.escape(symbol) + r'\b', doc) for symbol in class_names):
            related.append((name, node, 'Original class documentation explicitly links public-issue class ' + ', '.join(sorted(class_names))))

    dependencies = []
    for owner, node in primary:
        calls = {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
        imports = {}
        for statement in files[owner][0].body:
            if isinstance(statement, ast.ImportFrom) and statement.module:
                for alias in statement.names:
                    imports[alias.asname or alias.name] = statement.module.replace('.', '/')
        for called in sorted(calls - primary_names):
            options = [(name, cls) for name, cls in classes if cls.name == called]
            local = [item for item in options if item[0] == owner]
            imported = [item for item in options if called in imports and item[0] in {imports[called] + '.py', imports[called] + '/__init__.py'}]
            resolved = local or imported or (options if len(options) == 1 else [])
            for name, cls in resolved[:1]:
                dependencies.append((name, cls, 'Direct constructor dependency ' + called + ' of issue-selected ' + node.name))

    candidates = []
    for name, node in primary:
        candidates.append((name, node, 'Public issue selects ' + node.name))
    candidates.extend(related)
    candidates.extend(dependencies)
    selected = []

    def capture(name, start, end, reason):
        total = len(files[name][1])
        start = max(1, start - 4)
        end = min(total, end + 4)
        if end - start + 1 > MAX_LINES:
            omissions.append({'path': name, 'start_line': start + MAX_LINES, 'end_line': end, 'reason': 'Definition exceeds the bounded original-source window'})
            end = start + MAX_LINES - 1
        if any(r['reference']['path'] == name and r['reference']['start_line'] <= start <= end <= r['reference']['end_line'] for r in selected):
            return
        if len(selected) >= MAX_REGIONS:
            omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Four-region context budget exhausted'})
            return
        try:
            result = workspace.read_original(name, start, end)
        except ValueError:
            omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Complete original region exceeds source-read bounds'})
            return
        result['selection_reason'] = reason + '; original-source bounds and up to four neighboring insertion-anchor lines'
        selected.append(result)

    # A public path/function citation has priority over incidental reproduction symbols.
    # Capture its imports immediately; they are required for independent edit authority.
    for index, (name, node, reason) in enumerate(candidates):
        for start, end in _implementation_ranges(node):
            capture(name, start, end, reason)
        if cited and index < len(primary):
            imports = [item for item in files[name][0].body if isinstance(item, (ast.Import, ast.ImportFrom))]
            if imports:
                capture(name, imports[0].lineno, imports[-1].end_lineno, 'Original imports of explicitly cited source file')
    for name in dict.fromkeys(name for name, _, _ in candidates):
        imports = [item for item in files[name][0].body if isinstance(item, (ast.Import, ast.ImportFrom))]
        if imports:
            capture(name, imports[0].lineno, imports[-1].end_lineno, 'Original imports of issue-linked source file')
    if len(selected) < MAX_REGIONS:
        for item in initial_sources(workspace, use_entry_hints=False):
            ref = item['reference']
            if any(r['reference']['path'] == ref['path'] and r['reference']['start_line'] <= ref['start_line'] <= ref['end_line'] <= r['reference']['end_line'] for r in selected):
                continue
            if len(selected) >= MAX_REGIONS:
                break
            selected.append(item)
    if selected:
        selected[0]['localization'] = {'version': VERSION, 'selected_regions': len(selected), 'maximum_regions': MAX_REGIONS, 'maximum_region_lines': MAX_LINES, 'source': 'Public issue and original source only; no reference patches, test material or entry hints', 'omissions': omissions}
    return selected
