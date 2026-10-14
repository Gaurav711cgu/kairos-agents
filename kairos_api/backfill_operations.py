"""Versioned missing-value operations; fingerprints bind executable semantics."""
import hashlib
import inspect
import json
from kairos_api.jobs_repository import input_snapshot
from kairos_api.model_runtime import digest

OPERATIONS = {
    'investigation-config-digest-v2': {'table':'kairos_investigations','column':'config_digest','algorithm':'sha256-canonical-config-snapshot-v1'},
    'job-input-snapshot-v2': {'table':'kairos_jobs','column':'input_snapshot','algorithm':'frozen-scenario-input-with-existing-digest-match-v1'},
}


def value_for(name, row):
    if name == 'investigation-config-digest-v2':
        return digest(row['config_snapshot']), True
    value = input_snapshot(row['scenario_id'], row['policy'], row['context_blocks'])
    return value, digest(value) == row['input_digest']


def checksum(name):
    specification = {'operation':name, **OPERATIONS[name],
        'source':[inspect.getsource(function) for function in (value_for,input_snapshot,digest)]}
    return hashlib.sha256(json.dumps(specification,sort_keys=True,separators=(',',':')).encode()).hexdigest()
