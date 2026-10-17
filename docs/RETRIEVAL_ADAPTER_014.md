# Retrieval adapter014

This module trains a shared rank-16 residual projection over frozen CodeRankEmbed query/code embeddings. The encoder stays frozen. It never loads or downloads encoder weights, calls a model API, or reads held-out rows. At 768 dimensions the projection has 24,576 trainable parameters.

Two admission paths remain distinct:

- `issue013` recomputes the original preparation013 freeze from the reviewed inventory and independent audit. It requires the unchanged 40/8/16 positive issue-family gate, exact archive receipt, externally supplied hashes for all five inputs, and byte-identical regenerated public members. The historical empty inventory remains rejected. Only independently bound retrieval labels form within-issue positive/negative pairs.
- `source014` calls the separate `build_functions014.load_for_training014` loader. It admits only the reviewed source-only Jinja training and Flask development split. The original issue-family gate must remain false. A function's maintained docstring identifies its own function after that docstring is removed from code. All other functions in the same repository and split are contrastive pseudo-negatives; they may also be relevant. This is source matching, not independent relevance review, repair-model tuning, or evidence of repair gain. Click held-out data stays with the separate evaluator.

The source loader receives SHA-256 of canonical `frozen.json` without its terminating newline. Other CLI input hashes bind exact file bytes. Obtain trusted hashes from a separate review record; do not derive authorization from the files being admitted. A digest establishes integrity, not human approval.

## Frozen embedding cache

The caller encodes admitted `query` and `code` strings with the existing reviewed local encoder. The JSON cache has this structure:

```json
{
  "schema_version": "kairos-frozen-embeddings014-v1",
  "frozen_sha256": "canonical frozen manifest SHA-256",
  "encoder": {
    "model_id": "nomic-ai/CodeRankEmbed",
    "revision": "3c4b60807d71f79b43f3c4363786d9493691f8b1",
    "dimension": 768,
    "pooling": "cls",
    "normalize": true,
    "max_tokens": 512,
    "query_prefix": "Represent this query for searching relevant code: ",
    "profile_sha256": "SHA-256 of canonical reviewed encoder profile"
  },
  "rows": [
    {
      "example_id": "exact exported row ID",
      "query_sha256": "SHA-256 of exact query UTF-8 bytes",
      "code_sha256": "SHA-256 of exact code UTF-8 bytes",
      "query": [0.0],
      "code": [0.0]
    }
  ]
}
```

The illustrated vectors are placeholders, not valid embeddings. Each actual vector must contain 768 finite numbers with L2 norm between 0.99 and 1.01. Coverage must exactly equal the admitted train/development IDs. Held-out IDs, duplicate rows, changed text hashes, incompatible profiles and unnormalized vectors are rejected. The original issue path calls `training_bundle013.model_input` for every row; repair targets never become inputs.

## Fitting

Use an isolated Python environment with `requirements-training014.lock`. Existing local packages may be reused without installation. Add this training directory, the data preparation `scripts` directory, and the main checkout to `PYTHONPATH`. The main application dependencies remain unchanged.

```sh
python retrieval_adapter014.py source014 \
  --source-data /absolute/path/data/prepared \
  --source-frozen-sha256 TRUSTED_CANONICAL_FROZEN_SHA256 \
  --cache /absolute/path/train-development-embeddings.json \
  --cache-sha256 TRUSTED_CACHE_FILE_SHA256 \
  --output /absolute/path/new-training-run \
  --device cpu
```

`load_source_bundle`, `load_embedding_cache`, and `fit` provide the same Python interface. No fitting occurs at import or during admission. Training uses exactly 200 steps, batch size 16, seed 14014, AdamW with learning rate 0.003 and no weight decay, fixed cosine decay to a 0.1 learning-rate floor, temperature 0.1, and gradient norm cap 1. The constants in `PROTOCOL` pin all hyperparameters. No validation-based early stopping or held-out selection occurs. Each issue family or source target receives equal total pair weight. All paired candidates stay in their own issue or source repository/split.

Development selection happens at steps 0, 20, 40, ..., 200, using MRR, then Recall@5, with the earliest checkpoint retained on ties. Step zero is an eligible identity projection. Base and selected-adapter MRR and Recall@1/5/10 use identical candidate sets, stable row-ID ties and paired per-query deltas. The report distinguishes source functions from issue families. These bounded candidate metrics do not establish complete source-corpus recall or repair success.

`--stop-after 37` deliberately interrupts at global step 37 without introducing a development selection event. Continue into a new output directory using `--resume /absolute/path/checkpoint-000037 --resume-sha256 TRUSTED_CHECKPOINT_MANIFEST_SHA256`. The fixed 200-step schedule is not reset. Exact resume requires identical runtime, device, implementation, protocol, frozen data and cache identity. CPU/CUDA migration is allowed for inference, not claimed as bitwise training continuation.

CPU uses two threads. CUDA requires `CUBLAS_WORKSPACE_CONFIG=:4096:8` before launching Python, available CUDA, and deterministic PyTorch kernels. CUDA support is implemented; the focused local suite ran on CPU only.

## Safe state and inference export

Checkpoints contain `state.safetensors` and a JSON manifest. The manifest binds tensor bytes and the training identity. It records Adam tensors and parameter groups, global step, complete loss and development history, selected weights, Python RNG, Torch CPU/CUDA RNG, and the independent sampler's permutation, cursor, epoch and RNG. No pickle or `torch.load` is used. Resume requires the externally supplied manifest hash before tensor loading.

