"""Authored synthetic repair tasks for the F025 capability probe (design 025, Addendum 1).

P tasks state the exact change (protocol following); R tasks state only a symptom (repair skill).
Every check is visible to the model. ``reference`` is the author's fix, used only as an
infrastructure positive control; it is never rendered into a prompt.
"""
from pathlib import Path
from types import SimpleNamespace


def _task(identifier, kind, path, text, issue, check, reference):
    return {'task_id': identifier, 'kind': kind, 'files': {path: text}, 'issue': issue, 'check': check,
            'regions': [{'path': path, 'start_line': 1, 'end_line': text.count('\n')}], 'reference': reference}


def _block(path, search, replace):
    return f'{path}\n<<<<<<< SEARCH\n{search}=======\n{replace}>>>>>>> REPLACE\n'


TASKS = [
    _task('p1-constant', 'P', 'pkg/units.py',
          'KB = 1000\n\n\ndef kb_to_bytes(value):\n    return value * KB\n',
          'In pkg/units.py change the constant `KB = 1000` to `KB = 1024`.',
          'from pkg.units import kb_to_bytes\nassert kb_to_bytes(2) == 2048, kb_to_bytes(2)\n',
          _block('pkg/units.py', 'KB = 1000\n', 'KB = 1024\n')),
    _task('p2-insert-import', 'P', 'pkg/geo.py',
          '"""Shapes."""\n\n\ndef area(radius):\n    return math.pi * radius ** 2\n',
          'pkg/geo.py uses `math.pi` but never imports math. Add `import math` after the module docstring.',
          'from pkg.geo import area\nassert abs(area(1) - 3.14159) < 1e-4, area(1)\n',
          _block('pkg/geo.py', '"""Shapes."""\n', '"""Shapes."""\nimport math\n')),
    _task('p3-delete-line', 'P', 'pkg/cart.py',
          'def total(items):\n    print("debug", items)\n    return sum(items)\n',
          'Remove the debug line `print("debug", items)` from `total` in pkg/cart.py.',
          'import contextlib, io\nfrom pkg.cart import total\nout = io.StringIO()\n'
          'with contextlib.redirect_stdout(out):\n    value = total([1, 2, 3])\n'
          'assert value == 6 and out.getvalue() == "", (value, out.getvalue())\n',
          _block('pkg/cart.py', '    print("debug", items)\n', '')),
    _task('r1-slice', 'R', 'pkg/seq.py',
          'def last_n(items, n):\n    """Return the last n items."""\n    return items[-n - 1:]\n',
          '`last_n([1, 2, 3], 2)` returns `[1, 2, 3]`; it should return `[2, 3]`.',
          'from pkg.seq import last_n\nassert last_n([1, 2, 3], 2) == [2, 3], last_n([1, 2, 3], 2)\n'
          'assert last_n([1, 2, 3], 1) == [3]\n',
          _block('pkg/seq.py', '    return items[-n - 1:]\n', '    return items[-n:]\n')),
    _task('r2-default', 'R', 'pkg/tags.py',
          'def append_tag(tag, tags=[]):\n    tags.append(tag)\n    return tags\n',
          "Calling `append_tag('a')` and then `append_tag('b')` returns `['a', 'b']` the second time. "
          'A call without `tags` should start from an empty list.',
          "from pkg.tags import append_tag\nappend_tag('a')\nassert append_tag('b') == ['b'], append_tag('c')\n"
          "assert append_tag('x', ['w']) == ['w', 'x']\n",
          _block('pkg/tags.py', 'def append_tag(tag, tags=[]):\n',
                 'def append_tag(tag, tags=None):\n    if tags is None:\n        tags = []\n')),
    _task('r3-order', 'R', 'pkg/words.py',
          'def unique_words(text):\n    """Lowercased words, first occurrence kept, in original order."""\n'
          '    return sorted(set(text.lower().split()))\n',
          "`unique_words('c b a C')` returns `['a', 'b', 'c']`; the docstring promises `['c', 'b', 'a']`.",
          "from pkg.words import unique_words\nassert unique_words('c b a C') == ['c', 'b', 'a'], unique_words('c b a C')\n",
          _block('pkg/words.py', '    return sorted(set(text.lower().split()))\n',
                 '    return list(dict.fromkeys(text.lower().split()))\n')),
]


