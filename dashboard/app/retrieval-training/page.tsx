import Link from "next/link";
import evidence from "@/lib/training014-summary.json";

export const metadata = { title: "Retrieval training and held-out results" };
const percent = (n: number) => `${(100 * n).toFixed(2)}%`;

export default function RetrievalTraining() {
  const { base, adapter } = evidence.summary;
  const interval = evidence.uncertainty.delta_intervals.mrr;
  return <div className="page-shell reading-page">
    <header className="page-heading">
      <span className="eyebrow">Retrieval / Measured training</span>
      <h1>Train a smaller head.<br /><em>Measure what changed.</em></h1>
      <p>A frozen code encoder, 24,576 learned parameters and 113 held-out functions. Inspect the data, checkpoint selection and measured results.</p>
    </header>
    <div className="article-layout">
      <aside className="article-index"><span className="eyebrow">Inspect the experiment</span>
        <a href="#task">The retrieval task</a><a href="#training">Training and selection</a>
        <a href="#results">Held-out comparison</a><a href="#reproduce">Reproduce the result</a>
      </aside>
      <article className="prose">
        <section id="task"><h2>Find a function from its maintained description.</h2>
          <p>Each query comes from a maintained function docstring. The matching code has its own docstring removed. All candidates come from the same repository and split.</p>
          <ol><li>Freeze licensed source revisions and capture original bytes.</li><li>Remove exact and near duplicates before splitting.</li><li>Encode descriptions and source using pinned CodeRankEmbed.</li><li>Train a shared residual projection. Rank candidates by cosine similarity.</li><li>Evaluate once after development selection is frozen.</li></ol>
          <dl className="context-budget"><div><dt>Train · Jinja</dt><dd>{evidence.train}</dd></div><div><dt>Development · Flask</dt><dd>{evidence.development}</dd></div><div><dt>Held out · Click</dt><dd>{evidence.heldout}</dd></div></dl>
          <p>All three repositories use BSD-3-Clause licenses. Frozen source, attribution and deduplication receipts accompany the experiment. Other functions are unjudged contrastive candidates; some may also be relevant.</p>
        </section>
        <section id="training"><h2>Choose using development evidence.</h2>
          <p>The 137-million-parameter encoder stays frozen. A rank-16 projection learns 24,576 parameters over 200 optimizer steps. CPU training uses two threads.</p>
          <p>An initial profile and two development revisions were recorded before held-out evaluation. The selected profile uses eight hard contrastive candidates and a learning rate of 0.0003. Development MRR selected step {evidence.selected_step}; the held-out repository never entered training or selection.</p>
          <p>A real interruption after step 37 resumed for 163 steps. Optimizer, random generator, sampler and model state matched uninterrupted training bit for bit.</p>
          <a className="text-link" href="/api/training014/receipt.json" download>Download checkpoint-resume receipt</a>
        </section>
        <section id="results"><h2>A small gain, with uncertainty visible.</h2>
          <div className="pair-table-scroll" role="region" aria-label="Held-out retrieval results"><table className="pair-table" style={{ minWidth: 0 }}>
            <caption>113 Click functions · 113 candidates per query</caption>
            <thead><tr><th scope="col">Metric</th><th scope="col">Frozen encoder</th><th scope="col">Trained head</th></tr></thead>
            <tbody><tr><th scope="row">Mean reciprocal rank</th><td>{base.mrr.toFixed(4)}</td><td>{adapter.mrr.toFixed(4)}</td></tr>
              <tr><th scope="row">Recall at 1</th><td>{percent(base["recall@1"])}</td><td>{percent(adapter["recall@1"])}</td></tr>
              <tr><th scope="row">Recall at 5</th><td>{percent(base["recall@5"])}</td><td>{percent(adapter["recall@5"])}</td></tr>
              <tr><th scope="row">Recall at 10</th><td>{percent(base["recall@10"])}</td><td>{percent(adapter["recall@10"])}</td></tr></tbody>
          </table></div>
          <p>MRR improved for {evidence.changes.improved} queries, regressed for {evidence.changes.regressed}, and stayed unchanged for {evidence.changes.unchanged}. The paired 95% bootstrap interval for MRR difference is [{interval.lower.toFixed(4)}, {interval.upper.toFixed(4)}]. It includes zero.</p>
          <p>This measures function matching within one held-out repository. Related functions, one repository per split and unknown pretraining exposure limit generalization. The result does not establish better repairs or broad retrieval superiority.</p>
          <a className="text-link" href="/api/training014/bundle.json" download>Download all paired held-out outcomes</a>
        </section>
        <section id="reproduce"><h2>Inspect the artifact, then reproduce training.</h2>
          <p>The exported head contains projection weights and bound encoder identity. Frozen embedding caches permit CPU reproduction without downloading base model weights. No inference or training starts when this page opens.</p>
          <div className="investigation-actions"><a href="/api/training014/adapter.json" download>Download trained head</a><a href="/api/training014/retrieval.json" download>Download experiment manifest</a></div>
          <p>See the repository training instructions for source validation, exact cache hashes and the recorded 200-step command. The trained head transforms query and code embeddings together; the base code encoder remains frozen.</p>
          <Link className="text-link" href="/repair-investigation">Inspect a model-generated repair</Link>
        </section>
      </article>
    </div>
  </div>;
}
