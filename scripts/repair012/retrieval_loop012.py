"""Persist retrieval evidence before the optional bounded repair loop dispatches."""
from dataclasses import dataclass
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from kairos_api.investigations.sandbox import Workspace
from scripts.repair010.feedback010 import FeedbackWorker010
from scripts.repair010.codex_transport010 import CodexInvestigator010
from scripts.retrieval011 import load_index, query, capture
from scripts.retrieval011.encoder import verify_profile

VERSION = 'retrieval-loop-cli012-v1'


@dataclass(frozen=True)
class RuntimePolicy012:
    version: str
    configuration: str
    generation: dict
    metadata: dict
    source_files: tuple
    provider_factory: object = None
    worker_factory: object = None
    workspace_base: object = None

    def __post_init__(self):
        if self.version != VERSION or self.configuration not in {'loop-v8', 'baseline-v8'}:
            raise ValueError('Unsupported frozen retrieval-loop policy')
        json.dumps(self.generation, allow_nan=False)
        json.dumps(self.metadata, allow_nan=False)


class QueryEncoder012:
    """Load weights only in a short-lived child; release memory before repair/checks."""
    dimension = 768

    def __init__(self, directory, profile_path):
        self.profile_path = Path(profile_path).resolve(strict=True)
        if self.profile_path.stat().st_size > 65536:
            raise ValueError('Encoder profile exceeds its budget')
        profile = json.loads(self.profile_path.read_text())
        self.directory = verify_profile(directory, profile)
        try:
            torch_version = importlib.metadata.version('torch')
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError('Optional CPU embedding dependencies are unavailable') from error
        self.identity = {**profile, 'runtime': {'torch': torch_version, 'device': 'cpu',
            'batch_size': 2, 'threads': 2, 'attention': 'reviewed non-fused implementation',
            'normalization': 'L2'}}
        self.last_metadata = {}

    def encode(self, texts):
        raise ValueError('The live loop only queries a separately prepared source index')

    def encode_queries(self, texts):
        if len(texts) != 1 or not isinstance(texts[0], str) or not 0 < len(texts[0].encode()) <= 4096:
            raise ValueError('Live retrieval requires one bounded query')
        environment = {'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONPATH': os.pathsep.join(p for p in sys.path if p and Path(p).is_dir()),
            'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '1', 'HF_HUB_OFFLINE': '1'}
        result = subprocess.run([sys.executable, '-m', 'scripts.repair012.encoder_worker012',
            str(self.directory), str(self.profile_path)], input=texts[0].encode(),
            capture_output=True, env=environment, timeout=45, check=False,
            cwd=Path(__file__).resolve().parents[2])
        if result.returncode or len(result.stdout) > 65536 or len(result.stderr) > 65536:
            raise ValueError('Owned query encoder failed; no retrieval/provider fallback used')
        body = json.loads(result.stdout)
        if body.get('identity') != self.identity:
            raise ValueError('Query encoder identity changed')
        vectors = np.asarray(body['vectors'], dtype=np.float32)
        if vectors.shape != (1, 768) or not np.isfinite(vectors).all():
            raise ValueError('Query encoder returned invalid vectors')
        self.last_metadata = body['metadata']
        return vectors


def workspace_class012(index_root, index_id, encoder, mode='hybrid', limit=6):
    if mode not in {'lexical', 'dense', 'hybrid'} or type(limit) is not int or not 1 <= limit <= 6:
        raise ValueError('Unsupported frozen retrieval policy')

    class RetrievalWorkspace012(Workspace):
        def __init__(self, registry, case):
            super().__init__(registry, case)
            try:
                self.index = load_index(index_root, index_id, registry.directory(case) / 'source',
                    case['approved_prefix'], case['revision'], encoder=encoder)
            except BaseException:
                self.close()
                raise

        def initial_retrieval012(self):
            found = query(self.index, self.case['issue'], mode=mode, limit=limit, encoder=encoder)
            return capture(self, found)

        def search_original(self, text):
            found = query(self.index, text, mode=mode, limit=5, encoder=encoder)
            return {'matches': [{'path': item['chunk']['path'], 'line': item['chunk']['start_line'],
                                 'text': item['chunk']['text'].splitlines()[0][:200],
                                 'chunk_id': item['chunk']['id'], 'score': item['score']}
                                for item in found.selected],
                    'truncated': len(self.index.chunks) > len(found.selected),
                    'retrieval012': found.audit}

    return RetrievalWorkspace012


class ReportedTokenBudget012(ValueError):
    pass


class NoSourceEvidence012(ValueError):
    """The selected localization method supplied no actionable source authority."""


class TokenBoundCLI012(CodexInvestigator010):
    """Stop new calls using captured usage; a completed call may cross the ceiling."""
    prompt_ceiling = 64000
    completion_ceiling = 8192

    def prepare(self, case, configuration, observations, budgets):
        ledger = getattr(self, 'captured_usage012', [])
        prompt = completion = 0
        for usage in ledger:
            if (not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0
                    for key in ('prompt_tokens', 'completion_tokens'))):
                raise ReportedTokenBudget012('Captured token usage unavailable; no further model dispatch')
            prompt += usage['prompt_tokens']
            completion += usage['completion_tokens']
        if prompt >= self.prompt_ceiling or completion >= self.completion_ceiling:
            raise ReportedTokenBudget012('Captured provider-token allowance reached; no further dispatch')
        budgets = {**budgets, 'reported_prompt_tokens_remaining': self.prompt_ceiling - prompt,
                   'reported_completion_tokens_remaining': self.completion_ceiling - completion}
        request, context = super().prepare(case, configuration, observations, budgets)
        context['token_policy012'] = {'prompt_consumed': prompt, 'completion_consumed': completion,
            'prompt_ceiling': self.prompt_ceiling, 'completion_ceiling': self.completion_ceiling,
            'scope': 'Post-response admission control; final call may overshoot; internal CLI retries remain opaque'}
        return request, context


