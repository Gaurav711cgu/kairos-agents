# Repair study reporting

`scripts.repair_report013` reads captured evidence only. It does not execute models,
checks, containers, network calls, retries, or official prediction exports.

Freeze a study JSON before inference with `study_id`, an honest `scope`, unique
`cases` (instance ID strings), and at least two `arms`. Each arm contains
`arm_id`, the exact `model_name_or_path`, and a lowercase 64-character
`configuration_sha256`. Preserve the actual configuration and source receipts
separately. The planned three arms are baseline context with six calls, retrieval
with six calls, and retrieval with ten calls. The reporter also accepts other
explicitly frozen arms.

The ledger is `{"study_sha256": "...", "attempts": [...]}`. Compute its identity
with `repair_report013.identity(frozen_json)`. Each captured row must contain
`instance_id`, `arm_id`, the same model/configuration identity, and `outcome`.
Duplicate case/arm rows and mismatches are errors. Missing rows remain visible as
`missing_ledger`; they are not invented attempts. Preserve original ledger hashes
when adapting historical captures. A configuration hash or timestamp supplied by
the reporter's input does not independently prove provenance or freeze ordering.

Optional costs are `calls`, `checks`, `input_tokens`, `output_tokens`, and
`elapsed_seconds`. Null or absent costs remain missing. `observed_sum` is partial
when observations are missing; `complete_sum` then remains null. Internal provider
retries cannot be inferred from harness call counts. No cost is inferred from
absent provider usage.

Optional `confidence` is an object with `experiment_id`, `abstained`, and
`probability`. A probability also requires timezone-aware `captured_at` and a row
`independent_checks_started_at`, with capture strictly earlier. Abstention requires
a null/absent probability. Only `verified_repair` and `failed_checks` receive
Brier labels; unknown, infrastructure, invalid and unavailable outcomes remain
unscored. Reports retain per-issue/model observations and bin counts. Small
samples cannot establish reliable confidence thresholds.

Run `python3 -m scripts.repair_report013 --frozen study.json --attempts attempts.json --output report.json --seed 013`.
Primary paired differences include verified repairs and known failures:
`failed_checks`, `invalid_patch`, `invalid_response`, `no_patch`, and
`budget_exhausted`. Infrastructure, unavailable, timeout and unknown outcomes
stay excluded with explicit IDs and reasons. The graded-only secondary comparison
uses `verified_repair` and `failed_checks`. Every comparison retains the full
intent-to-run pair count. Verified-per-attempted and verified-per-intent-to-run
denominators remain separate. Percentile intervals resample issues, using the
narrow paired method from `retrieval_study011.py`.
They are descriptive and do not establish superiority or an official score.

Unit tests use synthetic fixtures solely to test reporting rules. No measured
repair result or confidence score is supplied with this module.
