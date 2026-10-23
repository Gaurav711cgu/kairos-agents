"""One bounded validator-feedback turn for the 021 single-shot protocol; model-independent.

Turn one is the unchanged 021 prompt. Its captured generation is validated
offline with the same parser and source-handle validator the scorer uses. Only a
parser or source-validator rejection earns exactly one more turn, whose prompt is the turn-one
prompt plus ``rejection_feedback010`` (exact coordinates, whitespace and the
rejected replacement), never a corrected edit. Regression tests stay a separate,
later step.
"""
import json

from kairos_api.investigations.context_v7 import source_block
from scripts.coding_eval020 import parse_action
from scripts.repair010.feedback010 import FeedbackContextOverflow010, rejection_feedback010

VERSION = 'validator-feedback-turn021-v1'
MAX_FEEDBACK_TURNS = 1
INSTRUCTION = ('Your previous action was rejected by the source validator. Return one corrected JSON '
               'propose_patch action using only the captured source handles.')


def validate021(workspace, text, regions):
    """Parse and render the edit exactly as scoring does; the original snapshot is never written."""
    handles = [source_block(region)['source_id'] for region in regions]
    try:
        action, _ = parse_action(text, handles)
    except (ValueError, KeyError, TypeError, RecursionError) as error:  # deep nesting must reject, not crash
        return {'accepted': False, 'stage': 'parse', 'reason': type(error).__name__ if isinstance(error, RecursionError) else str(error), 'action': None}
    authority = {source_block(region)['source_id']: region['reference'] for region in regions}
    try:
        rendered = workspace.propose_line_edits(action['edits'], authority)
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {'accepted': False, 'stage': 'validate', 'reason': type(error).__name__ + ': ' + str(error), 'action': action}
    return {'accepted': True, 'stage': 'validate', 'patch': rendered['patch'], 'action': action}


def next_turn021(first_messages, regions, verdict, *, tokenizer, maximum_prompt_tokens, maximum_bytes=6000):
    """Return turn-two messages, or None when accepted or the one-turn limit is reached.

    Keeps the trained system/user shape: the turn-one payload gains one
    ``rejected_attempt`` key. The rejected replacement travels inside the feedback,
    so no assistant turn is repeated. The turn count comes from the prompt itself,
    never from the caller. Over the token or byte cap it fails closed.
    """
    payload = json.loads(first_messages[1]['content'])
    if verdict['accepted'] or 'rejected_attempt' in payload:  # MAX_FEEDBACK_TURNS == 1
        return None
    request = None if verdict['action'] is None else {'action': 'propose_patch', 'edits': verdict['action']['edits'], 'model_seq': 1}
    observation = {'action': 'propose_patch', 'sequence': 1, 'request': request, 'result': {'error': verdict['reason']},
                   'proposal_context': {'sequence': 0, 'source_catalog': regions,
                                        'reference_bindings': {source_block(r)['source_id']: r['reference'] for r in regions}}}
    payload['rejected_attempt'] = {'protocol': VERSION, 'feedback': rejection_feedback010([observation], maximum_bytes),
                                   'instruction': INSTRUCTION}
    second = [first_messages[0], {'role': 'user', 'content': json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)}]
    if len(tokenizer.apply_chat_template(second, tokenize=True, add_generation_prompt=True)) > maximum_prompt_tokens:
        raise FeedbackContextOverflow010('Turn-two prompt exceeds the declared token cap; no dispatch')
    return second