# Authored after the first F025 run, never shown to the model or used to tune the harness: the
# held-out set for the next run (TASKS above informed the parser and prompt fixes).
HELDOUT = [
    _task('p4-constant', 'P', 'pkg/temp.py',
          'FREEZING = 0\n\n\ndef is_freezing(fahrenheit):\n    return fahrenheit <= FREEZING\n',
          'In pkg/temp.py change the constant `FREEZING = 0` to `FREEZING = 32`.',
          'from pkg.temp import is_freezing\nassert is_freezing(32) and not is_freezing(33)\n',
          _block('pkg/temp.py', 'FREEZING = 0\n', 'FREEZING = 32\n')),
    _task('p5-insert-import', 'P', 'pkg/paths.py',
          '"""Path helpers."""\n\n\ndef join(a, b):\n    return os.path.join(a, b)\n',
          'pkg/paths.py uses `os.path.join` but never imports os. Add `import os` after the module docstring.',
          "import os\nfrom pkg.paths import join\nassert join('a', 'b') == 'a' + os.sep + 'b'\n",
          _block('pkg/paths.py', '"""Path helpers."""\n', '"""Path helpers."""\nimport os\n')),
    _task('p6-delete-line', 'P', 'pkg/counter.py',
          'def count(items):\n    items = items[:-1]\n    return len(items)\n',
          'Remove the line `items = items[:-1]` from `count` in pkg/counter.py.',
          'from pkg.counter import count\nassert count([1, 2, 3]) == 3, count([1, 2, 3])\n',
          _block('pkg/counter.py', '    items = items[:-1]\n', '')),
    _task('r4-parity', 'R', 'pkg/parity.py',
          'def is_even(n):\n    return n % 2 == 1\n',
          '`is_even(4)` returns `False`.',
          'from pkg.parity import is_even\nassert is_even(4) and not is_even(3)\n',
          _block('pkg/parity.py', '    return n % 2 == 1\n', '    return n % 2 == 0\n')),
    _task('r5-clamp', 'R', 'pkg/bounds.py',
          'def clamp(x, lo, hi):\n    """Limit x to the range [lo, hi]."""\n    return max(hi, min(lo, x))\n',
          '`clamp(5, 0, 10)` returns `10`; it should return `5`.',
          'from pkg.bounds import clamp\nassert clamp(5, 0, 10) == 5 and clamp(-1, 0, 10) == 0 and clamp(11, 0, 10) == 10\n',
          _block('pkg/bounds.py', '    return max(hi, min(lo, x))\n', '    return max(lo, min(hi, x))\n')),
    _task('r6-split', 'R', 'pkg/stats.py',
          'def word_count(text):\n    """Number of words separated by any whitespace."""\n    return len(text.split(\' \'))\n',
          "`word_count('a  b')` returns `3`; it should return `2`.",
          "from pkg.stats import word_count\nassert word_count('a  b') == 2 and word_count(' x\\ty ') == 2\n",
          _block('pkg/stats.py', "    return len(text.split(' '))\n", '    return len(text.split())\n')),
]


def prompt_issue(task):
    return f"{task['issue']}\n\nVisible check (must pass):\n```python\n{task['check']}```"


def workspace(task, directory):
    """A case directory holding only the task files, opened as a normal investigation Workspace."""
    from kairos_api.investigations.sandbox import Workspace
    directory = Path(directory)
    for path, text in task['files'].items():
        target = directory / 'source' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    registry = SimpleNamespace(verify=lambda _: None, directory=lambda _: directory)
    return Workspace(registry, {'issue': task['issue'], 'approved_prefix': 'pkg/', 'entry_files': []})
