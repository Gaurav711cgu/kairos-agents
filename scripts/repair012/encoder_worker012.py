"""Run one local query encoding in an owned, credential-free child process."""
from pathlib import Path
import json
import sys

from scripts.retrieval011.encoder import CodeRankEncoder


def main():
    if len(sys.argv) != 3:
        raise ValueError('Expected explicit encoder directory and frozen profile')
    profile_path = Path(sys.argv[2])
    if profile_path.is_symlink() or profile_path.stat().st_size > 65536:
        raise ValueError('Invalid bounded encoder profile')
    raw = sys.stdin.buffer.read(4097)
    if not raw or len(raw) > 4096:
        raise ValueError('Query must contain 1–4096 UTF-8 bytes')
    text = raw.decode('utf-8')
    encoder = CodeRankEncoder(Path(sys.argv[1]), json.loads(profile_path.read_text()))
    vector = encoder.encode_queries([text])
    sys.stdout.write(json.dumps({'vectors': vector.tolist(), 'metadata': encoder.last_metadata,
                                'identity': encoder.identity}, allow_nan=False))


if __name__ == '__main__':
    main()
