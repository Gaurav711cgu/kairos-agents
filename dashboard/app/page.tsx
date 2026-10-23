import { CurrentResult } from "@/components/CurrentResult";
import currentCohort from "@/lib/study007-cohort.json";
import Link from "next/link";
import { activeStudyComplete, outcomeLabel, caseTitle, configurationLabel } from "@/lib/investigations";
import { getInvestigation, getActiveComparison, getFrozenInvestigations } from "@/lib/investigation-readers";
import { InvestigationRows } from "@/components/InvestigationRows";
import { ServiceError } from "@/components/IncidentRows";
import followup from "@/lib/followup006-cohort.json";
export const dynamic = "force-dynamic";
export default async function Home() {
  const result = await getActiveComparison();
  const records = result.data?.investigations ?? [];
  const latest = records;
  const prior = latest.some(item=>item.outcome==="verified_repair") ? null : await getFrozenInvestigations();
  const featured = latest.find(item=>item.outcome==="verified_repair") ?? prior?.data?.investigations.find(item=>item.outcome==="verified_repair") ?? latest.find(item=>item.configuration.startsWith("loop-")) ?? records[0];
  const featuredId = currentCohort.featured_id ?? (followup.complete && followup.featured_id ? followup.featured_id : featured?.id);
  const detail = featuredId ? await getInvestigation(featuredId) : null;
  const record = detail?.data;
  const patch = [...(record?.steps ?? [])].reverse().find(item=>item.name==="propose_patch" && item.result && !item.result.body.error);
  const patchText = patch?.result?.body.patch ?? patch?.request.body.patch;
  const rejection = [...(record?.steps ?? [])].reverse().find(item=>item.name==="propose_patch" && item.result?.body.error)?.result?.body.error;
  const cases = new Set(latest.map(item=>item.task_id)).size;
  const repaired = latest.filter(item=>item.outcome==="verified_repair").length;
  return <>
    <div className="site-meta"><span>Real repository investigations</span><span>{result.error ? "Records unavailable" : `${records.length} recorded attempts`}</span></div>
    <CurrentResult home />
    <div className="investigation-actions"><Link className="text-link" href="/how-it-works">Follow your first investigation</Link><Link className="text-link" href="/repair-comparison">Inspect the 57-attempt repair comparison</Link><Link className="text-link" href="/advancement">Read the frozen local-model study</Link><Link className="text-link" href="/repair-workflow">Read the repair workflow follow-up</Link><Link className="text-link" href="/repair-investigation">Inspect the completed repair investigation</Link></div>
    <section className="hero investigation-hero">
      <div className="hero-copy"><span className="eyebrow opening-label">Kairos / Repository investigation</span>
        <h1>Follow a defect.<br /><em>Inspect its repair.</em></h1>
        <p className="hero-deck">An agent proposes a source change.<br />Independent checks decide whether it works.</p>
        <p className="hero-description">A full-stack workbench that captures source context, model actions and independent checks. Review the proposed change, follow its execution and download the evidence.</p>
        <div className="hero-actions"><Link className="button primary" href={featuredId ? "/investigations/"+featuredId : "/investigations"}>Inspect an investigation</Link><Link className="button dark" href="/investigations">All attempts</Link><Link className="text-link" href="/engineering">Engineering decisions</Link></div>
        <p className="hero-footnote">Explore a completed investigation here, or <Link href="/workbench">set up the authenticated workbench</Link> to submit a new registered case.</p>
      </div>
      <div className="hero-instrument case-dossier">{record ? <>
        <div className="dossier-top"><span className="eyebrow">Published case file{record.task_snapshot.split==="development" ? " · Development demonstration" : record.configuration.endsWith("v3") ? " · Original study" : ""}</span><span>{configurationLabel(record.configuration)}</span></div>
        <h2>{caseTitle(record.task_id, record.task_snapshot.title)}</h2><p className="dossier-source">{record.task_snapshot.repository} · {record.task_snapshot.revision.slice(0,12)}</p>
        {record.task_id === "django__django-11066" && <p className="dossier-source">Development case with an issue-provided repair hint. Independent checks verify the submitted patch.</p>}<div className="dossier-result"><span className="eyebrow">Observed result</span><h3 className={record.outcome==="verified_repair" ? "result-pass" : ""}>{outcomeLabel(record.outcome,record.status)}</h3><p>{record.model_calls} model {record.model_calls === 1 ? "call" : "calls"} · {record.patch_count} patch {record.patch_count === 1 ? "proposal" : "proposals"} · {record.check_count} check {record.check_count === 1 ? "run" : "runs"}</p></div>
        {typeof patchText==="string" ? <pre role="region" className="dossier-patch" tabIndex={0} aria-label="Proposed patch excerpt">{patchText.split("\n").filter(line => /^[+@-]/.test(line)).slice(0,10).join("\n")}</pre> : <div className="dossier-note"><span className="eyebrow">What the record contains</span><p>{typeof rejection==="string" ? rejection : record.summary || "Captured requests and responses, with the stop reason preserved."}</p></div>}
        <Link className="dossier-open" href={"/investigations/"+record.id}>Open source, context and checks<span aria-hidden="true">↗</span></Link>
      </> : <ServiceError message={detail?.error ?? result.error ?? "No real investigation has been published yet."} />}</div>
    </section>
    <section className="section"><div className="section-heading"><div><span className="eyebrow">How to review a result</span><h2>Start with the failure.<br /><em>Follow the evidence.</em></h2></div><p>A repair must fix the reproduced regression and pass the relevant existing tests.</p></div>
      <div className="architecture-notes"><article><span className="note-number">01</span><h3>Inspect the source</h3><p>Each case identifies the issue, pinned revision and reproduction command. A baseline failure and passing reference repair establish the case before the agent runs.</p></article><article><span className="note-number">02</span><h3>Read the proposed change</h3><p>The model supplies exact source replacements. Kairos constructs the diff and rejects changes outside approved source paths. Every rejected proposal remains inspectable.</p></article><article><span className="note-number">03</span><h3>Check the result</h3><p>Checks run in a separate disposable environment without network access. Registered regression and existing tests determine the repair verdict.</p></article></div>
    </section>
    <section className="section"><div className="section-heading"><div><span className="eyebrow">Frozen local-model comparison</span><h2>Compare the recorded outcomes.</h2></div><p>Open an attempt to compare the frozen strategies on the same source. Earlier development attempts remain in the full record.</p></div><dl className="home-investigation-metrics"><div><dt>Cases in frozen local-model study</dt><dd>{result.error ? "—" : cases}</dd></div><div><dt>Frozen local-model study repairs</dt><dd>{result.error ? "—" : repaired}<small>{result.error ? " unavailable" : " / " + latest.length + " attempts"}</small></dd></div><div><dt>API spend</dt><dd>$0<small> local inference</small></dd></div></dl>
        <p className="hero-footnote">{currentCohort.complete ? "Five fresh Python cases across Django and pytest in the frozen local-model study. Two frozen strategies; neither verified a repair. " : followup.complete ? "Five fresh follow-up cases across Django, pytest and Requests. Two frozen strategies after a source-context defect was fixed. " : activeStudyComplete ? "Twelve evaluation cases across Django, pytest and Requests. Three frozen strategies. " : "Original six-case study. "}Benchmark-assisted source entry files. Small historical sample; no general performance claim. {followup.complete && <Link href="/follow-up">Read the follow-up and preserved 0/36 study.</Link>}</p>{result.error ? <ServiceError message={result.error}/> : <InvestigationRows records={latest.filter(item=>item.configuration.startsWith("loop-"))} />}<div className="investigation-actions"><Link className="text-link" href="/investigations">View the complete attempt ledger</Link></div></section>
    <section className="section" id="guarantees"><div className="section-heading"><div><span className="eyebrow">Engineering boundaries</span><h2>Claims you can inspect.</h2></div><p>Inspect the tested request path, worker recovery, source isolation and evaluation scope.</p></div>
      <dl className="investigation-boundaries"><div><dt>Saved before acceptance</dt><dd>PostgreSQL commits the request identity before the API returns 202. Reusing the identity with a different command returns a conflict.</dd></div><div><dt>Uncertain calls stay uncertain</dt><dd>Dispatch intent is saved before inference. A crash without a captured response never triggers a silent retry.</dd></div><div><dt>Changes remain isolated</dt><dd>Tools operate on immutable source snapshots and disposable copies. Downloads contain proposed patches; they do not alter your working repository.</dd></div><div><dt>Evaluation has limits</dt><dd>The active comparison covers {currentCohort.complete ? "five locked Python cases" : followup.complete ? "five locked follow-up cases" : activeStudyComplete ? "twelve locked evaluation cases" : "six historical cases"} with human-selected source entry points. Public issues may have appeared in training data. The comparison is descriptive.</dd></div></dl>
      <div className="investigation-actions"><Link className="text-link" href="/engineering">Read the architecture</Link><Link className="text-link" href="/history">Earlier system demonstrations</Link></div>
    </section>
  </>;
}
