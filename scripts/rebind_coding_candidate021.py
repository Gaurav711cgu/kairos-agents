"""Rebind development provenance without changing issue, excerpts or edit content."""
from copy import deepcopy
import hashlib
from scripts.source_edit_protocol021 import training_messages
from scripts.coding_candidate_policy021 import SOURCE_PREFIXES
from kairos_api.investigations.patches import source_path
from kairos_api.investigations.registry import tree_hash
from kairos_api.model_runtime import digest


def rebind(candidate, source, receipt):
    if (receipt.get('repository'), receipt.get('revision')) != (candidate['repository'], candidate['source_commit']):
        raise ValueError('Pinned source identity differs')
    actual = tree_hash(source)
    if receipt.get('source_digest') != actual:
        raise ValueError('Pinned source tree differs from acquisition receipt')
    training_messages(candidate)
    result = deepcopy(candidate); mapping = {}; changes = []
    prefix = SOURCE_PREFIXES.get(candidate['repository'])
    if prefix is None:
        raise ValueError('Repository has no approved source prefix')
    for block in result['input']['original_source']:
        path = source_path(source, prefix, block['path'])
        if not path.is_file() or path.stat().st_size > 250000:
            raise ValueError('Original source file unavailable or oversized')
        raw = path.read_bytes(); lines = raw.decode().splitlines(True)
        start, end = block['start_line'], block['end_line']
        chosen = lines[start - 1:end]
        numbered = ''.join(f'{n}: {line}' for n, line in enumerate(chosen, start))
        if len(chosen) != end - start + 1 or numbered != block['numbered_original_source']:
            raise ValueError('Captured excerpt differs from pinned source; rebinding forbidden')
        reference = {'path':block['path'], 'source_digest':hashlib.sha256(raw).hexdigest(),
                     'start_line':start, 'end_line':end}
        handle = 'S' + digest({**reference, 'text':''.join(chosen)})[:12]
        old = block['source_id']; mapping[old] = handle; block['source_id'] = handle
        changes.append({'path':block['path'], 'old_handle':old, 'new_handle':handle,
                        'file_sha256':reference['source_digest']})
    for edit in result['assistant_target']['edits']:
        if edit['source_id'] not in mapping:
            raise ValueError('Target references uncaptured source')
        edit['source_id'] = mapping[edit['source_id']]
    result['source_digest'] = actual
    training_messages(result)
    return result, {'version':'coding-source-rebinding021-v1', 'instance_id':candidate['instance_id'],
                    'old_tree_digest':candidate['source_digest'], 'verified_tree_digest':actual,
                    'handle_changes':changes, 'target_ranges_and_replacement_text_unchanged':True,
                    'training_ready':False, 'model_calls':0}
