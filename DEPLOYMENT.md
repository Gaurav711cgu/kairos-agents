# Local operation and optional publication

Kairos is delivered as a local reviewable system. No new hosting deployment or model upload was performed during the October 20 closeout. Training and repair claims have separate evidence; see [CLOSEOUT_020.md](docs/CLOSEOUT_020.md).

## Review locally

Use Python 3.12 and Node.js 24, then follow the [README quick start](README.md).

```sh
python3 -m scripts.reviewer demo
python3 -m scripts.reviewer check
python3 -m scripts.reviewer check --fullstack
python3 -m scripts.reviewer stop
```

The recorded interface serves captured results without live inference or authentication. Live full-stack operation provisions isolated PostgreSQL and Keycloak; inference requires an explicitly prepared worker/model. An unavailable live API must not be presented as a new successful investigation.

## Prepare the trained adapter for review

```sh
python3 -m scripts.prepare_hf_model --help
```

Pass the verified full100 result ZIP and a new output directory. The command validates archive identity, every manifest hash, training completion and safe paths before exporting only the adapter files, a factual model card and a release manifest. It excludes optimizer, RNG, scheduler state, account state and base weights. Existing output is never overwritten.

```sh
python3 -m scripts.upload_to_hf --help
```

The uploader validates the exact package before network access and requires explicit `--publish`. Credentials belong in the normal private Hugging Face environment, never source control or command-line token arguments. Repository creation defaults to private. External publication requires review of the concrete package.

## Evaluation boundary

The historical 15/15 annotated localization run is not a repair result or a fair benchmark. Its indexes were built from installed packages, not historical issue base revisions, and retrieval used caller annotations. The replacement issue-only diagnostic uses equal context-token budgets and reports these sources as ineligible. A valid future comparison must index pinned case source, withhold target/reference material from selection, and run independent patch checks before claiming repairs.
