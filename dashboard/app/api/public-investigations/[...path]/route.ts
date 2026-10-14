import { NextRequest, NextResponse } from "next/server";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence } from "@/lib/evidence-mode";
import { downloadRecordedInvestigation, recordedFailure } from "@/lib/recorded-evidence";
export async function GET(_request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  if (!/^[a-f0-9-]{36}\/(bundle|patch)$/.test(path)) return NextResponse.json({ error: "Unsupported download." }, { status: 404 });
  if (isRecordedEvidence()) {
    const [id, kind] = path.split("/");
    try {
      const download = await downloadRecordedInvestigation(id, kind as "bundle" | "patch");
      return new NextResponse(new Uint8Array(download.bytes), { headers: { "Content-Type": download.contentType, "Content-Disposition": `attachment; filename="${download.filename}"`, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
    } catch (error) { const failure = recordedFailure(error); return NextResponse.json({ error: failure.message }, { status: failure.status, headers: { "Cache-Control": "no-store" } }); }
  }
  try {
    const response = await fetch(apiBase() + "/api/public/investigations/" + path, { cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(10000) });
    const headers = new Headers({ "Content-Type": response.headers.get("content-type") || "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    const disposition = response.headers.get("content-disposition");
    if (disposition) headers.set("Content-Disposition", disposition);
    return new NextResponse(await response.arrayBuffer(), { status: response.status, headers });
  } catch { return NextResponse.json({ error: "Evidence download unavailable." }, { status: 502 }); }
}
