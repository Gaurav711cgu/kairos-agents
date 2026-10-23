"""Repair runs with a hosted model (any OpenAI-compatible provider), journaled exactly like the Colab probe.

The loop, package format, captures and scoring are those of F025 (``f025_colab.run_chains``,
``f025_score``); only the model call and the RUN interpreter change. Model-written scripts run in the
pinned Docker image with no network (``infra/sandbox/python-in-docker.sh``), never on the host.
Credentials are read from the environment or a private env file and are never printed or stored.

    python -m scripts.hosted_repair --package PKG.json --output DIR --model nvidia/nemotron-3-ultra-550b-a55b
    python scripts/f025_score.py --results DIR --package PKG.json ...   # independent Docker scoring
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from scripts.f025_colab import MAX_CALLS_PER_CHAIN, fetch_dev_source, run_chains

PROVIDERS = {'nvidia': ('https://integrate.api.nvidia.com/v1/chat/completions', 'NVIDIA_API_KEY'),
             'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY')}
DEFAULT_ENV_FILE = Path.home() / '.kairos-provider.env'
SANDBOX_PYTHON = Path(__file__).resolve().parent.parent / 'infra/sandbox/python-in-docker.sh'
HOSTED_ENVELOPE_TOKENS = 60000  # the hosted context is far larger; 3,539 was the T4 memory limit
MAX_OUTPUT_TOKENS = 8192  # reasoning models spend part of it before the answer
RETRY_STATUSES = {429, 500, 502, 503, 504}  # the provider produced no completion, so a retry is not a second answer


def load_env(path=DEFAULT_ENV_FILE):
    """KEY=VALUE lines from a private file; values already in the environment win."""
    if Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            key, sep, value = line.strip().partition('=')
            if sep and key and not key.startswith('#'):
                os.environ.setdefault(key, value)


def api_key(provider):
    name = PROVIDERS[provider][1]
    if not os.environ.get(name):
        raise SystemExit(f'{name} is not set: put it in {DEFAULT_ENV_FILE} (chmod 600) or the environment')
    return os.environ[name]


def client(provider, model, key, urlopen=urllib.request.urlopen, sleep=time.sleep, timeout=300):
    """``generate(messages, index, sampling)`` in the shape ``run_chains`` captures."""
    url = PROVIDERS[provider][0]

    def generate(messages, index, sampling):
        body = {'model': model, 'messages': messages, 'max_tokens': MAX_OUTPUT_TOKENS, 'top_p': 0.95,
                'temperature': 0.6 if sampling.get('do_sample') else 0.0, 'seed': sampling.get('seed')}
        request = urllib.request.Request(url, json.dumps(body).encode(),
                                         {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        for attempt in range(4):
            try:
                with urlopen(request, timeout=timeout) as response:
                    reply = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code not in RETRY_STATUSES or attempt == 3:
                    raise
                sleep(20 * (attempt + 1))
        choice, usage = reply['choices'][0], reply.get('usage', {})
        text = re.sub(r'<think>.*?</think>', '', choice['message'].get('content') or '', flags=re.S).strip()
        return {'text': text, 'ended_with_eos': choice.get('finish_reason') == 'stop', 'provider_model': reply.get('model'),
                'input_tokens': usage.get('prompt_tokens'), 'output_tokens': usage.get('completion_tokens')}
    return generate


def run(package, output, generate):
    return run_chains(package, Path(output), generate, host_checks=True, envelope_tokens=HOSTED_ENVELOPE_TOKENS,
                      call_cap=len(package['chains']) * MAX_CALLS_PER_CHAIN,
                      prepare_dev=lambda chain, directory: fetch_dev_source(chain, directory, run_python=str(SANDBOX_PYTHON)))


def main():  # pragma: no cover - network and Docker
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--provider', choices=sorted(PROVIDERS), default='nvidia')
    parser.add_argument('--model', required=True)
    parser.add_argument('--env-file', type=Path, default=DEFAULT_ENV_FILE)
    args = parser.parse_args()
    load_env(args.env_file)
    generate = client(args.provider, args.model, api_key(args.provider))
    print(json.dumps(run(json.loads(args.package.read_text()), args.output, generate)))


if __name__ == '__main__':
    main()
