/** Browser command identities contain no credentials or artifact bodies. */
export type SavedCommand = { path: string; body: Record<string, string>; key: string; createdAt: string };
export type CommandStorage = Pick<Storage, 'getItem' | 'setItem'>;
const storageKey = (workspace: string) => 'kairos:investigation-commands:v1:' + encodeURIComponent(workspace);
export function savedCommands(storage: CommandStorage, workspace: string): SavedCommand[] {
  const raw = storage.getItem(storageKey(workspace));
  if (!raw) return [];
  try {
    const values: unknown = JSON.parse(raw);
    if (!Array.isArray(values)) return [];
    return values.filter((v): v is SavedCommand => !!v && typeof v === 'object' &&
      (v.path === '' || /^\/[a-f0-9-]{36}\/fork$/.test(v.path)) && typeof v.key === 'string' &&
      typeof v.createdAt === 'string' && v.body && typeof v.body === 'object' &&
      Object.entries(v.body).every(([k,value]) => ['task_id','configuration'].includes(k) && typeof value === 'string'));
  } catch { return []; }
}
export function saveCommand(storage: CommandStorage, workspace: string, path: string, body: Record<string,string>): SavedCommand {
  const values=savedCommands(storage,workspace);
  const found=values.find(v=>v.path===path && JSON.stringify(v.body)===JSON.stringify(body));
  if (found) return found;
  const command={path,body,key:crypto.randomUUID(),createdAt:new Date().toISOString()};
  // Persist before dispatch. If storage is denied, do not dispatch an unjournaled command.
  storage.setItem(storageKey(workspace),JSON.stringify([...values,command]));
  return command;
}
export function clearCommand(storage: CommandStorage, workspace: string, key: string) {
  storage.setItem(storageKey(workspace),JSON.stringify(savedCommands(storage,workspace).filter(v=>v.key!==key)));
}
export class LatestRead {
  private version=0;
  private controller: AbortController | null=null;
  begin() { this.controller?.abort();this.controller=new AbortController();return {version:++this.version,signal:this.controller.signal}; }
  current(version:number) { return version===this.version && !this.controller?.signal.aborted; }
  stop() { this.controller?.abort();this.version++; }
}
export class InvestigationRequestError extends Error {
  status:number;
  constructor(message:string,status:number) { super(message);this.status=status; }
}
export async function investigationCommand(path:string, options:{body?:unknown;key?:string;signal?:AbortSignal}={}) {
  const response=await fetch('/api/workbench/investigations'+path,{method:options.body===undefined?'GET':'POST',signal:options.signal,
    headers:{'Content-Type':'application/json',...(options.key?{'Idempotency-Key':options.key}:{})},body:options.body===undefined?undefined:JSON.stringify(options.body)});
  const value=await response.json();
  if(!response.ok) throw new InvestigationRequestError(value.detail||value.error||'Investigation request failed.',response.status);
  return value;
}
export const activeInvestigation = (status:string) => ['queued','running'].includes(status);
