import { getIncidents } from "@/lib/kairos-api";
export async function GET() {
  const result = await getIncidents();
  return Response.json(result.data || { error: result.error }, {
    status: result.error ? 503 : 200,
    headers: { "Cache-Control": "no-store" },
  });
}
