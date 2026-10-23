"""Static, deterministic edit preflight: reject edits that drop top-level module names.

F024 pilot: every validator-accepted edit broke import (a deleted class another module
imports; an `import` line overwritten instead of extended), so 0 tests ran. Parsing both
versions is enough to catch that before spending a sandbox run. Opt-in: the frozen
pilot's validator and scores are unchanged.
"""
import ast


def _top_level_names(text):
    return _bound(ast.parse(text).body)


def _bound(body):
    names = set()
    for node in body:
        if isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):  # module-level, not def/class bodies
            for block in (node.body, getattr(node, 'orelse', []), getattr(node, 'finalbody', []),
                          *[h.body for h in getattr(node, 'handlers', [])]):
                names |= _bound(block)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split('.')[0] for alias in node.names if alias.name != '*')
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def removed_top_level_names(original, candidate):
    """Sorted names defined or imported at module level in ``original`` but absent in ``candidate``."""
    return sorted(_top_level_names(original) - _top_level_names(candidate))


def _referenced(text):
    return {node.id for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Name)}


def _imported_by_siblings(root, path):
    """Names other modules under the same top-level package import from ``path``."""
    parts = path[:-3].split('/')
    module = '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)  # `from pkg import X` targets pkg/__init__.py
    names = set()
    for other in (root / parts[0]).rglob('*.py'):
        relative = other.relative_to(root).as_posix()
        if relative == path:
            continue
        try:
            tree = ast.parse(other.read_text())
        except (SyntaxError, UnicodeError, OSError):
            continue
        here = relative[:-3].split('/')[:-1]  # package of both a/b/c.py and a/b/__init__.py is a/b
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            base = here[:len(here) - node.level + 1] if node.level else []
            target = '.'.join(base + (node.module.split('.') if node.module else []))
            if target == module:
                names.update(alias.name for alias in node.names)
    return names


def dangling_removals(root, path, original, candidate):
    """Removed top-level names still referenced in the module or imported by a sibling module.

    A correct fix may drop a name it no longer uses (the F024 gold fix removes an unused
    ``quote`` import), so plain removal is allowed.
    """
    removed = set(removed_top_level_names(original, candidate))
    return sorted(removed & (_referenced(candidate) | _imported_by_siblings(root, path)))
