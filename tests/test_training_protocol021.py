from types import SimpleNamespace
import pytest
from scripts import coding_train014 as training
from scripts.source_edit_protocol021 import tokenize_training
from scripts.coding_resource014 import resource_identity
from test_coding_train014 import row


class Tokenizer:
    def apply_chat_template(self, turns, tokenize, add_generation_prompt):
        text=''.join(t['role']+':'+t['content']+'\n' for t in turns)
        return list((text+('assistant:' if add_generation_prompt else '')).encode())


def test_legacy_tokenization_stays_default():
    example=row(1,'example/repo'); tokenizer=Tokenizer()
    assert training.tokenize_example(tokenizer,example)==training.tokenize_example(tokenizer,example,source_protocol='legacy014')


def test_explicit_shared_protocol_uses_same_training_inference_prefix():
    example=row(1,'example/repo'); tokenizer=Tokenizer()
    assert training.tokenize_example(tokenizer,example,source_protocol='shared021')==tokenize_training(tokenizer,example,maximum=2048)


def test_unknown_protocol_rejected():
    with pytest.raises(ValueError,match='Unknown'):training.tokenize_example(Tokenizer(),row(1,'example/repo'),source_protocol='unknown')


def test_shared_protocol_cannot_start_unadmitted_full_training(monkeypatch):
    monkeypatch.setattr(training,'admitted_inputs',lambda *_:pytest.fail('Must fail before admission or model loading'))
    with pytest.raises(ValueError,match='limited'):
        training.run(SimpleNamespace(source_protocol='shared021',study='public100'))


def test_resource_identity_separates_protocols():
    old={'profile':'14B','planned_steps':20};new={**old,'source_protocol':'source-edit-protocol021-v1','source_protocol_sha256':'a'*64}
    assert resource_identity(old)!=resource_identity(new)


def test_doctor_declares_selected_shared_protocol_without_loading_model(monkeypatch,capsys):
    import sys,json
    monkeypatch.setattr(sys,'argv',['coding_train014','doctor','--study','resource2','--source-protocol','shared021'])
    training.main()
    report=json.loads(capsys.readouterr().out)
    assert report['source_protocol']=='source-edit-protocol021-v1'
    assert len(report['source_protocol_sha256'])==64
    assert report['training_started'] is False and report['ready'] is False


def test_historical_step_budgets_stay_unchanged():
    assert training.planned_steps(SimpleNamespace(action='fit'), 2) == 20
    assert training.planned_steps(SimpleNamespace(action='train', study='public100'), 100) == 40
    assert training.planned_steps(SimpleNamespace(action='train'), 200) == 25


def test_longer_sanity_requires_explicit_shared_training_scope():
    args = SimpleNamespace(action='fit', study='resource2', source_protocol='shared021', sanity_steps=80)
    assert training.planned_steps(args, 2) == 80
    for field, value in [('action', 'train'), ('study', 'public100'), ('source_protocol', 'legacy014')]:
        changed = SimpleNamespace(**{**vars(args), field: value})
        with pytest.raises(ValueError, match='limited'):
            training.planned_steps(changed, 2)


def test_unregistered_step_budget_rejected():
    with pytest.raises(ValueError, match='20 or 80'):
        training.planned_steps(SimpleNamespace(action='fit', sanity_steps=81), 2)


def test_expanded_budget_refused_before_admission(monkeypatch):
    monkeypatch.setattr(training, 'admitted_inputs', lambda *_: pytest.fail('No admission or model access'))
    args = SimpleNamespace(action='train', study='public100', source_protocol='shared021', sanity_steps=80)
    with pytest.raises(ValueError, match='limited'):
        training.run(args)
