"""Load ignored local settings and run one development service."""
import argparse
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("service", choices=["api", "seed", "web", "test", "worker", "model", "investigator"])
args = parser.parse_args()
env = os.environ.copy()
for line in (root / ".env.kairos.local").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value
if args.service != "test" and (root / ".runtime/identity.env").exists():
    for line in (root / ".runtime/identity.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key] = value
python = str(root / ".venv/bin/python")
commands = {
    "api": [python, "-m", "uvicorn", "kairos_api.app:app", "--host", "127.0.0.1", "--port", "8100", "--no-access-log"],
    "seed": [python, "-m", "kairos_api.seed"],
    "test": [python, "-m", "pytest", *[str(p.relative_to(root)) for pattern in ("test_api_*.py", "test_identity*.py", "test_jobs*.py", "test_evaluation*.py", "test_effects*.py", "test_operations*.py", "test_investigations*.py") for p in sorted((root / "tests").glob(pattern))], "-q", "--tb=short"],
    "worker": [python, "-m", "kairos_api.worker"],
    "investigator": [python, "-m", "kairos_api.investigations.worker"],
    "model": ["python3", str(root / "scripts/serve_local_model.py"), "--model", str(root.parent / "resume/.local-models/qwen2.5-0.5b-instruct"), "--port", "8120"],
    "web": ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3100"],
}
os.chdir(root / "dashboard" if args.service == "web" else root)
os.execvpe(commands[args.service][0], commands[args.service], env)
