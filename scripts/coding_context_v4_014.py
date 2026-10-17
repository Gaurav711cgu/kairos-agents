"""Pack complete issue-selected source regions before reading supervision targets."""
import ast
from pathlib import Path

from kairos_api.investigations.context_v7 import source_block
from kairos_api.investigations.patches import source_path
from scripts.coding_context_v3_014 import select as linked_sources
from scripts.coding_train014 import encoded, read_bound, sha_file, safe_path

VERSION = 'issue-linked-source-token-packing014-v4'
MAX_PROMPT_TOKENS = 1536
INSTRUCTION = 'Return one propose_patch JSON action using source_id, start_line, end_line and new. Replace inclusive whole original-source lines. Preserve indentation.'
SYSTEM = 'Repair Python source using captured original-source handles. Return one JSON edit action.'


def load_tokenizer(directory, receipt_sha256):
    """Load only hash-bound local tokenizer files; never load model weights."""
    directory = Path(directory)
    receipt = read_bound(directory / 'tokenizer-receipt.json', receipt_sha256)
    if (receipt.get('version') != 'coding-tokenizer-acquisition014-v1'
            or receipt.get('model') != 'unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit'
            or receipt.get('revision') != 'ecfc63c083900ce4f19daad695e711f38ab98fcf'):
        raise ValueError('Pinned tokenizer identity differs')
    allowed = {'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'added_tokens.json', 'config.json'}
    if not {'tokenizer.json', 'tokenizer_config.json'} <= set(receipt['files']) <= allowed:
        raise ValueError('Unexpected tokenizer file manifest')
    observed = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    if observed != set(receipt['files']) | {'tokenizer-receipt.json'}:
        raise ValueError('Tokenizer file set differs')
    for name, item in receipt['files'].items():
        path = safe_path(directory, name)
        if path.stat().st_size != item['bytes'] or sha_file(path) != item['sha256']:
            raise ValueError('Tokenizer file bytes differ')
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)


def prompt_tokens(tokenizer, issue, regions):
    value = {'issue': issue, 'original_source': [source_block(item) for item in regions], 'instruction': INSTRUCTION}
    return len(tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': encoded(value).decode()}], tokenize=True, add_generation_prompt=True))


def select(workspace, tokenizer):
    """Reserve 512 of 2,048 tokens without inspecting the eventual edit target."""
    candidates = linked_sources(workspace)
    root = workspace.registry.directory(workspace.case) / 'source'
    compacted = []
    omissions = []
    for item in candidates:
        reference = item['reference']
        start, end = reference['start_line'], reference['end_line']
        target = source_path(root, workspace.case['approved_prefix'], reference['path'])
        tree = ast.parse(target.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or not 0 <= node.lineno - start <= 4:
                continue
            body = node.body
            if (len(body) > 1 and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)
                    and body[0].end_lineno - body[0].lineno + 1 >= 8
                    and body[0].end_lineno < end):
                begin = min([body[1].lineno] + [d.lineno for d in getattr(body[1], 'decorator_list', [])])
                omissions.append({'path': reference['path'], 'start_line': start, 'end_line': begin - 1, 'reason': 'Leading declaration and long documentation omitted; only captured implementation lines remain editable'})
                start = begin
                break
        result = workspace.read_original(reference['path'], start, end)
        result['selection_reason'] = item.get('selection_reason', 'Issue-selected original source')
        compacted.append(result)
    while compacted and prompt_tokens(tokenizer, workspace.case['issue'], compacted) > MAX_PROMPT_TOKENS:
        omitted = compacted.pop()
        reference = omitted['reference']
        omissions.append({'path': reference['path'], 'start_line': reference['start_line'], 'end_line': reference['end_line'], 'reason': 'Lower-priority whole source region exceeds fixed prompt-token budget'})
    if not compacted:
        raise ValueError('Issue and complete original-source regions exceed prompt budget; no JSON truncation allowed')
    compacted[0]['localization'] = {'version': VERSION, 'parent_policy': 'issue-linked-source-and-imports014-v3', 'source': 'Public issue, original source and pinned tokenizer only; target not read', 'maximum_regions': 4, 'maximum_prompt_tokens': MAX_PROMPT_TOKENS, 'reserved_target_tokens': 512, 'prompt_tokens': prompt_tokens(tokenizer, workspace.case['issue'], compacted), 'omissions': omissions, 'parent_omissions': candidates[0].get('localization', {}).get('omissions', [])}
    return compacted
