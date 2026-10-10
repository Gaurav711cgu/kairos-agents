import { NextRequest, NextResponse } from "next/server";
import { apiBase } from "@/lib/kairos-api";
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
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
    body = await request.json();
  } catch {
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
          Authorization: "Bearer " + process.env.KAIROS_DEV_TOKEN,
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
