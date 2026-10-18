"""
Upload Kairos 14B QLoRA adapter to Hugging Face Hub.

Usage:
    python scripts/upload_to_hf.py --repo-id <username>/kairos-14b-qlora [--token <HF_TOKEN>]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

try:
    from huggingface_hub import HfApi, create_repo
except ImportError:
    print("[!] huggingface_hub not installed. Install with: pip install huggingface_hub")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = ROOT / "dist" / "kairos-14b-qlora"

FILES_TO_UPLOAD = [
    "adapter_model.safetensors",
    "adapter_config.json",
    "README.md",
    "trainer_state.json",
    "resource-proof.json",
]


def upload_adapter(repo_id: str, model_dir: Path, token: str | None = None) -> None:
    token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    api = HfApi(token=token)

    print(f"[*] Ensuring Hugging Face repository exists: {repo_id}...")
    try:
        create_repo(repo_id=repo_id, repo_type="model", exist_ok=True, token=token)
        print(f"[✓] Repository ready: https://huggingface.co/{repo_id}")
    except Exception as e:
        print(f"[!] Note on repo creation: {e}")

    print(f"[*] Uploading Kairos adapter files from {model_dir}...")
    for fname in FILES_TO_UPLOAD:
        fpath = model_dir / fname
        if not fpath.exists():
            print(f"[!] Skipping missing file: {fname}")
            continue

        print(f"    Uploading {fname} ({fpath.stat().st_size:,} bytes)...")
        api.upload_file(
            path_or_fileobj=str(fpath),
            path_in_repo=fname,
            repo_id=repo_id,
            repo_type="model",
            token=token,
        )

    print(f"\n[✓] Successfully published Kairos 14B QLoRA adapter to:")
    print(f"    https://huggingface.co/{repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Kairos adapter to Hugging Face Hub")
    parser.add_argument("--repo-id", type=str, required=True, help="Target HF repo ID (e.g. yourname/kairos-14b-qlora)")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR, help="Directory containing adapter files")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face User Access Token (or set HF_TOKEN env var)")
    args = parser.parse_args()

    upload_adapter(args.repo_id, args.model_dir, args.token)


if __name__ == "__main__":
    main()
