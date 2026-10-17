# Training preparation013

This is offline data preparation software, not a training run. It uses only Python's standard library. It never executes source examples, invokes subprocesses, loads pickle files, downloads models, uploads data, or changes accounts. The module is integrated into the Kairos source tree; model fitting remains a separate operation.

The current audit has 123 public records, ten verified trajectories, **three distinct verified tasks**, four rendered verified patches and 91 exposed or reserved task IDs. These are not independent positive examples. The original retrieval011 audit remains a preserved historical snapshot. `evidence/evaluation013/training/inventory.empty.json` contains no acquired examples; its `frozen.empty.json` correctly reports `training_data_ready: false`. No cloud upload or training has occurred. Neither synthetic tests nor the empty inventory establish a licensed training corpus.

## Commands and integration

Run from the repository root:

```sh
python3 -m unittest discover -s tests -p test_training_bundle013.py -v
python3 -m scripts.training_bundle013 freeze inventory.reviewed.json frozen.reviewed.json --audit /path/to/data-audit.json
python3 -m scripts.training_bundle013 export inventory.reviewed.json frozen.reviewed.json prepared --audit /path/to/data-audit.json
```

Use the current `evidence/evaluation013/data-audit.json` for new work. It includes the three additional historical-plan IDs, reserved013 candidate IDs and the successful development pilot. The original retrieval011 audit remains a historical snapshot. The audit input must be independently maintained. Every exposure identity and original issue digest in its exact bytes must be covered by the inventory guard. Do not substitute an empty audit for production use. The committed empty freeze uses audit SHA-256 `c856081562e65b97206b4a1067d88d140d156fc44b0a9cfaeca621b8e7e9f3dd`.

The curator prepares an inventory and completes rights, relevance/verification, privacy and export review before freezing it. Compute the review binding with `sha(canonical({k: v for k, v in inventory.items() if k != "export_review"}))`. Set the review decision only after that review; the digest is an integrity binding, not a signature or a substitute for human evidence. A changed inventory, audit, implementation, seed, gate or manifest requires a separately reviewed freeze. The CLI refuses to overwrite an existing freeze or export directory.

The curator keeps the inventory, frozen manifest, all receipts and `holdout-manifest.private.json` private. The training author receives only `training-bundle.zip` or its `public` directory. Do not hand over the parent export directory. Held-out queries, targets, relevance labels, verifier code and private grading receipts remain in a separate evaluator-owned store. The private manifest records identifiers only; it does not construct that evaluator store.

Before any fitting, check the trusted frozen manifest and public `manifest.json` together, verify the archive SHA-256 against `export-receipt.private.json`, and require `training_data_ready` to be true. Export is permitted for inspection while that gate is false; it never authorizes fitting. A user-supplied Boolean cannot alter the recomputed gate. A training integration must call `model_input(exported_row)` for inputs. Its only output is `query` and original `code`; repair targets remain separate supervised loss targets. The loader rejects held-out rows and changed example hashes. Do not concatenate `target_patch` into the prompt or retrieval query.

## Local inventory schema

Every object uses exact field sets; missing and unknown fields are rejected. JSON duplicate keys and non-finite numbers are rejected. Maximum input/export size is 16 MiB, maximum rows 1,000, maximum query or patch length 20,000 characters, maximum original source file length 1 MiB. These bounds make pairwise review triggers finite; this is a small pilot tool, not a web-scale deduplicator.

The root fields are:

| Field | Contract |
| --- | --- |
| `schema_version` | Exactly `kairos-training-preparation013-v1`. |
| `study_id` | Nonempty, versioned identifier. |
| `examples` | Only retrieval rows or only repair rows; separate studies cannot combine their counts. |
| `families` | Object mapping the lexicographically smallest `owner/repo#numeric_issue` to the complete list of canonical aliases. Every example must have explicit membership. Overlapping families must be merged first. |
| `unresolved_families` | Family keys with unresolved alias, backport, adjacent-commit or related-fix relationships; quarantined. The curator must perform this relationship review. |
| `rights` | Map from local reference keys to rights evidence objects. |
| `receipts` | Map from exact canonical receipt SHA-256 to the corresponding object. Private; never exported. |
| `exposures` | Map to current acquisition-review events. Historical events belong in the guard and independent append-only audit. |
| `guard` | `reviewer`, `reviewed_at`, `audit_sha256`, `identities`, `issue_sha256`, `reserved_components`, `locked_components`. The last four fields are string lists. Populate reserved/locked components from all existing frozen protocols before adding real rows. |
| `export_review` | `reviewer`, timezone-aware `reviewed_at`, Boolean `approved`, `inventory_content_sha256`. |

