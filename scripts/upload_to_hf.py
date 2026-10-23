"""Explicitly publish a verified adapter bundle as one Hugging Face commit.

No upload occurs without --publish. Credentials are read from the environment or
normal Hub authentication, never accepted as a command-line token argument.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

from scripts.prepare_hf_model import DEFAULT_OUT, verify_bundle


def upload_adapter(repo_id: str, model_dir: Path, token: str | None = None) -> None:
    manifest=verify_bundle(model_dir)
    # Import after integrity checks; merely importing this script has no network effects.
    from huggingface_hub import HfApi, CommitOperationAdd
    api=HfApi(token=token or os.environ.get('HF_TOKEN'))
    api.create_repo(repo_id=repo_id,repo_type='model',exist_ok=True,private=True)
    operations=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=str(Path(model_dir)/name))
        for name in sorted(set(manifest['files'])|{'release-manifest.json'})]
    return api.create_commit(repo_id=repo_id,repo_type='model',operations=operations,
        commit_message='Publish verified experimental Kairos adapter artifacts')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-id',required=True)
    parser.add_argument('--model-dir',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    if not args.publish:parser.error('Use --publish only after reviewing the verified bundle and authorizing publication')
    upload_adapter(args.repo_id,args.model_dir)
    print('Verified adapter files uploaded in one commit; inspect the Hub repository for visibility and access.')


if __name__=='__main__':main()
