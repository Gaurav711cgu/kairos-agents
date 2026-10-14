import currentCohort from "./study007-cohort.json";
import currentResults from "./study007-results.json";
import cohort from "./investigation-cohort.json";
import studyCohort from "./study004-cohort.json";
import followupCohort from "./followup006-cohort.json";
import followupResults from "./followup006-results.json";
import { z } from "zod";
import { apiBase, type ApiResult } from "./kairos-api";
import { investigationSummary, investigationSchema, type Investigation } from "./investigation-contract";
import { isFrozenComparison } from "./investigations";
import { isRecordedEvidence } from "./evidence-mode";
import { getRecordedInvestigation, listRecordedInvestigations } from "./recorded-evidence";

const get = async <T>(path: string, schema: z.ZodType<T>): Promise<ApiResult<T>> => {
  try {
    const response = await fetch(apiBase() + path, { cache: "no-store", signal: AbortSignal.timeout(10000) });
    if (!response.ok) return { data: null, error: `Investigation service returned HTTP ${response.status}.` };
    const result = schema.safeParse(await response.json());
    if (!result.success) return { data: null, error: "Unsupported investigation record. No unverified data is shown." };
    return { data: result.data, error: null };
  } catch { return { data: null, error: "Investigation service unavailable. Start the API and refresh to inspect its database records." }; }
};
const getLiveInvestigations = (cursor?: string) => get("/api/public/investigations" + (cursor ? "?cursor=" + encodeURIComponent(cursor) : ""), z.object({ investigations: z.array(investigationSummary), next_cursor: z.string().nullable() }));
export async function getFrozenInvestigations() {
  const values=await readComparisonRecords(cohort.ids);
  if(values.some(value=>!value.data))return {data:null,error:"The frozen comparison is unavailable. No partial results shown."};
  return {data:{investigations:values.map(value=>investigationSummary.parse({...value.data!,title:value.data!.task_snapshot.title})),next_cursor:null},error:null};
}
export async function getInvestigation(id: string): Promise<ApiResult<Investigation>> {
  return isRecordedEvidence() ? getRecordedInvestigation(id) : get("/api/public/investigations/" + encodeURIComponent(id), investigationSchema);
}
export async function getInvestigations(cursor?: string) {
  return isRecordedEvidence() ? listRecordedInvestigations(cursor) : getLiveInvestigations(cursor);
}
async function readComparisonRecords(ids: string[]) {
  const values: ApiResult<Investigation>[] = new Array(ids.length);
  let next = 0;
  await Promise.all(Array.from({length: Math.min(4, ids.length)}, async () => {
    while (next < ids.length) {
      const index = next++;
      values[index] = await getInvestigation(ids[index]);
    }
  }));
  return values;
}

export async function getActiveComparison(){
  if(currentCohort.complete){
    const values=await readComparisonRecords(currentCohort.ids);
    if(values.some(value=>!value.data))return {data:null,error:"The build007 comparison is unavailable. No partial comparison shown."};
    return {data:{investigations:values.map(value=>investigationSummary.parse({...value.data!,title:value.data!.task_snapshot.title})),next_cursor:null},error:null};
  }
  if(followupCohort.complete){
    const values=await readComparisonRecords(followupCohort.ids);
    if(values.some(value=>!value.data))return {data:null,error:"The follow-up comparison is unavailable. No partial comparison shown."};
    return {data:{investigations:values.map(value=>investigationSummary.parse({...value.data!,title:value.data!.task_snapshot.title})),next_cursor:null},error:null};
  }
  if(!studyCohort.complete)return getFrozenInvestigations();
  const values=await readComparisonRecords(studyCohort.ids);
  if(values.some(value=>!value.data))return {data:null,error:"The frozen study is unavailable. No partial comparison shown."};
  return {data:{investigations:values.map(value=>investigationSummary.parse({...value.data!,title:value.data!.task_snapshot.title})),next_cursor:null},error:null};
}
export async function getComparisonPeers(record:Investigation){
  const current=currentResults.attempts.find(value=>value.id===record.id);
  if(current){
    const peers=currentResults.attempts.filter(value=>value.cohort===current.cohort && value.task_id===record.task_id && value.id!==record.id);
    const values=await readComparisonRecords(peers.map(value=>value.id));
    return values.flatMap(value=>value.data && value.data.task_digest===record.task_digest && value.data.config_snapshot.model_manifest_digest===record.config_snapshot.model_manifest_digest && value.data.configuration!==record.configuration?[value.data]:[]);
  }
  const followup=(followupCohort.ids as string[]).includes(record.id);
  const development=followupResults.attempts.filter(value=>value.split==='development');
  const isDevelopment=development.some(value=>value.id===record.id);
  const ids=isDevelopment?development.map(value=>value.id):followup?followupCohort.ids:isFrozenComparison(record)?cohort.ids:(studyCohort.ids as string[]).includes(record.id)?studyCohort.ids:[];
  const tasks: Record<string,string> = isDevelopment?Object.fromEntries(development.map(value=>[value.id,value.task_id])):followup?followupCohort.task_by_id:isFrozenComparison(record) ? cohort.task_by_id : studyCohort.task_by_id;
  const values=await readComparisonRecords(ids.filter(id=>id!==record.id && tasks[id]===record.task_id));
  return values.flatMap(value=>value.data && value.data.task_id===record.task_id && value.data.task_digest===record.task_digest && value.data.config_snapshot.model_manifest_digest===record.config_snapshot.model_manifest_digest && value.data.configuration!==record.configuration && value.data.configuration.slice(-2)===record.configuration.slice(-2)?[value.data]:[]);
}
