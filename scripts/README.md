# Scripts index

Scripts are imported as `scripts.<name>` by tests, CI and evidence receipts, so they keep their paths. A numeric
suffix names the build or study a script belongs to; older suffixes are kept to reproduce historical results.

## Run the product

| Script | Does |
| --- | --- |
| `reviewer` | `demo`, `fullstack`, `check`, `stop`: start or verify the whole system locally |
| `repair_case` | Qualify, repair and score one real SWE-bench bug with a hosted model |
| `hosted_repair` | Run a repair package against NVIDIA or OpenRouter models |
| `run_local`, `configure_local`, `serve_local_model`, `migrate`, `setup_identity`, `setup_investigation_runtime` | Local services, database migrations, OIDC and inference setup |
| `reviewer_*` | Helpers behind `reviewer`: evidence, services, runtime, inference, repair |

## Current repair pipeline (025)

| Script | Does |
| --- | --- |
| `repair_loop025` | Bounded FIND/READ/RUN/SEARCH-REPLACE loop with self-test |
| `search_replace025`, `edit_preflight024` | Parse and apply edit blocks safely |
| `f025_colab`, `f025_tasks`, `f025_cases` | Package building, journaled chain runner, case selection |
| `f025_score`, `qualify014`, `f024_qualify`, `admission023` | Docker qualification and independent scoring |
| `benchmark025_report` | Build the website's benchmark data from scored runs |
| `localization_dev024` | Development / validation / holdout bucket assignment |

## Verification and evidence

`verify_*` check a sealed release or study against its captured evidence (CI runs several on their sealed
commits). `seal_*` create those seals. `package_release00*`, `publication005` and `present*` package releases.

## Research by study

| Prefix or suffix | Study |
| --- | --- |
| `*004`, `study004`, `advance004`, `resume004` | Build 004 repair study and capacity tests |
| `*006`, `*007`, `study007*` | Reviewer releases and qualification |
| `*010`, `*011`, `*012`, `*013` | Repair workflow, retrieval, loop and evaluation studies |
| `coding_*014`, `*014` | 14B QLoRA training, data, verification and comparison |
| `*020`, `*021` | Adapter evaluation and protocol studies |
| `*024`, `f024*` | Localization and the F024 pilot |
| `fde_repair_loop`, `free_model_pilot`, `codesage_mcp_client`, `eval_swebench_batch` | Earlier provider and batch experiments |

## Benchmarks and drills

`benchmark_control_plane`, `run_benchmarks`, `report_capacity004`, `drill_worker_crash`, `verify_recovery006`,
`verify_operations*`: load tests and failure drills behind the capacity and recovery claims.