An example's shared fields are `kind`, `instance_id`, `repository`, `upstream_issue_id`, `dataset_id`, `dataset_revision`, `source_commit`, timezone-aware `acquired_at`, `query`, `issue_sha256`, `path`, `source_text`, `source_file_sha256`, `start_line`, `end_line`, `code`, `chunk_sha256`, `rights_refs` and `exposure_refs`.

Repository identifiers are `owner/repo`; upstream issue IDs are numeric strings. Dataset revisions and source commits are full lowercase 40- or 64-character hashes, not mutable tags. Issue, full original source and chunk hashes bind exact UTF-8 bytes. Inclusive positive line numbers must reproduce `code` exactly from `source_text`, including line endings. The full original source is local validation material and is removed from exports. This verifies bytes, not the truth of a claimed acquisition commit; acquisition review must establish that provenance.

Paths are relative POSIX paths. Absolute paths, traversal, empty segments, backslashes, hidden path components and denied runtime/private directories are rejected. No filesystem source path is dereferenced. Source examples and patches remain inert strings, so symlinked source trees cannot be traversed. JSON input symlinks and export-parent symlinks are rejected.

### Retrieval examples

`kind` is `retrieval`. Additional fields are:

| Field | Contract |
| --- | --- |
| `relevance` | Integer 0 or 1; Boolean is rejected. A failed repair does not imply irrelevance. |
| `label_provenance` | Exactly `method`, `reviewer`, `reviewed_at`, `receipt_sha256`. Method is `independent_review` or explicitly named `patch_proxy`. |
| `negative_method` | Null for a positive. For a negative, exactly `method`, pinned `miner_revision`, `component_key`; mining is restricted to that component, which is stricter than within-split mining. |

A relevance receipt has exactly `kind: relevance_review`, `issue_sha256`, `repository`, `source_commit`, `path`, `start_line`, `end_line`, `source_file_sha256`, `chunk_sha256`, `relevance`, `method`, `reviewer` and `reviewed_at`. All values must match the example and label provenance; unchanged bytes cannot be retagged to another commit or file. Patch-derived labels remain documented proxies; they do not establish complete relevance coverage. Conflicting relevance labels on the same issue/chunk quarantine the family.

### Verified repair examples

`kind` is `repair`. Additional fields are `target_patch`, `target_patch_sha256`, `baseline_failure_receipt_sha256`, `verification_pass_receipt_sha256`, `verifier_revision`, `outcome`, `outcome_provenance` and `target_use`.

The required values are `outcome: verified_repair`, `outcome_provenance: original` or `post_hoc`, and `target_use: supervised_loss_only`. An original investigation's failure must never be relabeled as an original success after a post-hoc check. Failed or unknown trajectories do not fit this schema and must stay in a separate diagnostic corpus.

Each verification receipt has exactly `kind` (`baseline_failure` or `verification_pass`), `issue_sha256`, `repository`, `source_commit`, `path`, `start_line`, `end_line`, `source_file_sha256`, `target_patch_sha256`, pinned `verifier_revision`, `tests_sha256`, nonnegative integer `passed`, `failed`, positive `total`, Boolean `independent: true` and `outcome_provenance`. Both receipts must bind the same issue/source/patch/verifier/test suite and exact test count. The baseline must fail at least one test; the candidate must pass every test. This tool verifies receipt consistency, not verifier execution or independence; curator evidence must substantiate those claims.

The bounded repair schema supports one original file/chunk per row. It does not infer multi-file context. Exported repair rows also contain an `original_context` object with `path`, `start_line`, `end_line` and `code`.

### Rights and current exposure evidence

Each rights object has exactly `component_key`, `kind`, `origin`, `revision`, `license_or_terms`, `evidence_sha256`, `notices`, `reviewer`, `reviewed_at`, `training_allowed` and `redistribution_allowed`. Origins use HTTPS without credentials, queries or fragments. Nonempty license/terms and exact evidence hashes are mandatory. Notices are retained in public `rights.json`. Unknown/conflicting decisions must be recorded as false and quarantine the entire family; this tool does not decide legal rights.

