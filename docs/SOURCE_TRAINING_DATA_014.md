# Licensed source retrieval pilot014

This acquisition contains 414 real maintained docstring-to-function pairs from three pinned public repositories. It is a source retrieval pilot, not an issue-repair corpus. The existing `training_bundle013` issue-family gate remains false and unchanged.

| Split | Repository | Pinned commit | Functions |
| --- | --- | --- | ---: |
| train | pallets/jinja | `5ef70112a1ff19c05324ff889dd30405b1002044` | 166 |
| development | pallets/flask | `d086db856be187255b8ec61ef409357393020f32` | 135 |
| holdout | pallets/click | `2247b35ea1c47c727d7a06e51fa280e12a863ff6` | 113 |

The three repository splits were fixed before extraction. The source-only floors are 40/8/16 functions. They are separate protocol choices and do not satisfy the013 issue-family floors, statistical-power requirements, or a repair-evaluation protocol. Repository-disjoint transfer also confounds library domain and repository style. These public sources may have appeared in the base encoder's pretraining; that exposure is unknown.

## Source rights and exact provenance

All three exact pinned `LICENSE.txt` files contain the BSD 3-Clause terms. Acquisition retains their full copyright and permission notices, including the disclaimer. Source URLs and source/Git-blob hashes appear in `raw-v2/acquisition.json`. `prepared/rights.private.json` retains all three notices; public `rights.json` retains only the two training/development repository notices.

Primary license evidence:

- [Jinja license at the pinned revision](https://raw.githubusercontent.com/pallets/jinja/5ef70112a1ff19c05324ff889dd30405b1002044/LICENSE.txt)
- [Flask license at the pinned revision](https://raw.githubusercontent.com/pallets/flask/d086db856be187255b8ec61ef409357393020f32/LICENSE.txt)
- [Click license at the pinned revision](https://raw.githubusercontent.com/pallets/click/2247b35ea1c47c727d7a06e51fa280e12a863ff6/LICENSE.txt)

The acquisition downloaded only Python modules under the package's `src` prefix, exact repository licenses, and Git-tree metadata. It acquired 69 source/license objects and 1,431,985 bytes including Git trees. Each source object is checked against both its SHA-256 and the advertised Git blob SHA-1 at the pinned tree. No acquired source is imported or executed. AST parsing is the only source processing.

The independent historical audit is pinned to exact SHA-256 `c856081562e65b97206b4a1067d88d140d156fc44b0a9cfaeca621b8e7e9f3dd`. Its 91 reserved/exposed identities include Django, pytest and Requests repository tasks, plus two local Kairos fixtures. All three acquired source repositories are outside those upstream repositories. A first Requests acquisition was rejected by this exclusion gate before extraction or training; its source cache was discarded and its rejection metadata retained. No GitHub issue text, SWE-bench packaging rights, or numeric issue identity is used in this protocol.

## Derivation and labels

Each row records the exact original source file SHA-256, inclusive AST function line range, original range SHA-256, source commit, path, qualified function name, and source/license references. Public functions and methods with sufficient maintained docstrings are candidates; nested functions are not counted separately. A row's query is the first docstring paragraph with whitespace collapsed. Model-input code is the complete function range with its own docstring removed and indentation dedented. The removed docstring line range, transformed-code hash and query hash are explicit. Original source snapshots remain local validation material, outside the public bundle.

The maintained function's own docstring is a structural positive association. It is not a reviewed issue relevance label or repair success. Other functions from the same admitted split and repository can be used as contrastive pseudo-negatives. They are unjudged and can be semantically relevant; no independently reviewed negative label is asserted.

There were 427 candidate functions. Exact normalized equality and Unicode word-token five-gram Jaccard similarity at least 0.80 on either query or transformed code form duplicate groups. All transitive cross-repository duplicate groups are removed entirely. Within one repository, the lexicographically smallest content-derived example ID is retained. Thirteen candidates were removed, leaving 414 rows. This bounded textual deduplication does not prove semantic independence. The private deduplication receipt records every edge and exclusion.

## Frozen admission and evaluator separation

Trusted freeze: `prepared/frozen.json`. Its digest convention is SHA-256 of canonical JSON with sorted keys, UTF-8, compact separators and no trailing newline. The trusted digest is:

```text
0665b9ec9202ac05ff1a71f1c66239ac13081eb2cdd207e5dfa4402e07872729
```

`load_for_training014(data_dir, expected_frozen_sha256)` in `scripts/build_functions014.py` returns `(train_rows, development_rows, identity)`. It reads only the frozen artifact and four exact allowlisted public files. It checks the trusted review binding, source-only gate, original013 boundary, fixed source revisions/splits/licenses, historical audit hash, exact file and row hashes, notices and admitted-row deduplication. It never reads the holdout file, private manifest, private receipts, or full source snapshots.

`load_for_evaluation014(data_dir, expected_frozen_sha256)` in `scripts/evaluate_functions014.py` is evaluator-owned. It additionally verifies the freeze's private-manifest hash, preparation implementation hash, every private file receipt, holdout identities and hashes, Click license and cross-split duplicate separation. It returns holdout rows only. Training code must never import or call this loader.

`prepared/training-bundle014.zip` contains exactly the four public files: `train.jsonl`, `development.jsonl`, `rights.json`, and `manifest.json`. It contains no holdout functions, private receipts, full source files, model weights, credentials, or runtime state. The export receipt binds the exact ZIP and members. Export and readiness are preparation evidence; no model fitting, cloud upload or official benchmark result follows from them.

## Reproduction

From this staging directory:

```sh
python3 scripts/acquire_functions014.py new-raw
python3 scripts/build_functions014.py build --raw new-raw --output new-prepared --audit /path/to/preserved/data-audit.json
python3 scripts/build_functions014.py verify --raw raw-v2 --output prepared
python3 -m unittest discover -s tests -v
```

Acquisition requires public inbound network access. Preparation and verification use only Python's standard library and run offline. Existing output directories are preserved; acquisition/build refuse to overwrite them. A rebuilt freeze uses its own acquisition timestamp and digest and requires its own trusted curator review before training admission.
