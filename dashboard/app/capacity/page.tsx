import Link from 'next/link';
import capacity from '@/lib/capacity004.json';
type Stage = typeof capacity.stages[number];
type QuietRun = {complete:boolean;target_met:boolean;host_policy:string;limits:string;stages:Stage[]};
const quiet = (capacity as typeof capacity & {quiet_repeat?:QuietRun}).quiet_repeat;
export const metadata={title:'Measured local capacity'};
function Stages({stages}:{stages:Stage[]}){return <div className="capacity-stages">{stages.map(stage=><article key={stage.label}>
  <span className="eyebrow">{stage.seconds>1000?'30-minute soak':'Three-minute load'} / {stage.clients} clients</span>
  <h3>{stage.target_met?'Passed targets':'Failed acceptance'}</h3>
  <dl><div><dt>Requests</dt><dd>{stage.requests.toLocaleString('en-US')}</dd></div>
    <div><dt>Acknowledgement p95</dt><dd>{stage.ack_p95_ms.toFixed(1)} ms</dd></div>
    <div><dt>Summary read p95</dt><dd>{stage.read_p95_ms.toFixed(1)} ms</dd></div>
    <div><dt>Unexpected errors</dt><dd>{stage.unexpected_errors.toLocaleString('en-US')}</dd></div>
    <div><dt>Unplanned quota rejections</dt><dd>{stage.observed_quota_rejections.toLocaleString('en-US')}</dd></div>
    <div><dt>All non-success responses</dt><dd>{(stage.non_success_rate*100).toFixed(2)}%</dd></div></dl>
</article>)}</div>;}
export default function Capacity(){return <div className="page-shell reading-page">
  <header className="page-heading"><span className="eyebrow">Build 004 / Measured control plane</span>
    <h1>{quiet?.complete && quiet.target_met ? quiet.stages.reduce((total,stage)=>total+stage.requests,0).toLocaleString('en-US')+' requests.' : 'Measured local capacity.'}<br/><em>{quiet?.complete && quiet.target_met ? 'A complete 42-minute test.' : 'Inspect every load stage.'}</em></h1>
    <p>Actual HTTP and PostgreSQL on an 8 GB Mac. Inspect latency, errors and recovery across the successful repeat and initial failed run.</p></header>
  <section className="prose"><h2>What was measured</h2>
    <p>Durable command receipts, retries, progress reads, listing and cancellation. Fixture identity and tasks isolate control-plane work. Inference and identity-provider throughput are separate.</p>
    <p>Targets: p95 below 750 ms and fewer than 1% non-success responses. Quota rejections were not planned in this workload and count toward failures.</p></section>
  {quiet?.complete && <section aria-label="Quiet capacity repeat"><div className="prose"><h2>Complete quiet repeat</h2><p>{quiet.host_policy}</p><p>{quiet.target_met?'All four three-minute stages and the 30-minute ten-client soak met the declared targets.':'The complete repeat missed at least one declared target. Inspect each stage below.'}</p><p>{quiet.limits}</p></div><Stages stages={quiet.stages}/></section>}
  <section aria-label="Original capacity run"><div className="prose"><h2>Original pooled run</h2><p>The four three-minute stages passed. The ten-client soak failed during a service restart. These results remain preserved alongside the quiet repeat.</p></div><Stages stages={capacity.stages}/></section>
  <section className="prose"><h2>Read latency alongside errors</h2>
    <p>{capacity.latency_scope}</p><p>{capacity.interference}</p>
    <h2>One optimization, with its limits</h2><p>{capacity.bounded_optimization}</p>
    <p>The quiet repeat retains uncertain command identities, confirms cancellation before moving on, and streams raw request rows. It uses the same bounded eight-connection pool. Its result does not erase the original outage.</p>
    <p>Database logs establish a restart. Its cause remains unproven. An interrupted model call stayed unknown and was never sent again.</p>
    <p>The original harness labeled every quota rejection expected. The ten-client soak did not plan quota pressure. The corrected report counts those rejections as unplanned failures.</p>
    <a className="button dark" href="/capacity/results.json" download>Download measurements</a>
    <p><Link className="text-link" href="/engineering">Inspect the request and recovery design</Link></p></section>
</div>;}
