import { NextRequest, NextResponse } from "next/server";
import { boundedBody, BodyLimitError } from "@/lib/bounded-body";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedPrivateError } from "@/lib/evidence-mode";
const id = "[a-f0-9-]{36}";
const allowed = new RegExp("^(investigations(?:/cases|/"+id+"(?:/(cancel|fork|publish|replay|progress|bundle|patch))?)?|auth/(me|logout)|runs/"+id+"/proposal|jobs(?:/"+id+"(?:/(cancel|recover|fork|replay|verify))?)?|evaluations(?:/"+id+")?|jobs/"+id+"/blobs/[a-f0-9]{64}|effects(?:/"+id+"/(approve|revoke|dispatch|receipt))?)$");
async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  if(isRecordedEvidence()) return NextResponse.json({error:recordedPrivateError},{status:403,headers:{"Cache-Control":"no-store"}});
  const path=(await context.params).path.join("/");
  if(!allowed.test(path)) return NextResponse.json({error:"Unsupported operation."},{status:404});
  const session=request.cookies.get("kairos_session")?.value;
  if(!session) return NextResponse.json({error:"Sign in to continue."},{status:401});
  if(request.method!=="GET") {
    let valid=false;
    try {const origin=new URL(request.headers.get("origin")||"");valid=origin.host===request.headers.get("host") && origin.protocol===request.nextUrl.protocol && origin.origin===request.headers.get("origin");}catch{/* Invalid origins have no authority. */}
    if(!valid) return NextResponse.json({error:"Request origin rejected."},{status:403});
    if(Number(request.headers.get("content-length")||0)>32768) return NextResponse.json({error:"Request too large."},{status:413});
  }
  try {
    const headers: Record<string,string>={Cookie:"kairos_session="+session,"Content-Type":"application/json"};
    for(const key of ["origin","idempotency-key"]){const value=request.headers.get(key);if(value)headers[key]=value;}
    const body=request.method==="GET"?undefined:await boundedBody(request);
    if(body && new TextEncoder().encode(body).length>32768) return NextResponse.json({error:"Request too large."},{status:413});
    const upstream=await fetch(apiBase()+"/api/"+path+request.nextUrl.search,{method:request.method,headers,body,cache:"no-store",redirect:"manual",signal:AbortSignal.timeout(20000)});
    const download=path.endsWith("/bundle")||path.endsWith("/patch");
    const response=new NextResponse(download ? await upstream.arrayBuffer() : await upstream.text(),{status:upstream.status,headers:{"Content-Type":upstream.headers.get("Content-Type")||"application/json","Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"}});
    if(download && upstream.headers.has("Content-Disposition"))response.headers.set("Content-Disposition",upstream.headers.get("Content-Disposition")!);
    if(path==="auth/logout"){for(const cookie of upstream.headers.getSetCookie())response.headers.append("Set-Cookie",cookie);}
    return response;
  }catch(error){if(error instanceof BodyLimitError)return NextResponse.json({error:"Request too large."},{status:413});return NextResponse.json({error:"Service unavailable. A submitted command may be durable; refresh records before retrying with the same identity."},{status:502});}
}
export const GET=proxy;
export const POST=proxy;
