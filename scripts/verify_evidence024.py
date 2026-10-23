"""Read-only: recompute every MANIFEST.json 'files' sha256 under evidence/localization024 (or a given root)."""
import hashlib
import json
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / 'evidence' / 'localization024'


def verify(root):
    """Return (checked, problems); problems are 'manifest: path: missing|mismatch|bad entry'."""
    checked, problems = 0, []
    for manifest in sorted(Path(root).rglob('MANIFEST.json')):
        label = str(manifest.relative_to(root))
        files = json.loads(manifest.read_text()).get('files')
        if not isinstance(files, dict):
            problems.append(f'{label}: no files map')
            continue
        for name, expected in sorted(files.items()):
            if isinstance(expected, dict):
                expected = expected.get('sha256')
            path = manifest.parent / name
            checked += 1
            if not isinstance(expected, str):
                problems.append(f'{label}: {name}: bad entry')
            elif not path.is_file():
                problems.append(f'{label}: {name}: missing')
            elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                problems.append(f'{label}: {name}: mismatch')
    return checked, problems


def main(argv=None):
    root = Path((argv if argv is not None else sys.argv[1:] or [DEFAULT])[0])
    checked, problems = verify(root)
    print(f'checked {checked} files, {len(problems)} problems')
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
