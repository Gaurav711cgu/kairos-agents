import entries from "@/lib/training014-downloads.json";
import { repair010Download } from "@/lib/repair010-downloads";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return repair010Download(entries, (await context.params).path);
}
