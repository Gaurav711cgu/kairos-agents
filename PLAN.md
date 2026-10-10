# Kairos build 001 — incident product vertical slice

Date: 2026-10-11. Existing prototype is retained as legacy; its README metrics and sample UI data are not verified evidence.

## Objective
Ship a polished recruiter-facing incident experience backed by real controlled order-support executions persisted in PostgreSQL. Preserve an explicit distinction between deterministic reference policy and an actual language model.

## Authority
Saved specifications: /Users/gauravkumarnayak/Desktop/resume/kairos-plan/BRAIN.md and linked documents. User authorized starting implementation and choosing skills. Skill routing questions are already answered by that context.

## Work split
1. Backend: new kairos_api package, PostgreSQL schema/transaction repository, controlled scenario runner, API, independent grading and tests.
2. Frontend: existing dashboard becomes editorial site with incident inspector, context comparison, controlled fork interaction, engineering/evidence/docs pages; fetch actual API data.
3. Integration: dependency setup, local PostgreSQL, server startup, tests, browser verification, provenance/docs/memory updates.

## API contract
API port 8100; web port 3100. Public read-only routes return sanitized controlled scenario data.
GET /api/health -> {status, database, version}
GET /api/public/incidents -> {incidents: IncidentSummary[]}
GET /api/public/incidents/{id} -> IncidentDetail
POST /api/runs -> authorized controlled execution (not public)
POST /api/runs/{id}/fork -> authorized isolated read-only policy rerun
GET /api/runs/{id} -> authorized tenant-scoped detail
GET /api/public/evidence -> actual measured checks/provenance, no fabricated throughput/statistics

IncidentSummary: id, slug, title, summary, scenario_id, policy, status, created_at, event_count, provenance, parent_run_id, grade_passed.
IncidentDetail extends summary: task, scenario (order_id, order_total_cents, delay_minutes, policy_exception), context_blocks [{id,label,content,source,included}], events [{seq,event_type,title,summary,created_at,payload,event_hash,prev_hash}], decision {refund_cents,reason,evidence_ids}, grade {passed,expected_refund_cents,actual_refund_cents,checks:[{name,passed,detail}]}, duration_ms, configuration {runner,model,policy_version}, lineage {parent_run_id,fork_seq}, integrity {verified,scope}.
Policies: compact (omit exception block), preserve (retain all policy blocks). Scenario_id: late-order-exception (exception prevents refund), late-order-standard (refund permitted), insufficient-evidence (must abstain; nullable decision refund and expected). All data synthetic; execution and grading real deterministic code. runner field prominently labels reference policy. Optional LLM adapter may be added with actual response capture; absent credentials never silently become model evidence.

## Safety/claim constraints
Commit before successful write response. Idempotency key plus request digest; conflicting reuse rejects. Tenant identity from verified developer credential initially; not browser-supplied tenant header. Public mutation disabled. Record exact contexts and parent lineage. Fork is a fresh scenario execution, not arbitrary checkpoint resume; expose this limitation. No external effects or payments. Public data only published sanitized scenarios. Hash chain establishes local consistency only, not administrator-resistant immutability. No synthetic confidence intervals or CI status.

## Acceptance gates
- PostgreSQL stores actual runs/events and survives API restart.
- Duplicate command accepted once; conflicting payload rejected; private tenant reads denied.
- Independent grader detects exception loss; preserve-context rerun passes on controlled scenario.
- Public website renders actual evidence; missing backend has explicit error state.
- Keyboard/mobile inspection and fork flow tested; typecheck/build pass.
- Saved brain/evidence updated with actual commands/results and open gates.

## Design direction
Editorial engineering instrument: paper/ink/forest palette, asymmetric composition, structural typography, incident comparison as memorable anchor. Subjective DFII estimate: impact 4, fit 5, feasibility 4, performance 4, risk 3 = 14. Skill formula range is internally inconsistent, so this is an author estimate, not a measured quality result. Use licensed local display/body font assets if available; no gradient/card-wall template.

## Remaining project gates
This slice does not complete P00 model qualification, P01 managed identity, arbitrary checkpoint replay, external effects, statistical calibration, hosted CI, public deployment, or user adoption.
