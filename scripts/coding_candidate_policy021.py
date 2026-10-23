"""Development-only case policy; historical qualification policy stays frozen."""
from scripts.coding_qualify014 import SOURCE_PREFIXES as HISTORICAL_PREFIXES, SUPPORTED_ENVIRONMENTS

SOURCE_PREFIXES = {**HISTORICAL_PREFIXES, 'pydantic/pydantic': 'pydantic/'}
# Names require matching independent reviews, never automatic image reuse.
CANDIDATE_ENVIRONMENTS = {**SUPPORTED_ENVIRONMENTS,
    ('getmoto/moto', '4.0'): 'Moto4.0', ('getmoto/moto', '4.1'): 'Moto4.1',
    ('pydantic/pydantic', '2.0'): 'Pydantic2.0'}
