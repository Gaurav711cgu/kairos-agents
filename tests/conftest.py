"""Explicit isolated database preparation shared by historical repository fixtures."""
import pytest


@pytest.fixture(autouse=True)
def prepare_isolated_schema(monkeypatch,request):
    # Migration tests intentionally exercise unmanaged/pending startup failures.
    if request.module.__name__.startswith('test_migrations007'):
        return
    from kairos_api.migrations import apply
    from kairos_api.repository import RunRepository
    from kairos_api.jobs_repository import JobsRepository
    from kairos_api.evaluation import EvaluationRepository
    from kairos_api.identity import IdentityRepository
    from kairos_api.effects import EffectRepository
    from kairos_api.investigations.repository import InvestigationRepository
    for cls in (RunRepository,JobsRepository,EvaluationRepository,IdentityRepository,EffectRepository,InvestigationRepository):
        original=cls.initialize
        def prepared(self,_original=original):
            apply(self.database_url)
            return _original(self)
        monkeypatch.setattr(cls,'initialize',prepared)
