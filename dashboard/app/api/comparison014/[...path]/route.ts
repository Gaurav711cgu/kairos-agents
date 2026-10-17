import entries from "@/lib/comparison014-downloads.json";
import { comparisonDownload } from "@/lib/comparison014-downloads";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return comparisonDownload(entries, (await context.params).path);
}
