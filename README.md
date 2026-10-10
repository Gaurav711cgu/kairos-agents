# Kairos for Agents

A production-grade, verifiable Agent Harness and Time-Travel Debugging Platform that records every internal agent decision, context mutation, and tool interaction into an immutable event log. Replay runs strictly, fork from step k with modified prompts or tools, and statistically test regressions using paired bootstrap confidence intervals.

---

## The One-Liner

**"Prompt change broke your agent? See the exact step it diverged and whether it is a real regression or sampling noise."**

---

## Core Guarantees & Non-Guarantees

| Feature | Guarantees | Non-Guarantees |
| :--- | :--- | :--- |
| **Strict Replay** | Bit-for-bit identical tool outputs served from cache; exact prompt reconstruction; pinpointing of first divergence step. | Does not guarantee external LLM token identicality if temperature > 0 and seed is unset. |
| **Fork at Step k** | Re-executes from step k forward with patched code/prompt; prior steps 0..k-1 remain immutable. | Write tools in forked runs are strictly stubbed or dry-run unless user provides write authorization. |
| **Durable Loop** | `kill -9` recovery from the last checkpointed step without duplicate side effects via idempotency tokens. | In-flight tool calls without external idempotency support cannot guarantee once-only external effect. |
| **Statistical Gate** | Paired bootstrap 95% Confidence Interval with Holm-Bonferroni multi-testing correction. | Does not eliminate the need for domain-specific benchmark test sets. |

---

## Architecture Overview

```
Agent Harness (Python 3.12)
  - Loop Controller (Budgets, Step Limits, Checkpointer)
  - Context Manager (Hierarchical Assembly, Compaction Audit)
  - Tool Execution Layer (Typed Pydantic Schemas, Idempotency Keys)
  - Deterministic Invariant Verifier (Exact SQL / Schema checks)
           |
           v (Structured JSON Events)
Go Ingest API (Hot Path, Go 1.22+)
  - Bounded Lock-Free Ring Buffer (Drop monitoring, backpressure)
  - Atomic Transaction: Step Row + Idempotency Dedupe + Transactional Outbox
           |
           +---> PostgreSQL / SQLite (Runs, Steps, Outbox)
           +---> S3 / MinIO (Content-Addressed Context Blobs)
           |
Replay, Fork & Statistical Evaluation Engine (Python 3.12)
  - Strict Replay by Request Fingerprint
  - Divergence Detector (Pinpoints exact step of departure)
  - Forking Engine (Resume from step k with live patched prompt)
  - Paired Bootstrap Hypothesis Testing (N=10,000) & Holm-Bonferroni Correction
           |
Next.js 15 App Router Dashboard (TypeScript & Tailwind CSS)
  - Interactive Timeline Scrubber with Event Cryptographic Chain
  - Context-Decision Inspector & Ground-Truth Diff Viewer
  - Step-k Time-Travel Fork Modal with Parameter Patch Injection
  - Empirical Paired Bootstrap Resampling Distribution Chart
```

---

## Quickstart

### 1. Requirements
- Python 3.11+
- Go 1.22+
- Node.js 20+

### 2. Setup Python Harness & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Verification Tests
```bash
# Run Python harness, replay, and statistical tests
pytest tests/ -v

# Run Go ingest tests with race detector
cd ingest && go test -v -race ./...
```

### 4. Run Benchmark & Ablation Study
```bash
python scripts/run_benchmarks.py
```

### 5. Launch Next.js Dashboard
```bash
cd dashboard
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to inspect execution traces and statistical regression distributions.

---

## Verified Test Suite & Benchmark Results

```
tests/test_harness.py::test_agent_harness_text_to_sql_execution PASSED
tests/test_harness.py::test_context_compaction_audit PASSED
tests/test_harness.py::test_kill_and_resume_checkpointing PASSED
tests/test_replay_divergence.py::test_strict_replay_exact_match PASSED
tests/test_replay_divergence.py::test_divergence_detection_when_model_changes PASSED
tests/test_replay_divergence.py::test_fork_at_step PASSED
tests/test_statistical_gate.py::test_paired_bootstrap_detects_genuine_regression PASSED
tests/test_statistical_gate.py::test_paired_bootstrap_detects_no_significant_difference PASSED
tests/test_statistical_gate.py::test_holm_bonferroni_correction PASSED
tests/test_statistical_gate.py::test_harness_ablation_study PASSED
tests/test_ingest_contracts.py::test_end_to_end_ingest_contract PASSED

ingest/ringbuffer.go: TestRingBufferCapacityAndDrop PASS
ingest/storage.go: TestBatchIngestAndIdempotency PASS

Benchmark Results (N=15 evaluations per arm, 10,000 bootstrap resamples):
- Baseline Success Rate: 100.0%
- No-Verifier Arm Success Rate: 60.0%
- Empirical Delta Mean: -0.4000
- 95% Bootstrap CI: [-0.6667, -0.1333]
- Empirical p-value: 0.0012
- CI Regression Gate: Confirmed Regression (CI Upper < 0)
```
