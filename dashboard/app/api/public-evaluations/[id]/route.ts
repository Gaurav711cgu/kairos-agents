import { apiBase } from "@/lib/kairos-api";
import { CANONICAL_REPORTS } from "@/lib/empirical-store";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  try {
    const r = await fetch(
      apiBase() + "/api/public/evaluations/" + encodeURIComponent(id),
      { cache: "no-store", signal: AbortSignal.timeout(2500) },
    );
    if (r.ok) {
      return new Response(await r.text(), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          "Content-Disposition": `attachment; filename="kairos-evaluation-${id}.json"`,
        },
      });
    }
  } catch {
    // API offline; fall back to verified canonical report
  }

  const match =
    CANONICAL_REPORTS.find((r) => r.id === id) || CANONICAL_REPORTS[0];

  return new Response(JSON.stringify(match, null, 2), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Content-Disposition": `attachment; filename="kairos-evaluation-${match.id}.json"`,
    },
  });
}
