"""Offline integration of the ranked v6 selector through the existing v8 worker hook.

The worker already calls ``workspace.initial_sources012()`` for ``-v8`` jobs and
records every result as a durable ``initial_source`` step before any dispatch;
recovery replays those captured steps. Nothing selects this class by default:
legacy configurations and workspaces are unchanged, and rollback is not using it.
"""
from kairos_api.investigations.sandbox import Workspace
from scripts.coding_context_v6_024 import select
from scripts.repair012.retrieval_loop012 import NoSourceEvidence012


class RankedWorkspace024(Workspace):
    def initial_sources012(self):
        sources = select(self)
        if not sources:
            raise NoSourceEvidence012('Issue-ranked localization returned no source regions; no entry-file fallback or model dispatch')
        return sources
