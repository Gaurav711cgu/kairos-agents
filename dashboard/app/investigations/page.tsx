import { getInvestigations, getFrozenInvestigations } from "@/lib/investigation-readers";
import { InvestigationRows } from "@/components/InvestigationRows";
import Link from "next/link";
import { ServiceError } from "@/components/IncidentRows";
export const dynamic = "force-dynamic";
export default async function Investigations({searchParams}:{searchParams:Promise<{cursor?:string;collection?:string}>}) {
  const query=await searchParams,cursor=query.cursor;
  const result = query.collection==="build003" ? await getFrozenInvestigations() : await getInvestigations(cursor);
  return <div className="page-shell">
    <header className="page-heading"><span className="eyebrow">Real repository cases</span><h1>Every attempt.<br /><em>Open to inspection.</em></h1>
      <p>Historical defects in Kairos, Django, pytest and Requests. Actual local model responses, proposed patches and independent checks.</p>
    </header>
    <p className="investigation-scope">Browse frozen studies and development attempts, including accepted patches, rejected proposals and check results. Source regions were human-selected; these public cases may appear in model training data.</p>
    {!result.data ? <ServiceError message={result.error} /> : <><InvestigationRows records={result.data.investigations} />{result.data.next_cursor && <Link className="button dark" href={"/investigations?cursor="+encodeURIComponent(result.data.next_cursor)}>Earlier attempts</Link>}{cursor && <Link className="text-link" href="/investigations">Latest attempts</Link>}</>}
  </div>;
}
