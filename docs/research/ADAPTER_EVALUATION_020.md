# Trained 14B adapter comparison — 20 October 2026

The completed comparison found **0/9 verified repairs for the base model and 0/9 for the trained adapter**. Three additional frozen cases had no captured initial source context and remained unavailable in both arms. The twelve-case cohort was preserved; no case was replaced or retuned. This is a small, historically exposed curated comparison, not an official SWE-bench result or a new holdout.

## What actually ran

The saved full100 QLoRA adapter was compared with its same pinned 14B quantized base on a free Tesla T4. Eighteen inference calls completed, with zero training updates. Both arms used the same frozen prompts, greedy decoding, 4,096-token context, 1,024-token output ceiling and generation time budget. Order was counterbalanced. Every completed capture was preserved locally; the final 46,554-byte export passed all 44 manifest-member hashes, frozen model/adapter/prompt bindings, intent identities and capture digests.

Independent Mac verification reproduced baseline failure and reference success for all nine available cases, using pinned source and the original reviewed Docker images. Generated edits used the production original-source authority, syntax and patch validator. Four candidates per arm reached independent tests and failed. Five base candidates were rejected as invalid patches; the adapter had four invalid patches and one invalid action. Causes included unchanged edits, escaped source bounds, Python indentation/syntax errors and incorrect behavior. No candidate was corrected by hand. All original source tree fingerprints were checked before temporary reconstruction cleanup.

## Interpretation

Training completion is established; repair improvement is not. This adapter does not earn a deployment preference over its base from this study. The earlier system-level 7/12 loop result used a different Codex CLI transport and remains separate. Historical 0/10 and 0/36 studies are also separate. Neither larger parameter count nor lower training loss guarantees successful repairs.

The model received only frozen initial context and one proposal. This does not evaluate a feedback loop. One historical issue was fully redacted, and three cases lacked initial context. The training corpus contained 100 supervision rows but only two independent admission captures. These concrete weaknesses motivate a future separately versioned development experiment: improve source/edit alignment, train on independently verified diverse examples, then compare on untouched cases. Do not retune this evaluation cohort or claim that more compute alone fixes these failures.

## Receipts

- `final-evaluation020.json`: exact outcome accounting and limitations.
- `attempt2-evidence-manifest.json`: local generation/check artifact fingerprints.
- `attempt2-export-receipt.json`: retrieved export identity.
- Runtime evidence: `../../kairos-ai014/.runtime/paired-evaluation020-attempt2/verification/report.json`.
- `verifier-preflight020.json`: reference/verifier hash reconstruction.
- `session-loss020.json`: separate earlier uncertain attempt; never overwritten.

No new model experiment is required to finish reporting this result. Docker is stopped after independent checks; cloud runtime deletion was explicitly approved after local export verification. Account sign-out must be verified separately. No provider-retention erasure claim is made.
