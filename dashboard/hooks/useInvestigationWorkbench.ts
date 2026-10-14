'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { z } from 'zod';
import { investigationSchema, investigationSummary, type Investigation, type InvestigationSummary } from '@/lib/investigations';
import { activeInvestigation, clearCommand, investigationCommand, InvestigationRequestError, LatestRead, saveCommand, savedCommands, type SavedCommand } from '@/lib/investigation-client';
const caseSchema=z.object({id:z.string(),title:z.string(),qualified:z.boolean(),split:z.string()});
const pageSchema=z.object({investigations:z.array(investigationSummary),next_cursor:z.string().nullable()});
const progressSchema=z.object({id:z.string(),status:z.string(),outcome:z.string().nullable(),model_calls:z.number(),patch_count:z.number(),check_count:z.number(),phase:z.string(),latest_sequence:z.number(),updated_at:z.string()});
const message=(error:unknown)=>error instanceof Error?error.message:'Investigation service unavailable.';
export function useInvestigationWorkbench(workspace:string) {
  const [cases,setCases]=useState<z.infer<typeof caseSchema>[]>([]),[records,setRecords]=useState<InvestigationSummary[]>([]);
  const [task,setTask]=useState(''),[configuration,setConfiguration]=useState('loop-v7');
  const [selected,setSelected]=useState<Investigation|null>(null),[selectedId,setSelectedId]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[loaded,setLoaded]=useState(false),[loadingDetail,setLoadingDetail]=useState(false);
  const [playback,setPlayback]=useState(false),[phase,setPhase]=useState(''),[pending,setPending]=useState<SavedCommand[]>([]),[cursor,setCursor]=useState<string|null>(null);
  const reads=useRef(new LatestRead()),lists=useRef(new LatestRead()),mounted=useRef(true),commandLock=useRef(false);
  const refresh=useCallback(async(appendCursor?:string)=>{
    const ticket=lists.current.begin();
    try {
      const [caseList,listing]=await Promise.all([investigationCommand('/cases',{signal:ticket.signal}),investigationCommand(appendCursor?'?cursor='+encodeURIComponent(appendCursor):'',{signal:ticket.signal})]);
      if(!lists.current.current(ticket.version))return;
      const registered=z.object({cases:z.array(caseSchema)}).parse(caseList).cases.filter(c=>c.qualified),page=pageSchema.parse(listing);
      setCases(registered);setTask(previous=>previous||registered[0]?.id||'');setRecords(previous=>appendCursor?[...previous,...page.investigations.filter(r=>!previous.some(p=>p.id===r.id))]:page.investigations);
      setCursor(page.next_cursor);setLoaded(true);
    }catch(failure){if(lists.current.current(ticket.version))setError(message(failure));}
  },[]);
  useEffect(()=>{
    mounted.current=true;const currentReads=reads.current,currentLists=lists.current;
    const timer=setTimeout(()=>{try{setPending(savedCommands(sessionStorage,workspace));}catch{setError('Browser command storage is unavailable.');}void refresh();},0);
    return()=>{mounted.current=false;clearTimeout(timer);currentReads.stop();currentLists.stop();};
  },[refresh,workspace]);
  const inspect=useCallback(async(id:string,replay=false)=>{
    const ticket=reads.current.begin();setSelectedId(id);setSelected(null);setLoadingDetail(true);setPlayback(replay);setError('');setPhase('');
    try{
      const value=await investigationCommand('/'+id+(replay?'/replay':''),{signal:ticket.signal});
      const record=investigationSchema.parse(replay?value.investigation:value);
      if(reads.current.current(ticket.version)){setSelected(record);setPhase(record.status);}
    }catch(failure){if(reads.current.current(ticket.version))setError(message(failure));}
    finally{if(reads.current.current(ticket.version))setLoadingDetail(false);}
  },[]);
  useEffect(()=>{
    if(!selected || playback || !activeInvestigation(selected.status))return;
    const id=selected.id;let disposed=false,timer:ReturnType<typeof setTimeout>|undefined,controller:AbortController|undefined;
    const schedule=(ms:number)=>{if(!disposed && document.visibilityState==='visible')timer=setTimeout(poll,ms);};
    const poll=async()=>{
      controller=new AbortController();let delay=2000;
      try{
        const progress=progressSchema.parse(await investigationCommand('/'+id+'/progress',{signal:controller.signal}));
        if(disposed)return;
        setPhase(progress.phase);setError('');
        if(progress.latest_sequence!==selected.steps.at(-1)?.seq && (progress.latest_sequence!==0 || selected.steps.length) || progress.updated_at!==selected.updated_at || progress.status!==selected.status){
          const value=investigationSchema.parse(await investigationCommand('/'+id,{signal:controller.signal}));
          if(!disposed)setSelected(value);
        }
        if(!activeInvestigation(progress.status))return;
      }catch(failure){if(!disposed && !controller.signal.aborted){setError(message(failure)+' Retrying in 30 seconds.');delay=30000;}}
      schedule(delay);
    };
    const visibility=()=>{clearTimeout(timer);controller?.abort();if(document.visibilityState==='visible')schedule(0);};
    document.addEventListener('visibilitychange',visibility);schedule(2000);
    return()=>{disposed=true;clearTimeout(timer);controller?.abort();document.removeEventListener('visibilitychange',visibility);};
  },[selected,playback]);
  const execute=async(path:string,body:Record<string,string>,saved?:SavedCommand)=>{
    if(commandLock.current)return;commandLock.current=true;setBusy(true);setError('');
    const ticket=reads.current.begin();let command:SavedCommand|undefined=saved;
    try{
      command=command||saveCommand(sessionStorage,workspace,path,body);setPending(savedCommands(sessionStorage,workspace));
      const value=investigationSchema.parse(await investigationCommand(command.path,{body:command.body,key:command.key}));
      clearCommand(sessionStorage,workspace,command.key);
      if(!mounted.current)return;
      setPending(savedCommands(sessionStorage,workspace));
      if(reads.current.current(ticket.version)){setSelectedId(value.id);setSelected(value);setPlayback(false);setPhase(value.status);setLoadingDetail(false);}
      await refresh();
    }catch(failure){
      if(command && failure instanceof InvestigationRequestError && failure.status>=400 && failure.status<500 && ![401,403,408].includes(failure.status))clearCommand(sessionStorage,workspace,command.key);
      if(mounted.current){try{setPending(savedCommands(sessionStorage,workspace));}catch{/* Storage denial already prevents dispatch. */}setError(message(failure)+' Retry the saved command to keep its identity.');}
    }finally{commandLock.current=false;if(mounted.current)setBusy(false);}
  };
  const mutate=async(operation:'cancel'|'fork'|'publish')=>{
    if(!selected)return;
    if(operation==='fork')return execute('/'+selected.id+'/fork',{configuration});
    if(commandLock.current)return;commandLock.current=true;setBusy(true);setError('');const id=selected.id;
    const ticket=reads.current.begin();
    try{
      const record=investigationSchema.parse(await investigationCommand('/'+id+'/'+operation,{body:{}}));
      if(reads.current.current(ticket.version)){setSelected(record);setPlayback(false);setPhase(record.status);}
      await refresh();
    }catch(failure){if(mounted.current)setError(message(failure));}
    finally{commandLock.current=false;if(mounted.current)setBusy(false);}
  };
  const signOut=async()=>{try{const response=await fetch('/api/workbench/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw new Error('Sign out failed.');window.location.assign('/workbench');}catch(failure){setError(message(failure));}};
  return {cases,records,task,setTask,configuration,setConfiguration,selected,selectedId,loadingDetail,error,busy,loaded,playback,phase,pending,cursor,
    refresh:()=>refresh(),loadMore:()=>cursor&&refresh(cursor),inspect,replay:()=>selected&&inspect(selected.id,true),submit:()=>execute('',{task_id:task,configuration}),retry:(command:SavedCommand)=>execute(command.path,command.body,command),mutate,signOut};
}
