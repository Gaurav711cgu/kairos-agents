"""Public line hints never grant access to answers or a different source tree."""
from pathlib import Path
import urllib.request
import pytest
from scripts.coding_context_v5_014 import citations,select
from scripts.coding_context_v4_014 import select as original
from test_coding_context014 import make_workspace
from test_coding_context_v4_014 import SourceOnlyTokenizer


def test_cited_function_and_its_direct_method_are_captured(tmp_path):
    text='class Target:\n    def _value(self):\n        return "wrong"\n\n    def validate(self):\n        value = self._value()\n        return value\n'
    # Separate the two functions so neighbor padding cannot already cover both.
    text=text.replace('    def validate', '\n'*12+'    def validate')
    line=next(i for i,value in enumerate(text.splitlines(),1) if 'def validate' in value)
    w=make_workspace(tmp_path,text,f'TypeError at https://github.com/upstream/project/blob/old-revision/package/value.py#L{line}-L{line+2}')
    try:
        regions=select(w,SourceOnlyTokenizer())
        assert any('def _value' in item['text'] for item in regions)
        assert any('def validate' in item['text'] for item in regions)
        assert any('direct callee' in item['selection_reason'] for item in regions)
        for item in regions:w.restore_reference(item)
        assert regions[0]['localization']['version']=='issue-cited-source-and-callees014-v5'
        assert (w.registry.directory(w.case)/'source/package/value.py').read_text()==text
    finally:w.close()


def test_module_line_citation_without_enclosing_function(tmp_path):
    w=make_workspace(tmp_path,'VALUE = "original"\n','Fix https://github.com/o/r/blob/main/package/value.py#L1')
    try:
        result=select(w,SourceOnlyTokenizer())
        assert 'VALUE = "original"' in result[0]['text']
        assert result[0]['reference']['start_line']==1
    finally:w.close()


def test_no_citations_preserves_v4_source_selection(tmp_path):
    w=make_workspace(tmp_path,'class Target:\n    value = 1\n','Target is wrong')
    try:
        before=original(w,SourceOnlyTokenizer());after=select(w,SourceOnlyTokenizer())
        assert [r['reference'] for r in before]==[r['reference'] for r in after]
        assert 'fallback' in after[0]['localization']
    finally:w.close()


def test_selection_never_reads_answers_or_fetches_cited_revision(tmp_path,monkeypatch):
    w=make_workspace(tmp_path,'def target():\n    return 1\n','Fix https://github.com/o/r/blob/different/package/value.py#L1-L2')
    read=Path.read_text
    def guarded(path,*args,**kwargs):
        if path.name in {'reference.patch','test.patch','verify.py','hidden_answer.py'}:raise AssertionError('Hidden material read')
        return read(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guarded)
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:pytest.fail('Remote content fetched'))
    try:assert select(w,SourceOnlyTokenizer())
    finally:w.close()


@pytest.mark.parametrize('path',['../outside.py','package/../../outside.py','package/escape.py'])
def test_paths_and_symlinks_cannot_escape_original_source(tmp_path,path):
    w=make_workspace(tmp_path,'def target():\n    return 1\n','target is wrong https://github.com/o/r/blob/main/'+path+'#L1')
    secret=tmp_path/'outside.py';secret.write_text('SECRET = "do not read"\n')
    (w.registry.directory(w.case)/'source/package/escape.py').symlink_to(secret)
    try:
        regions=select(w,SourceOnlyTokenizer())
        assert all('SECRET' not in item['text'] for item in regions)
    finally:w.close()


def test_long_callee_is_omitted_with_reason_and_bounds_preserved(tmp_path):
    text='class Target:\n    def helper(self):\n'+''.join('        value_'+str(i)+' = '+str(i)+'\n' for i in range(100))+'\n    def validate(self):\n        return self.helper()\n'
    w=make_workspace(tmp_path,text,'Fix https://github.com/o/r/blob/main/package/value.py#L104-L105')
    try:
        regions=select(w,SourceOnlyTokenizer())
        assert all(r['reference']['end_line']-r['reference']['start_line']<80 for r in regions)
        assert any('Complete callee' in item['reason'] for item in regions[0]['localization']['omissions'])
        assert regions[0]['localization']['prompt_tokens']<=1536
    finally:w.close()


def test_oversized_issue_rejects_without_json_truncation(tmp_path):
    w=make_workspace(tmp_path,'def target():\n    return 1\n','target '+ 'x'*9000+' https://github.com/o/r/blob/main/package/value.py#L1-L2')
    try:
        with pytest.raises(ValueError,match='no JSON truncation'):select(w,SourceOnlyTokenizer())
    finally:w.close()


def test_bad_or_unbounded_line_hints_are_not_authority():
    assert not list(citations('https://github.com/o/r/blob/main/package/value.py#L0-L20'))
    assert not list(citations('https://github.com/o/r/blob/main/package/value.py#L1-L200'))
    assert not list(citations('https://github.com/o/r/blob/main/package/value.py#L9-L1'))
