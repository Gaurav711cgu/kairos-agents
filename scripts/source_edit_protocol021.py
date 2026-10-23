"""Shared development protocol for training and inference; historical v020 stays frozen."""
import json

VERSION = 'source-edit-protocol021-v1'
SYSTEM = ('Repair Python source using only captured source handles. Return one JSON object '
          'with action="propose_patch" and edits containing source_id, start_line, end_line, '
          'and new. Replace inclusive numbered original lines. Preserve indentation. '
          'Do not edit tests. Do not include unchanged edits.')


def messages(issue, sources):
    if not isinstance(issue, str) or not issue.strip():
        raise ValueError('A nonempty issue is required')
    if not isinstance(sources, list) or not 1 <= len(sources) <= 4:
        raise ValueError('One to four captured source regions required')
    normalized, handles = [], set()
    for source in sources:
        handle = source['source_id']
        import re
        if not isinstance(handle, str) or not re.fullmatch(r'S[a-f0-9]{12}', handle) or handle in handles:
            raise ValueError('Invalid or duplicate source handle')
        handles.add(handle)
        start, end = source['start_line'], source['end_line']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= start + 79:
            raise ValueError('Invalid captured source bounds')
        numbered = source.get('numbered_original_source')
        plain = source.get('original_source')
        if (numbered is None) == (plain is None):
            raise ValueError('Exactly one original-source representation required')
        if numbered is not None:
            lines = numbered.splitlines(keepends=True)
            if len(lines) != end - start + 1 or any(not line.startswith(f'{n}: ') for n, line in enumerate(lines, start)):
                raise ValueError('Numbered source differs from bounds')
            numbered = ''.join(lines)
        else:
            if not isinstance(plain, str):
                raise ValueError('Original source must be text')
            lines = plain.splitlines(keepends=True)
            if len(lines) != end - start + 1:
                raise ValueError('Complete source lines required')
            numbered = ''.join(f'{n}: {line}' for n, line in enumerate(lines, start))
        if len(numbered.encode()) > 12000:
            raise ValueError('Source region exceeds bounded context')
        normalized.append({'source_id': handle, 'path': source['path'], 'start_line': start,
                           'end_line': end, 'numbered_original_source': numbered})
    payload = {'protocol': VERSION, 'issue': issue, 'original_source': normalized}
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)}]


def training_messages(row):
    return messages(row['input']['issue'], row['input']['original_source'])


def tokenize_training(tokenizer, row, maximum=4096):
    """Supervise only the assistant suffix using exactly the inference prefix."""
    prompt = training_messages(row)
    target = row['assistant_target']
    from scripts.coding_eval020 import parse_action
    parse_action(json.dumps(target), [source['source_id'] for source in row['input']['original_source']])
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    complete = tokenizer.apply_chat_template(prompt + [{'role':'assistant','content':json.dumps(
        target, sort_keys=True, separators=(',', ':'), ensure_ascii=False)}],
        tokenize=True, add_generation_prompt=False)
    if complete[:len(prefix)] != prefix or len(complete) <= len(prefix):
        raise ValueError('Chat template must preserve the exact inference prefix')
    if len(complete) > maximum:
        raise ValueError('Complete training sequence exceeds budget; truncation forbidden')
    return {'input_ids':complete,'attention_mask':[1]*len(complete),
            'labels':[-100]*len(prefix)+complete[len(prefix):]}
