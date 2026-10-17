"""Issue-only class/function context for coding supervision revision two."""
import ast
import re
import warnings
from kairos_api.investigations.context_v7 import initial_sources
from kairos_api.investigations.patches import source_path

VERSION='issue-symbols-and-source-margins014-v2'


def select(workspace):
    """Select original regions without reference patches, tests or entry hints."""
    issue=workspace.case['issue'];symbols=set(re.findall(r'[A-Za-z_]\w*',issue))
    root=workspace.registry.directory(workspace.case)/'source'
    candidates=[]
    for path in sorted((root/workspace.case['approved_prefix']).rglob('*.py')):
        name=path.relative_to(root).as_posix()
        try:
            target=source_path(root,workspace.case['approved_prefix'],name)
            if target.stat().st_size>250000:continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',SyntaxWarning)
                tree=ast.parse(target.read_text())
        except (ValueError,OSError,UnicodeError,SyntaxError):continue
        cited_path=name in issue
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in symbols and not node.name.startswith('__'):
                candidates.append((0 if cited_path else 2,name,node.lineno,node,'Public issue names this function'))
            if isinstance(node,ast.ClassDef) and node.name in symbols:
                if node.end_lineno-node.lineno+1<=72:
                    candidates.append((1,name,node.lineno,node,'Public issue names this complete class'))
                else:
                    methods=[n for n in node.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
                    for method in methods:
                        if method.name in symbols or method.name in {'__init__','__call__'}:
                            rank=1 if method.name in symbols else 2
                            candidates.append((rank,name,method.lineno,method,'Original method of public-issue class '+node.name))
    selected=[];omissions=[]
    def capture(name,node,reason):
        start=min([node.lineno]+[d.lineno for d in getattr(node,'decorator_list',[])])
        end=node.end_lineno
        if end-start+1>72:
            # Long docstrings must not consume the whole implementation window.
            body=getattr(node,'body',[])
            if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str) and len(body)>1:
                start=body[1].lineno
                reason+='; long docstring/signature omitted from this body window'
            end=min(end,start+71)
            omissions.append({'path':name,'reason':'Definition exceeds bounded implementation window; omitted lines are not supplied'})
        total=len((root/name).read_text().splitlines())
        start=max(1,start-4);end=min(total,end+4,start+79)
        if any(r['reference']['path']==name and r['reference']['start_line']<=start<=end<=r['reference']['end_line'] for r in selected):return
        try:result=workspace.read_original(name,start,end)
        except ValueError:
            omissions.append({'path':name,'reason':'Complete original region exceeds source-read bounds'});return
        result['selection_reason']=reason+'; at most four original neighboring lines for insertion anchors'
        selected.append(result)
    for _,name,_,node,reason in sorted(candidates,key=lambda item:item[:3]):
        capture(name,node,reason)
        if len(selected)==4:break
    if len(selected)<4:
        for item in initial_sources(workspace,use_entry_hints=False):
            ref=item['reference']
            if any(r['reference']['path']==ref['path'] and r['reference']['start_line']<=ref['start_line']<=ref['end_line']<=r['reference']['end_line'] for r in selected):continue
            selected.append(item)
            if len(selected)==4:break
    if selected:selected[0]['localization']={'version':VERSION,'selected_regions':len(selected),'maximum_regions':4,'source':'Public issue and original source only; no entry hints, reference patch or hidden tests','omissions':omissions,'lower_ranked_candidates_omitted':max(0,len(candidates)-len(selected))}
    return selected