class UsageAwareWorker012(FeedbackWorker010):
    def _state(self, job, workspace):
        state = super()._state(job, workspace)
        self.provider.captured_usage012 = [step['result']['body'].get('usage')
            for step in state[0]['steps'] if step['kind'] == 'model' and step['state'] == 'captured']
        return state

    def _run(self, job, workspace):
        try:
            return super()._run(job, workspace)
        except NoSourceEvidence012 as error:
            return self.repository.finish(job, 'no_patch', str(error))
        except ReportedTokenBudget012 as error:
            _, _, patch, verification, invalid = self._state(job, workspace)
            self._record(job, 'context', 'token_budget_stop012', {}, {'reason': str(error)})
            return self._outcome(job, workspace, patch, verification, invalid, str(error))


class RetrievalWorker012(UsageAwareWorker012):
    def _state(self, job, workspace):
        record = self.repository.read(str(job['id']), job['tenant_id'])
        if not record['integrity']['verified']:
            raise ValueError('Captured retrieval requires verified record integrity')
        selection = [step for step in record['steps'] if step['kind'] == 'context'
                     and step['name'] == 'retrieval_selection012']
        if selection:
            step = selection[-1]
            if step['request']['body'].get('index_id') != workspace.index.index_id:
                raise ValueError('Recovered retrieval index differs from the frozen selection')
            if step['state'] == 'captured':
                saved = step['result']['body']
            else:
                observations, audit = workspace.initial_retrieval012()
                saved = {'observations': observations, 'audit': audit}
                self.repository.capture(job, step['seq'], saved)
        else:
            if any(s['name'] == 'initial_source' for s in record['steps']):
                raise ValueError('An incompatible initial context policy is already captured')
            observations, audit = workspace.initial_retrieval012()
            saved = {'observations': observations, 'audit': audit}
            self._record(job, 'context', 'retrieval_selection012',
                         {'index_id': workspace.index.index_id}, saved)
        if not saved['observations']:
            raise NoSourceEvidence012('Captured retrieval returned no source regions; no entry-file fallback or model dispatch')
        for observation in saved['observations']:
            result = observation['result']
            workspace.restore_reference(result)
            identifier = result['retrieval011']['chunk_id']
            record = self.repository.read(str(job['id']), job['tenant_id'])
            existing = [s for s in record['steps'] if s['kind'] == 'tool' and s['name'] == 'initial_source'
                        and s['request']['body'].get('chunk_id') == identifier]
            if existing:
                if existing[-1]['state'] != 'captured':
                    self.repository.capture(job, existing[-1]['seq'], result)
            else:
                self._record(job, 'tool', 'initial_source',
                             {'origin': 'retrieval012', 'chunk_id': identifier}, result)
        return super()._state(job, workspace)
