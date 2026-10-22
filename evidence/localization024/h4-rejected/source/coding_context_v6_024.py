"""Issue-relevance ranked variant of the v3 original-source selector.

v3 captured issue-named definitions in alphabetical path order and preferred any
named class over every named function, so common words ("get", "Field") in early
files exhausted the four-region budget. v6 keeps v3 capture semantics (member
groups, documented and constructor links, import authority, omissions) and only
changes which definitions come first: files ranked by a cited module path, then
IDF-weighted distinct issue symbols they define, one definition per file before
any second. Only the public issue and original source are read. v3 stays
unchanged for historical reproduction.
"""
import ast
import math
import re
import warnings

from kairos_api.investigations.context_v7 import initial_sources
from kairos_api.investigations.patches import source_path
from scripts.coding_context_v3_014 import MAX_LINES, MAX_REGIONS, _implementation_ranges

VERSION = 'issue-ranked-source024-v6-h4'


def citation(name, issue):
    """Score a path tail (``models/query.py``) or dotted module above a bare basename."""
    parts = name[:-3].split('/')
    if parts[-1] == '__init__':
        parts = parts[:-1]
    tail = '/'.join(name.split('/')[-2:])
    if (re.search(r'(?<![\w/])' + re.escape(tail) + r'\b', issue)
            or (len(parts) > 1 and re.search(r'\b' + re.escape('.'.join(parts)) + r'\b', issue))):
        return 100
    base = name.rsplit('/', 1)[-1]
    return 50 if base != '__init__.py' and re.search(r'(?<![\w.])' + re.escape(base) + r'\b', issue) else 0


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

    # Rarer definition names carry more evidence; a cited path dominates.
    defined = {}
    for name, node in classes + functions:
        defined.setdefault(node.name, set()).add(name)
    weight = {symbol: math.log((1 + len(files)) / len(owners)) for symbol, owners in defined.items()}
    cited = {name: citation(name, issue) for name in files}
    # One- and two-letter names (DateFormat.a, .I) collide with ordinary issue words.
    named = [(name, node) for name, node in classes + functions if len(node.name) >= 3 and node.name in symbols]
    named_class_names = {node.name for _, node in named if isinstance(node, ast.ClassDef)}
    file_score = dict(cited)
    for name, symbol in dict.fromkeys((name, node.name) for name, node in named):
        file_score[name] += weight[symbol]
    # A named method at least as rare as its named class is more specific; a generic one
    # ("format", "choices") must not displace a distinctive class.
    methods = [(name, node) for name, node in named if not isinstance(node, ast.ClassDef)]
    named = [(name, node) for name, node in named if not (isinstance(node, ast.ClassDef) and any(
        owner == name and method in node.body and weight[method.name] >= weight[node.name]
        for owner, method in methods))]
    displaced = named_class_names - {node.name for _, node in named if isinstance(node, ast.ClassDef)}
    # Within a file, an explicit call/attribute/code citation (``.collect``, ``collect(``) outranks incidental words.
    explicit = {node.name for _, node in named if re.search(r'(?:\.|`)' + re.escape(node.name) + r'\b|\b' + re.escape(node.name) + r'\s*\(', issue)}
    ordered = sorted(named, key=lambda item: (-file_score[item[0]], item[1].name not in explicit, -weight[item[1].name], item[0], item[1].lineno))
    first, rest = [], []
    for name, node in ordered:
        (rest if any(name == owner for owner, _ in first) else first).append((name, node))
    # Fixes usually concentrate in one file: the top file's second definition precedes other files.
    second = next((item for item in rest if first and item[0] == first[0][0]), None)
    if second:
        rest.remove(second)
        first.insert(1, second)
    primary = first + rest
    primary_names = {node.name for _, node in primary}
    class_names = named_class_names
    related = []
    for name, node in classes:
        if (name, node) in primary or node.name in named_class_names:
            continue
        doc = ast.get_docstring(node) or ''
        if any(re.search(r'\b' + re.escape(symbol) + r'\b', doc) for symbol in class_names):
            related.append((name, node, 'Original class documentation explicitly links public-issue class ' + ', '.join(sorted(class_names))))

    dependencies = []
    for owner, node in first[:MAX_REGIONS]:
        calls = {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
        imports = {}
        for statement in files[owner][0].body:
            if isinstance(statement, ast.ImportFrom) and statement.module:
                for alias in statement.names:
                    imports[alias.asname or alias.name] = statement.module.replace('.', '/')
        for called in sorted(calls - primary_names - displaced):
            options = [(name, cls) for name, cls in classes if cls.name == called]
            local = [item for item in options if item[0] == owner]
            imported = [item for item in options if called in imports and item[0] in {imports[called] + '.py', imports[called] + '/__init__.py'}]
            resolved = local or imported or (options if len(options) == 1 else [])
            for name, cls in resolved[:1]:
                dependencies.append((name, cls, 'Direct constructor dependency ' + called + ' of issue-selected ' + node.name))

    # One definition per ranked file (plus the top file's second) first, then links, then the rest.
    candidates = [(name, node, 'Public issue selects ' + node.name) for name, node in first]
    candidates.extend(related)
    candidates.extend(dependencies)
    candidates.extend((name, node, 'Public issue selects ' + node.name) for name, node in rest)
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

    # A cited file's imports follow its first definition; they carry edit authority.
    leading = set(first)
    for name, node, reason in candidates:
        for start, end in _implementation_ranges(node):
            capture(name, start, end, reason)
        if cited[name] and (name, node) in leading:
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
        selected[0]['localization'] = {'version': VERSION, 'selected_regions': len(selected), 'maximum_regions': MAX_REGIONS,
                                       'maximum_region_lines': MAX_LINES, 'ranked_files': list(dict.fromkeys(name for name, _ in first))[:10],
                                       'source': 'Public issue and original source only; no reference patches, test material or entry hints',
                                       'omissions': omissions}
    return selected
