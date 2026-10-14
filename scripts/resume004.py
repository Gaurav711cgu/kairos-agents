"""Resume frozen build004 identities, then stop owned inference and unused Docker.
Existing active attempts require explicit recovery inspection before this command.
"""
import json
import os
from pathlib import Path
import subprocess
import time
from scripts import advance004
from scripts.study004 import environment, frozen
from kairos_api.investigations.repository import InvestigationRepository

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/build004'


def main():
    selected = json.loads((OUT / 'profile-selection.json').read_text())['selected']
    profile = advance004.profiles[selected]
    assert frozen(profile) == json.loads((OUT / ('study-' + selected) / 'evaluation-lock.json').read_text())
    ready = subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not ready:
        subprocess.run(['open', '-a', 'Docker'], check=True)
    try:
        for _ in range(90):
            if subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(1)
        else:
            raise TimeoutError('Docker startup deadline')
        environment()
        repo = InvestigationRepository()
        with repo.connect() as connection:
            assert not connection.execute("SELECT 1 FROM kairos_investigations WHERE status IN ('queued','running')").fetchone(), 'Inspect active attempts before resuming'
        repo.close()
        print('Docker ready; selected profile only; no replacement attempts.', flush=True)
        advance004.start(selected)
        advance004.run(selected, 'evaluation')
        advance004.run(selected, 'report')
        env = os.environ.copy()
        env.update(KAIROS_INVESTIGATION_MODEL_MANIFEST=str(profile), KAIROS_TEST_INVESTIGATION_PROVIDER='1', KAIROS_TEST_INVESTIGATION_DOCKER='1')
        with (OUT / 'crash-recovery-output.txt').open('a') as log:
            subprocess.run([str(advance004.PYTHON), '-m', 'scripts.verify_investigation_crashes', '--release', '004', '--configuration', 'baseline-v4'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        with (OUT / 'real-provider-docker.txt').open('a') as log:
            subprocess.run([str(advance004.PYTHON), '-m', 'pytest', 'tests/test_investigations.py::test_real_model_enforces_nested_schema', 'tests/test_investigations.py::test_real_docker_verifier_is_nonroot_readonly_and_network_disabled', '-q', '--tb=short'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        advance004.write(OUT / 'study-execution.json', {'complete': True, 'selected': selected, 'development_revision': 2, 'evaluation_tuned': False, 'api_spend_usd': 0, 'resumed_after_interruption': True})
        print('Study and live recovery/provider/container checks complete.', flush=True)
    finally:
        advance004.stop()
        names = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True).stdout.splitlines()
        if set(names) <= {'kairos-keycloak-build002', 'kairos-postgres-build001'}:
            subprocess.run(['docker', 'desktop', 'stop'], check=False)
            print('Inference and unused Docker stopped.', flush=True)
        else:
            print('Other containers present; Docker preserved.', flush=True)


if __name__ == '__main__':
    main()
