'use client';
import { caseTitle, configurationLabel, outcomeLabel } from '@/lib/investigations';
import { activeInvestigation } from '@/lib/investigation-client';
import { useInvestigationWorkbench } from '@/hooks/useInvestigationWorkbench';
import { InvestigationInspector } from './InvestigationInspector';
const phases:Record<string,string>={queued:'Waiting for the worker',preparing_workspace:'Preparing the disposable workspace',model_dispatch_pending:'Waiting for the local model',verification_running:'Running registered checks',tool_running:'Running a source tool',result_captured:'Captured the latest result'};
export function InvestigationWorkbench({role,workspace}:{role:string;workspace:string}) {
  const state=useInvestigationWorkbench(workspace),selected=state.selected;
  return <section className="investigation-workbench">
    <div className="investigation-actions"><span>Workspace {workspace} · {role.charAt(0).toUpperCase()+role.slice(1)}</span><button className="button dark" onClick={state.signOut}>Sign out</button></div>
    <header><span className="eyebrow">Registered repository cases</span><h2>Start an investigation.</h2><p>Private by default. Six calls maximum. Source changes stay in a disposable copy.</p></header>
    {state.error && <p role="alert" className="error-state">{state.error}</p>}
    {state.pending.length>0 && <aside className="pending-commands" aria-label="Unconfirmed commands"><p>A submitted command may already be saved. Retry uses its original identity.</p>{state.pending.map(command=><button key={command.key} className="button dark" disabled={state.busy||role==='viewer'} onClick={()=>state.retry(command)}>Retry saved {command.path?'fork':'command'}</button>)}</aside>}
    <div className="investigation-filters">
      <label>Historical case<select value={state.task} onChange={event=>state.setTask(event.target.value)} disabled={!state.loaded||state.busy}>{state.cases.map(item=><option key={item.id} value={item.id}>{caseTitle(item.id,item.title)} · {item.split}</option>)}</select></label>
      <label>Approach<select value={state.configuration} onChange={event=>state.setConfiguration(event.target.value)} disabled={state.busy}><option value="loop-v7">Tool loop · Checked revisions</option><option value="baseline-v7">Single call · Captured line edits</option><option value="loop-v5">Historical tool loop · Version 5</option><option value="baseline-v5">Single call · Source-bound edits</option><option value="loop-v4">Historical tool loop · Version 4</option><option value="baseline-v4">Historical single call · Version 4</option><option value="drafts-v4">Historical independent drafts</option></select></label>
      <button className="button primary" disabled={!state.task||state.busy||role==='viewer'} onClick={state.submit}>{state.busy?'Saving command…':'Queue investigation'}</button>
      <button className="button dark" onClick={state.refresh} disabled={state.busy}>Refresh records</button>
    </div>
    {state.loaded&&!state.cases.length&&<p>No cases have passed preflight. Prepare and verify the registered cases first.</p>}
    <p className="investigation-scope">Evaluation and validation cases are frozen study material. An interactive rerun is a new attempt, not an untouched holdout result.</p>
    <div className="private-investigation-list">{state.records.map(item=><button key={item.id} onClick={()=>state.inspect(item.id)} aria-pressed={state.selectedId===item.id}><span>{caseTitle(item.task_id,item.title)}</span><small>{configurationLabel(item.configuration)} · {outcomeLabel(item.outcome,item.status)}</small></button>)}</div>
    {state.cursor&&<button className="button dark" onClick={state.loadMore}>Load earlier records</button>}
    {state.loadingDetail&&<p role="status">Loading the selected investigation…</p>}
    {selected&&<div className="private-investigation-detail"><h3>{caseTitle(selected.task_id,selected.task_snapshot.title)}</h3><p aria-live="polite">{phases[state.phase]||outcomeLabel(selected.outcome,selected.status)} · {selected.model_calls} model {selected.model_calls===1?'call':'calls'} · {selected.check_count} check {selected.check_count===1?'run':'runs'}</p>
      {state.playback&&<p role="status">Recorded playback. No model calls or tool execution.</p>}
      <div className="investigation-actions"><button className="button dark" disabled={state.busy} onClick={state.replay}>Replay saved steps</button><button className="button dark" disabled={state.busy} onClick={()=>state.inspect(selected.id)}>Refresh this attempt</button><button className="button dark" disabled={state.busy||role==='viewer'||!activeInvestigation(selected.status)} onClick={()=>state.mutate('cancel')}>Cancel</button><button className="button dark" disabled={state.busy||role==='viewer'} onClick={()=>state.mutate('fork')}>Create a fresh fork</button>{role==='admin'&&<button className="button dark" disabled={state.busy||activeInvestigation(selected.status)||selected.published} onClick={()=>state.mutate('publish')}>Publish evidence</button>}</div>
      <InvestigationInspector key={selected.id} record={selected} comparison={null} privateView />
    </div>}
  </section>;
}
