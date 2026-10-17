"""Use public line citations and their original-source callees before fallback.

Cited upstream revisions are hints only. Every excerpt and edit handle comes
from the frozen local source. This module never fetches links or reads targets.
"""
import ast
import re
from urllib.parse import unquote, urlsplit

from kairos_api.investigations.patches import source_path
from scripts.coding_context_v4_014 import MAX_PROMPT_TOKENS, prompt_tokens, select as fallback

VERSION = 'issue-cited-source-and-callees014-v5'


def citations(issue):
    """Parse bounded GitHub blob line hints without requesting remote content."""
    for value in re.findall(r'https://github\.com/[^\s<>`"\)]+', issue):
        url = urlsplit(value.rstrip('.,;'))
        parts = unquote(url.path).strip('/').split('/')
        lines = re.fullmatch(r'L([1-9][0-9]*)(?:-L([1-9][0-9]*))?', url.fragment)
        if url.netloc != 'github.com' or len(parts) < 5 or parts[2] != 'blob' or not lines:
            continue
        start, end = int(lines[1]), int(lines[2] or lines[1])
        name = '/'.join(parts[4:])
        if not name.endswith('.py') or not start <= end <= start + 79:
            continue
        yield name, start, end, parts[3]


def select(workspace, tokenizer):
    root = workspace.registry.directory(workspace.case) / 'source'
    issue = workspace.case['issue']
    candidates, omissions = [], []
    seen = set()
    for name, first, last, revision in list(citations(issue))[:16]:
        try:
            target = source_path(root, workspace.case['approved_prefix'], name)
            if not target.is_file() or target.stat().st_size > 250000:
                raise ValueError('Cited source unavailable or oversized')
            text = target.read_text(); lines = text.splitlines(); tree = ast.parse(text)
            if last > len(lines):
                raise ValueError('Cited lines exceed frozen source')
        except (ValueError, OSError, UnicodeError, SyntaxError):
            omissions.append({'path': name, 'start_line': first, 'end_line': last, 'reason': 'Citation cannot authorize a safe frozen-source region'})
            continue
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        enclosing = [node for node in functions if node.lineno <= first <= last <= node.end_lineno]
        node = min(enclosing, key=lambda item: item.end_lineno - item.lineno) if enclosing else None
        owner = None
        if node:
            classes = [item for item in ast.walk(tree) if isinstance(item, ast.ClassDef) and item.lineno <= node.lineno <= item.end_lineno]
            owner = min(classes, key=lambda item: item.end_lineno - item.lineno) if classes else None
        planned = [(first, last, 'Bounded public issue line citation within frozen original source')]
        if node is not None and node.end_lineno - node.lineno < 72:
            planned = [(node.lineno, node.end_lineno, 'Function enclosing public issue line citation')]
        if node:
            names = {call.func.id for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
            methods = {call.func.attr for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                       and isinstance(call.func.value, ast.Name) and call.func.value.id in {'self', 'cls'}}
            targets = [item for item in (owner.body if owner else []) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in methods]
            targets += [item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name in names]
            for item in sorted(targets, key=lambda item: item.lineno)[:4]:
                planned.append((item.lineno, item.end_lineno, 'Same-file direct callee of publicly cited function'))
        for start, end, reason in planned:
            if end - start >= 72:
                omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Complete callee exceeds bounded region; omitted without answer-assisted cropping'})
                continue
            start, end = max(1, start - 4), min(len(lines), end + 4)
            key = (name, start, end)
            if key in seen:
                continue
            seen.add(key)
            candidates.append((name, start, end, reason, revision))
    selected = []
    for name, start, end, reason, revision in candidates:
        if len(selected) == 4:
            omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Four-region context budget exhausted'})
            continue
        try:
            region = workspace.read_original(name, start, end)
        except ValueError:
            omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Original-source read bounds exceeded'})
            continue
        region['selection_reason'] = reason + '; cited revision is a hint, handle binds frozen local source'
        region['cited_upstream_revision'] = revision
        if prompt_tokens(tokenizer, issue, [*selected, region]) > MAX_PROMPT_TOKENS:
            omissions.append({'path': name, 'start_line': start, 'end_line': end, 'reason': 'Whole source region exceeds fixed prompt-token budget'})
            continue
        selected.append(region)
    if not selected:
        selected = fallback(workspace, tokenizer)
        previous = selected[0].get('localization', {})
        selected[0]['localization'] = {'version': VERSION, 'fallback': previous, 'omissions': omissions,
                                     'source': 'No usable public citation; unchanged v4 issue-only fallback'}
        return selected
    selected[0]['localization'] = {'version': VERSION, 'source': 'Public issue citations and original AST only; no target, hidden tests or entry hints',
                                  'maximum_regions': 4, 'maximum_region_lines': 80, 'maximum_prompt_tokens': MAX_PROMPT_TOKENS,
                                  'reserved_target_tokens': 512, 'prompt_tokens': prompt_tokens(tokenizer, issue, selected), 'omissions': omissions}
    return selected
