import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedHistoryError } from "@/lib/evidence-mode";
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
 if(isRecordedEvidence())return Response.json({error:recordedHistoryError},{status:404,headers:{"Cache-Control":"no-store"}});
 const {id}=await params;
 if(!/^[a-f0-9-]{36}$/.test(id))return Response.json({error:"Report unavailable."},{status:404});
 try {
  const upstream=await fetch(apiBase()+"/api/public/evaluations/"+encodeURIComponent(id),{cache:"no-store",signal:AbortSignal.timeout(8000)});
  return new Response(await upstream.text(),{status:upstream.status,headers:{"Content-Type":"application/json","Cache-Control":"no-store",...(upstream.ok?{"Content-Disposition":`attachment; filename="kairos-evaluation-${id}.json"`}:{})}});
 }catch{return Response.json({error:"Report service unavailable."},{status:502,headers:{"Cache-Control":"no-store"}});}
}
