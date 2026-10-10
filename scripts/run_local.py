"""Load ignored local settings and run one development service."""
import argparse
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("service", choices=["api", "seed", "web", "test"])
args = parser.parse_args()
env = os.environ.copy()
for line in (root / ".env.kairos.local").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        env[key] = value
python = str(root / ".venv/bin/python")
commands = {
    "api": [python, "-m", "uvicorn", "kairos_api.app:app", "--host", "127.0.0.1", "--port", "8100"],
    "seed": [python, "-m", "kairos_api.seed"],
    "test": [python, "-m", "pytest", "tests/test_api_runner.py", "tests/test_api_postgres.py", "-q"],
    "web": ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3100"],
}
os.chdir(root / "dashboard" if args.service == "web" else root)
os.execvpe(commands[args.service][0], commands[args.service], env)