`export_projection(checkpoint_directory, trusted_checkpoint_manifest_sha256, new_export_directory)` writes a small `adapter.json` and `manifest.json`. This deployment artifact contains only selected projection weights and configuration, public hashes and the encoder identity. It excludes the base model, optimizer, sampler, RNG, examples and held-out material. `load_inference_projection(export_directory, trusted_export_manifest_sha256, device="cpu")` reconstructs the shared head. Apply it to L2-normalized embeddings from the exact bound encoder for both query and code, then use cosine similarity. Encoding remains external and frozen.

The separate `evaluate_source014.py` evaluator imports the evaluator-owned `evaluate_functions014.load_for_evaluation014` admission module. It verifies the frozen private-manifest chain, exact Click held-out rows and cache coverage, and the encoder identity against the exported head. It reads only the inference JSON head, never checkpoint optimizer state. It ranks each held-out target among every sealed held-out function and reports per-query ranks, paired MRR/Recall deltas, and 2,000 fixed-seed paired-bootstrap 95% intervals. These are conditional descriptive intervals over related functions in one repository; they do not estimate repository-level generalization.

```sh
python evaluate_source014.py \
  --data /absolute/path/data/prepared \
  --frozen-sha256 TRUSTED_CANONICAL_FROZEN_SHA256 \
  --cache /absolute/path/evaluator-only-heldout-cache.json \
  --cache-sha256 TRUSTED_HELDOUT_CACHE_FILE_SHA256 \
  --adapter /absolute/path/exported-selected-head \
  --adapter-manifest-sha256 TRUSTED_HEAD_MANIFEST_FILE_SHA256 \
  --output /absolute/path/new-heldout-report.json
```

Held-out examples, caches, labels and result-based choices stay outside the training loader. Held-out outcomes must not change the schedule, data selection or checkpoint choice.

## Focused verification

```sh
python -m unittest discover -s /absolute/path/training -p test_retrieval_adapter014.py -v
```

The optional suite skips explicitly when the isolated ML dependencies are absent. All synthetic geometry data is labeled `fixture`; it tests real gradients, safe checkpoint integrity, complete 37+163-step versus uninterrupted 200-step bitwise resume, sampler and optimizer restoration, inference export, exact cache bindings, source split boundaries, and the unchanged false/forged preparation013 gate. Fixture learning is not reported as a model outcome. The suite does not fit acquired source data or run a held-out evaluator.

## Measured source014 release

The real selected profile completed 200 CPU optimizer steps. Development selected step 100 from the hard8-lr0003 profile; exactly two additional revisions followed the initial uniform-negative run. No Click scores entered that selection. Actual 37+163-step resume reproduced the full uninterrupted checkpoint bit for bit.

On 113 held-out Click functions, base/head MRR was 0.920823/0.922526, Recall@1 was 0.876106 for both, and Recall@5 was 0.964602/0.973451. The 2,000-replicate paired function-bootstrap MRR difference interval was [-0.011066, 0.014514]. This conditional interval includes zero and does not estimate repository-level generalization. The study supports a narrow measured training claim. It does not establish repair gain, language-model fine-tuning, independent relevance labels or benchmark superiority.

Captured train/development encoding took 38.203824 seconds; held-out encoding took 20.331182 seconds. Standalone fitting wall time was not captured. Every candidate profile and paired result remains under `evidence/measurement014/training`. The selected head manifest SHA-256 is `404b4e89a224ee424da41b650e23619d401e6b9187fd5f1f2209d1190bff62d0`.

From the checkout, using an isolated Python environment with `requirements-training014.lock` and the regular application dependencies:

```sh
python -m scripts.reproduce_training014 \
  --output /absolute/path/new-training-reproduction \
  --budget-root /absolute/path/owned-experiments
```

The output must be new and inside the counted storage roots. Existing model caches and experiments also belong in the aggregate budget when present. The command verifies the package and compressed embedding hashes, reproduces the frozen selected profile, and compares exact inference-head bytes and the selected step. It records complete manifest equality separately because checkpoint provenance includes runtime identity. It never opens held-out embeddings or dispatches inference. Cross-version or cross-device bitwise equivalence is not promised; runtime identity is recorded, and differences fail the exact reproduction receipt.

## Use the trained head in retrieval

`TrainedCodeEncoder014` wraps the exact verified CodeRank encoder and applies the selected projection to both code and query vectors. Its encoder identity includes the head manifest digest and selected step. Existing retrieval indexes therefore reject a query encoder that omits or changes the head; the projection is never silently applied only to queries. Input finiteness, normalization, dimension and artifact hashes are checked.

```python
from scripts.retrieval011.encoder import CodeRankEncoder
from scripts.trained_encoder014 import TrainedCodeEncoder014

base = CodeRankEncoder(encoder_directory, reviewed_profile, batch_size=2, threads=2)
encoder = TrainedCodeEncoder014(
    base,
    "evidence/measurement014/training/adapter",
    "404b4e89a224ee424da41b650e23619d401e6b9187fd5f1f2209d1190bff62d0",
)
# Pass this same encoder to retrieval011.core.build_index and query.
```

The default repair studies retain their frozen encoder and AST strategy bindings. Choosing this experimental head requires building a separately identified index. Artifact integration does not by itself demonstrate a repair improvement.
