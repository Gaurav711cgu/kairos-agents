# Documentation index

Files keep their original paths because evidence receipts reference them. This index groups them by purpose.
Numeric suffixes (`_004`, `_014`, `_025`) name the build or study a document belongs to.

## Start here

| Document | Read it for |
| --- | --- |
| [`../README.md`](../README.md) | What Kairos does, results and how to run it |
| [`RESUME_CLAIMS.md`](RESUME_CLAIMS.md) | Claims with their evidence and limits |
| [`INTERVIEW_DEFENSE.md`](INTERVIEW_DEFENSE.md) | Questions reviewers ask and grounded answers |
| [`showcase/DEMO.md`](showcase/DEMO.md), [`showcase/VISITOR_WORKFLOW.md`](showcase/VISITOR_WORKFLOW.md) | A guided walk through the website |

## Architecture and operations

| Document | Covers |
| --- | --- |
| [`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`showcase/ARCHITECTURE.md`](showcase/ARCHITECTURE.md) | Components, data model, request sequence |
| [`../DECISIONS.md`](../DECISIONS.md) | Numbered design decisions |
| [`showcase/OPERATIONS.md`](showcase/OPERATIONS.md) | API and operating guide |
| [`IDENTITY_BOUNDARY.md`](IDENTITY_BOUNDARY.md) | OIDC login, tenants and roles |
| [`CAPACITY_004.md`](CAPACITY_004.md), [`OVERLOAD_WORKFLOWS_006.md`](OVERLOAD_WORKFLOWS_006.md) | Load tests and overload behavior |
| [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md), [`../DEPLOYMENT.md`](../DEPLOYMENT.md) | Readiness gaps and hosting |
| [`showcase/CI_009.md`](showcase/CI_009.md) | Continuous integration |

## Repair and evaluation (current)

| Document | Covers |
| --- | --- |
| [`REPAIR_REDESIGN_025.md`](REPAIR_REDESIGN_025.md) | The F025 repair loop, every run, root causes and fixes |
| [`research/`](research/) | 020-025 study reports: pilots, qualification, adapter evaluation, status snapshots |
| [`EVALUATION_013.md`](EVALUATION_013.md), [`COMPARISON_014.md`](COMPARISON_014.md), [`MEASUREMENT_014.md`](MEASUREMENT_014.md) | Earlier strategy comparisons |
| [`QUALIFICATION_014.md`](QUALIFICATION_014.md) | How a case qualifies before any model call |

## Models, retrieval and training

| Document | Covers |
| --- | --- |
| [`AI_ENGINEERING_014.md`](AI_ENGINEERING_014.md), [`AI_ADVANCEMENT_PLAN_011.md`](AI_ADVANCEMENT_PLAN_011.md) | Model strategy and roadmap |
| [`CODING_ADAPTER_014.md`](CODING_ADAPTER_014.md), [`CODING_DATA_014.md`](CODING_DATA_014.md), [`CODING_EXECUTION_014.md`](CODING_EXECUTION_014.md), [`CODING_PUBLIC100_014.md`](CODING_PUBLIC100_014.md) | QLoRA adapter: data, training, results |
| [`RETRIEVAL_011.md`](RETRIEVAL_011.md), [`RETRIEVAL_ADAPTER_014.md`](RETRIEVAL_ADAPTER_014.md), [`SOURCE_TRAINING_DATA_014.md`](SOURCE_TRAINING_DATA_014.md) | Code retrieval and its adapter |
| [`CLOUD_TRAINING_013.md`](CLOUD_TRAINING_013.md), [`TRAINING_PREPARATION_013.md`](TRAINING_PREPARATION_013.md), [`LENOVO_INFERENCE.md`](LENOVO_INFERENCE.md) | Compute and inference setup |
| [`LOOP_012.md`](LOOP_012.md), [`REPAIR_STUDY_004.md`](REPAIR_STUDY_004.md), [`REPAIR_REPORTING_013.md`](REPAIR_REPORTING_013.md) | Earlier repair loops and studies |

## Build history

Build-by-build records, kept as written: `BUILD_00*`, `FINAL_REPORT_00*`, `CLAIMS_00*`, `DEMO_00*`, `REVIEWER_00*`,
`RELEASE_006`, `PUBLICATION_005`, `ARCHITECTURE_REVIEW_00*`, `README_BUILD_00*`, `CLOSEOUT_020`, `DELIVERY_PLAN_013`,
`USER_JOURNEYS_007`, `REVIEW_GUIDE_014`, and [`history/`](history/) (the README before the 025 results).

## Background

`DISCOVERY_BRIEF.md`, `LEGACY_REUSE_REVIEW.md`, `legacy-prototype-*.md`, `MIROFISH_REVIEW_006.md`,
`REUSE_AND_HIRING_REVIEW.md`, [`planning/`](planning/) (original planning notes) and
[`superpowers/plans/`](superpowers/plans/) (execution plans).