Every row needs rights evidence separately covering issue text, source, labels and dataset packaging; repair rows also need patch rights. The issue revision equals the original issue hash, source revision equals the pinned source commit, dataset revision equals the pinned dataset revision, label revision equals its relevance/pass receipt hash, and patch revision equals the exact target-patch hash. A packaging license cannot fill another category.

Each current exposure event has exactly `component_key`, `issue_sha256`, `kind: acquisition_review` and `reviewed_at`, and must bind the row's family and original query. `exposure_refs` must be nonempty. The curator must append actual new exposures to the external ledger; this tool never edits historical audit files.

## Deduplication, splitting and gate

Explicit aliases, revisions, related issues and all examples inherit one family key. Audit import preserves raw IDs and adds canonical mappings only for documented `owner__repo-number` and `-scope` variants. It does not strip arbitrary suffixes. Families touching any historical identity, original issue digest, reserved component or locked component are excluded from this initial protocol, including train/development. The historical retrieval011 digests use SHA-256 of lowercase, whitespace-collapsed issue text; the guard checks that exact normalization as well as the raw issue hash. Exact original issue bytes remain independently bound to receipts and rights. Historical exposed positives remain diagnostic.

Exact duplicate rows for the same family/revision/source/query/chunk/target/label collapse to a deterministic canonical copy. Removed-copy, retained-copy and normalized issue/patch hashes remain in the local freeze; the bound inventory retains full provenance. Shared boilerplate code across different issues does not establish a label or a family. Cross-family identical/normalized issues or patches quarantine both families. Normalization is only Unicode NFC, CRLF-to-LF and whitespace collapsing. Word-token five-gram Jaccard similarity at least 0.80 is a quarantine trigger, as are comparisons containing a text with fewer than five tokens. These triggers require curator review; they do not prove independent examples. Confirmed related copies should be merged into one explicit family before a new version is frozen.

The split bucket is `int(SHA256(UTF8("kairos-cloud013-v1\n" + component_key)).hexdigest(), 16) % 100`: 0–69 train, 70–84 development, 85–99 holdout. Existing frozen cohorts must be reserved rather than reassigned. Do not change the seed or add candidates to replace disappointing holdout outcomes. Negative mining must stay within the declared component. Each family receives total `issue_weight` 1 across its exported rows, so repeated patches and negatives do not increase its independent weight.

The gate requires at least 40 train, eight development and 16 holdout **positive issue families**, two repositories, and at least four development/eight holdout positive families per repository. For cross-repository alias families, repository counts use the canonical family key's repository once. Negative-only families never satisfy these floors. Frozen output reports raw rows, deduplicated rows, all distinct families, positive families, repository counts, quarantine and shortfalls separately. These study floors are a protocol choice, not statistical power guarantees.

## Export boundary and limitations

The deterministic ZIP allowlist is exactly `train.jsonl`, `development.jsonl`, `rights.json`, `manifest.json` and `allowlist.json`. There are no holdout examples, source snapshots, raw receipts, verifier code or runtime directories in it. `allowlist.json` binds every other member's exact SHA-256 and size; the separate private receipt binds the archive's exact SHA-256 and byte size. The archive is reopened and every member's bytes, size, regular-file mode and safe name are checked against the in-memory allowlist.

Exported rows use `kairos-retrieval-training-v1` or `kairos-repair-training-v1`, retain the applicable shared fields except `source_text`, and add `split`, `component_key`, computed `issue_weight` and `example_id`. `example_id` is SHA-256 of canonical UTF-8 JSON of that row without the ID, with sorted keys, no ASCII escaping, compact separators, no NaN and no trailing newline. `kind`, `acquired_at` and `issue_weight` are explicit preparation013 additions to the earlier design contract.

The scanner rejects known private home/runtime path forms, private keys and common credential patterns. It is bounded pattern matching; a passing scan does not certify privacy, licensing, noncontamination or safe publication. Human review must inspect the extracted allowlisted public files before any later upload. No upload, model download, paid compute, account action, frozen evaluation replacement or actual fitting is authorized by this deliverable.
