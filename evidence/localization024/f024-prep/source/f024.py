"""F024 offline harness: memory preflight, outcome classes and turn-two planning.

No model call happens here. Turn-one prompts come from the frozen 021 pack; captures
come back from an approved Colab run and are validated locally by ``validate021``.
"""
from scripts.feedback_turn021 import next_turn021, validate021
from scripts.repair010.feedback010 import FeedbackContextOverflow010

# Largest input+output ever observed on the T4 profile (peak 14.42 of 14.6 GiB).
# Unknown territory beyond it is refused, not attempted.
ENVELOPE_TOKENS = 3539
TURN1_MAX_NEW = 1024
TURN2_MAX_NEW = 512


def preflight(prompt_tokens, max_new_tokens):
    return prompt_tokens + max_new_tokens <= ENVELOPE_TOKENS


def classify(verdict):
    if verdict['accepted']:
        return 'accepted'
    if verdict['stage'] == 'parse':
        return 'parse'
    reason = verdict['reason']
    if 'syntax rejected' in reason:
        return 'syntax_indentation' if 'indent' in reason else 'syntax_other'
    if 'escapes captured excerpt' in reason or 'bounds' in reason:
        return 'range'
    if 'makes no change' in reason:
        return 'no_change'
    return 'validator_other'


def turn2(jobs, captures, context_for, tokenizer):
    """Plan turn two for rejected turn-one captures that fit the envelope; record every outcome."""
    planned, ledger = [], {}
    for job in jobs:
        text = captures.get(job['job_id'])
        if text is None:
            ledger[job['job_id']] = 'generation_missing'  # uncertain or failed dispatch: never redispatched
            continue
        workspace, regions = context_for(job)
        verdict = validate021(workspace, text, regions)
        ledger[job['job_id']] = classify(verdict)
        try:
            second = next_turn021(job['messages'], regions, verdict, maximum_bytes=1500, tokenizer=tokenizer,
                                  maximum_prompt_tokens=ENVELOPE_TOKENS - TURN2_MAX_NEW)
        except FeedbackContextOverflow010:
            ledger[job['job_id']] += '+turn2_over_envelope'
            continue
        if second is not None:
            planned.append({'job_id': job['job_id'].rsplit('/', 1)[0] + '/t2', 'messages': second, 'max_new_tokens': TURN2_MAX_NEW})
    return planned, ledger
