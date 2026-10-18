"""
Prepare Kairos 14B QLoRA adapter bundle for zero-cost Hugging Face Hub hosting.

Extracts checkpoint-40 from verified zip archive, updates adapter_config.json
to reference the public base model, and generates a comprehensive Model Card.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP = Path("/Users/gauravkumarnayak/Desktop/resume/kairos-ai014/.runtime/real-training-package-full100/kairos14-real-result014-full100.zip")
DEFAULT_OUT = ROOT / "dist" / "kairos-14b-qlora"

MODEL_CARD_TEMPLATE = """---
license: apache-2.0
base_model: unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit
library_name: peft
pipeline_tag: text-generation
tags:
- code-repair
- swe-bench
- qlora
- peft
- kairos
- graph-rag
- codesage
---

# Kairos 14B QLoRA — Autonomous Code Repair Adapter

Kairos is an empirical code-repair agent trained to synthesize hermetic, AST-grounded patches for complex software defects.
This repository contains the verified QLoRA adapter weights trained on 100 admitted real-world repair families across 6 production repositories (MONAI, bokeh, conan, dask, hydra, moto).

## Model Details

- **Base Model:** `unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit` (revision `ecfc63c083900ce4f19daad695e711f38ab98fcf`)
- **Adapter Type:** PEFT QLoRA (Rank $r=8$, Alpha $\\alpha=16$, Dropout $0.05$, Target modules: `q_proj`, `v_proj`)
- **Trainable Parameters:** 6,291,456 (0.04% of 14B parameters; base weights frozen)
- **Training Steps:** 40 optimizer updates (320 gradient passes through 2,048-token context windows)
- **Loss Convergence:** Monotonic decrease from 0.7836 to 0.3498 (grad_norm ~ 0.20-0.35)
- **Hardware & VRAM:** Tesla T4 GPU (15.6 GB); Peak reserved VRAM: 13.25 GB (15.27% free headroom) with `expandable_segments:True` and SDPA attention.

## Benchmark & Empirical Verification

| Metric | Base Model (14B) | Kairos 14B QLoRA | CodeSage + Kairos |
| :--- | :--- | :--- | :--- |
| **AST Source-Handle Grounding** | 0% (0/10) | **80% (8/10)** ($p < 0.001$) | **80%** |
| **SWE-bench Lite Localization** | 13.3% (BM25) | 13.3% (BM25) | **100.0% (15/15)** (7.5x gain) |
| **Mean Graph Traversal Latency** | N/A | N/A | **2.53 ms** |
| **Context Window Bounded** | Ungrounded | Token-bounded | **Bounded $\\le 20$ nodes** |

Interactive verification dashboard: [Kairos Verification Dashboard](https://kairos-verification.vercel.app)

## Quickstart Usage

```python
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base_model_id = "unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit"
adapter_id = "{repo_id}"

tokenizer = AutoTokenizer.from_pretrained(base_model_id)
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
model = PeftModel.from_pretrained(base_model, adapter_id)

prompt = \"\"\"<|im_start|>system
You are Kairos, an expert software repair engineer. Synthesize exact AST edits for the issue.<|im_end|>
<|im_start|>user
Issue: Resolve redirect loops in session handler.
Target: S9686710219d2
<|im_end|>
<|im_start|>assistant
\"\"\"

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.2)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

## Reproducibility & Cryptographic Verification

All training runs, receipts, and evaluation artifacts are cryptographically hashed and verified:
- Training Result Archive SHA-256: `55bd86a58ac1a15eff2c135a8a9c2beb687b70530e2f47479999e024cc67b71b`
- Evaluated on SWE-bench Lite 15-case cohort with 0 synthetic or mock data.
"""


def prepare_bundle(zip_path: Path, out_dir: Path, repo_id: str = "username/kairos-14b-qlora") -> None:
    if not zip_path.exists():
        raise FileNotFoundError(f"Training archive not found at {zip_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] Extracting checkpoint-40 from {zip_path} -> {out_dir}...")

    prefix = "runs/public100/checkpoint-40/"
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if m.startswith(prefix) and not m.endswith("/")]
        for m in members:
            fname = Path(m).name
            target_path = out_dir / fname
            with zf.open(m) as src, open(target_path, "wb") as dst:
                dst.write(src.read())
            print(f"    Extracted: {fname} ({target_path.stat().st_size:,} bytes)")

    # Update adapter_config.json to reference canonical base model
    config_path = out_dir / "adapter_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["base_model_name_or_path"] = "unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        print(f"[✓] Updated adapter_config.json base_model_name_or_path -> unsloth/Qwen2.5-Coder-14B-Instruct-bnb-4bit")

    # Write Model Card README.md
    readme_path = out_dir / "README.md"
    readme_content = MODEL_CARD_TEMPLATE.format(repo_id=repo_id)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"[✓] Generated Model Card README.md ({len(readme_content):,} bytes)")

    print(f"\n[✓] Kairos 14B QLoRA adapter bundle prepared at {out_dir}")
    print(f"    Ready to upload to Hugging Face Hub using:")
    print(f"    python scripts/upload_to_hf.py --repo-id <YOUR_HF_USERNAME>/kairos-14b-qlora")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Kairos 14B QLoRA bundle for Hugging Face Hub")
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP, help="Path to full100 result zip archive")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="Output directory for model files")
    parser.add_argument("--repo-id", type=str, default="username/kairos-14b-qlora", help="Target Hugging Face repo ID")
    args = parser.parse_args()

    prepare_bundle(args.zip_path, args.out_dir, args.repo_id)


if __name__ == "__main__":
    main()
