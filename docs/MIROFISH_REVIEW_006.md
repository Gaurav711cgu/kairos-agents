# MiroFish review for Kairos

Reviewed 2026-10-13 at commit `7657031ac01184afe2cb220f5ee3545573b5e843`. Repository: https://github.com/666ghj/MiroFish. Read-only clone: `/Users/gauravkumarnayak/Desktop/resume/research/MiroFish`. No dependencies installed or application executed.

MiroFish builds a graph from uploaded material, configures simulated social agents, runs OASIS simulations, generates reports and offers interaction with simulated agents or its report agent. The stack is Vue/Vite/D3 and Flask/Python with CAMEL/OASIS and Zep Cloud. The documented setup requires an OpenAI-compatible LLM API configuration and Zep Cloud key. This is a simulation/report product; its code does not provide repository defect repair, snapshot-bound edits or an independent source-patch verifier.

## Useful ideas

- Show explicit stages and the evidence produced at each stage. Kairos should show original source, model action, validation and independent checks in that order. Its existing readable inspector now includes retained v5 source and source blocks.
- Distinguish system tool results from model prose. The report agent strips model-created tool-result tags before accepting actual tool results. Kairos already has typed, separately captured tool steps and should keep that stronger boundary instead of adopting tag parsing.
- A small evidence graph could link issue, source excerpt, candidate and checks. Derive those edges from captured IDs and hashes; do not introduce a cloud graph or simulated personas to obtain them. Defer this optional visualization until repair follow-up acceptance completes.
- Keep reports connected to inspectable captures. The follow-up page and downloads should describe the source-context defect, fixed protocol and new outcomes without rewriting the frozen 0/36 comparison.

## Decisions

Retain Kairos PostgreSQL receipts, leases and fencing. MiroFish task bookkeeping includes an in-memory task dictionary; importing that would discard properties already tested in Kairos. Retain local pinned inference and registered verification, preserving zero API spend. Thousands of simulated agents and cloud memory do not address the observed missing-source/disabled-patch defect and would add untested cost and complexity.

The repository declares AGPL-3.0. No source code, prompts, assets or branding have been copied. The adopted elements are workflow ideas implemented within Kairos's existing design. This review does not establish simulation prediction accuracy or imply a code-repair benchmark result for MiroFish.

Relevant inspected files: `backend/app/services/report_agent.py`, `backend/app/models/task.py`, `backend/app/config.py`, `frontend/src/components/Step3Simulation.vue`, `frontend/src/components/GraphPanel.vue`, and `backend/app/utils/zep_lifecycle.py`.
