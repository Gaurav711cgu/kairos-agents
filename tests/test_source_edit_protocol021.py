import pytest
from scripts.source_edit_protocol021 import messages, training_messages


def source(**extra):
    return {'source_id':'S0123456789ab','path':'src/value.py','start_line':8,'end_line':9,**extra}


def test_training_and_inference_have_identical_bytes_and_indentation():
    plain='def value():\n    return 1\n'
    numbered='8: def value():\n9:     return 1\n'
    row={'input':{'issue':'Fix value','original_source':[source(numbered_original_source=numbered)]}}
    assert training_messages(row)==messages('Fix value',[source(original_source=plain)])
    assert '9:     return 1' in messages('Fix value',[source(original_source=plain)])[1]['content']


@pytest.mark.parametrize('block',[
    source(original_source='one line\n'),
    source(numbered_original_source='1: wrong\n2: offsets\n'),
    source(original_source='a\nb\n',numbered_original_source='8: a\n9: b\n'),
    {**source(original_source='a\nb\n'),'start_line':True},
])
def test_incomplete_ambiguous_or_stale_numbering_rejected(block):
    with pytest.raises(ValueError):messages('Issue',[block])


def test_duplicate_handles_rejected():
    block=source(original_source='a\nb\n')
    with pytest.raises(ValueError):messages('Issue',[block,block])


def test_supervised_suffix_matches_inference_and_masks_prompt(monkeypatch):
    from scripts.source_edit_protocol021 import tokenize_training
    class Tokenizer:
        def apply_chat_template(self, turns, tokenize, add_generation_prompt):
            # Character tokens make exact prefix/suffix behavior inspectable.
            raw=''.join(t['role']+':'+t['content']+'\n' for t in turns)
            if add_generation_prompt:raw+='assistant:'
            return list(raw.encode())
    row={'input':{'issue':'Fix value','original_source':[source(original_source='def value():\n    return 1\n')]},
         'assistant_target':{'action':'propose_patch','edits':[{'source_id':'S0123456789ab','start_line':9,'end_line':9,'new':'    return 2'}]}}
    tokenizer=Tokenizer();result=tokenize_training(tokenizer,row)
    prefix=tokenizer.apply_chat_template(training_messages(row),True,True)
    assert result['labels'][:len(prefix)]==[-100]*len(prefix)
    assert result['labels'][len(prefix):]==result['input_ids'][len(prefix):]
    with pytest.raises(ValueError,match='truncation'):tokenize_training(tokenizer,row,maximum=10)
