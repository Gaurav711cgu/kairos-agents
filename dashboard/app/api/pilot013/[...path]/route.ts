import entries from "@/lib/pilot013-downloads.json";
import { repair010Download } from "@/lib/repair010-downloads";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  return repair010Download(entries, path);
}
