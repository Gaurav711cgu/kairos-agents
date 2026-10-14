import { NextRequest, NextResponse } from "next/server";
import { boundedBody, BodyLimitError } from "@/lib/bounded-body";
import { apiBase } from "@/lib/kairos-api";
import { isRecordedEvidence, recordedPrivateError } from "@/lib/evidence-mode";
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  if (isRecordedEvidence()) return NextResponse.json({ error: recordedPrivateError }, { status: 403, headers: { "Cache-Control": "no-store" } });
  const origin = request.headers.get("origin");
  const requestHost = request.headers.get("host");
  const allowedHosts = new Set(["localhost", "127.0.0.1", "[::1]"]);
  let sameLocalOrigin = false;
  try {
    const originUrl = new URL(origin || "");
    // Next may normalize nextUrl to localhost. The actual Host header preserves
    // the browser address; compare it exactly and independently restrict loopback.
    sameLocalOrigin =
      allowedHosts.has(originUrl.hostname) &&
      originUrl.host === requestHost &&
      originUrl.protocol === request.nextUrl.protocol &&
      originUrl.origin === origin;
  } catch {
    /* Invalid origins have no authority. */
  }
  if (
    process.env.NODE_ENV !== "development" ||
    process.env.KAIROS_ENABLE_LOCAL_MUTATIONS !== "true" ||
    !process.env.KAIROS_DEV_TOKEN ||
    !sameLocalOrigin
  )
    return NextResponse.json(
      {
        error:
          "Controlled mutations are available only in explicitly enabled local developer mode.",
      },
      { status: 403 },
    );
  const key = request.headers.get("idempotency-key");
  if (!key || !/^[a-zA-Z0-9-]{16,80}$/.test(key))
    return NextResponse.json(
      { error: "A valid command identity is required." },
      { status: 400 },
    );
  let body: unknown;
  try {
    body = JSON.parse(await boundedBody(request));
  } catch (error) {
    if (error instanceof BodyLimitError) return NextResponse.json({error:"Request too large."},{status:413});
    return NextResponse.json(
      { error: "Invalid request body." },
      { status: 400 },
    );
  }
  if (
    !body ||
    typeof body !== "object" ||
    !("policy" in body) ||
    body.policy !== "preserve"
  )
    return NextResponse.json(
      { error: "Only a preserve-context policy rerun is supported." },
      { status: 400 },
    );
  const { id } = await params;
  try {
    const response = await fetch(
      apiBase() + "/api/runs/" + encodeURIComponent(id) + "/fork",
      {
        method: "POST",
        headers: {
          ...(request.cookies.get("kairos_session")?.value
            ? { Cookie: "kairos_session=" + request.cookies.get("kairos_session")!.value, Origin: request.headers.get("origin")! }
            : { Authorization: "Bearer " + process.env.KAIROS_DEV_TOKEN }),
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify({ policy: "preserve" }),
        signal: AbortSignal.timeout(15000),
      },
    );
    if (!response.ok)
      return NextResponse.json(
        {
          error:
            "The execution service rejected the request (HTTP " +
            response.status +
            ").",
        },
        { status: response.status },
      );
    const result = await response.json();
    return NextResponse.json({ id: result.id });
  } catch {
    return NextResponse.json(
      {
        error:
          "The execution outcome is unconfirmed. Inspect incident records before retrying.",
      },
      { status: 502 },
    );
  }
}
