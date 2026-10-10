# Kairos Dashboard

Interactive inspection, replay, and statistical verification interface for autonomous agent execution traces.

## Core Capabilities

1. **Timeline Scrubber**: Real-time scrubbing across sequential agent execution steps ($k = 0, \dots, N$), with cryptographic hash display and instant divergence warnings.
2. **Context-Decision Diff Inspector**: Side-by-side comparison of "What the Model Saw" (hierarchical prompt, schemas, token budget meter) versus "What the Model Decided & Committed" (tool parameters, SHA-256 idempotency key, deterministic verifier invariant results).
3. **Time-Travel Fork Panel**: Ability to branch execution from any historical step $k$, patch action parameters or prompt constraints, and re-execute live without re-running earlier steps.
4. **Paired Bootstrap Regression Visualizer**: Visual density distribution of resampled performance deltas ($N=10,000$ iterations) and Multi-Task Holm-Bonferroni Family-Wise Error Rate control table.
5. **Go Ingest Telemetry**: Real-time indicators of bounded ring buffer capacity, zero-drop backpressure, transactional outbox status, and content-addressed blob deduplication ratio (3.42x).

## Getting Started

Run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

To generate a static production build:

```bash
npm run build
```
