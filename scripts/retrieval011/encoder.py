"""Pinned, local-only CodeRankEmbed inference with explicit tokenization evidence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np

MODEL = "nomic-ai/CodeRankEmbed"
REVISION = "3c4b60807d71f79b43f3c4363786d9493691f8b1"
ORIGINAL_SHA256 = "827529bcd58aef0d9082e66eeff7e7d53a02f62bd005f841a26b3d3e2fb17ebe"
PREFIX = "Represent this query for searching relevant code: "


def _sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_profile(directory, profile):
    """Check an explicit public profile before importing custom code or weights."""
    original = Path(directory).absolute()
    if any(p.is_symlink() for p in (original, *original.parents)):
        raise ValueError("Encoder directory cannot traverse symlinks")
    root = original.resolve(strict=True)
    if (profile.get("version") != "coderank-encoder011-v1" or profile.get("model") != MODEL
            or profile.get("revision") != REVISION
            or profile.get("original_weights", {}).get("sha256") != ORIGINAL_SHA256
            or profile.get("dimension") != 768 or profile.get("pooling") != "cls"
            or profile.get("query_prefix") != PREFIX
            or profile.get("storage_dtype") != "float16"
            or profile.get("inference_dtype") != "float32" or profile.get("max_tokens") != 512):
        raise ValueError("Unsupported frozen encoder profile")
    required = {"config.json", "configuration_hf_nomic_bert.py", "modeling_hf_nomic_bert.py",
                "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt",
                "1_Pooling/config.json", "README.md", "model.fp16.safetensors"}
    if set(profile.get("files", {})) != required:
        raise ValueError("Encoder profile has an unexpected file inventory")
    total = 0
    for name, value in profile["files"].items():
        path = root / name
        if any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
            raise ValueError("Encoder files cannot traverse symlinks")
        if (not path.is_file() or type(value.get("bytes")) is not int
                or path.stat().st_size != value["bytes"] or _sha(path) != value.get("sha256")):
            raise ValueError("Encoder file hash or size mismatch")
        total += value["bytes"]
    if total > 300 * 1024**2:
        raise ValueError("Encoder profile exceeds its storage budget")
    return root


class CodeRankEncoder:
    dimension = 768

    def __init__(self, directory, profile, *, batch_size=2, threads=2):
        if batch_size not in (1, 2, 4) or threads not in (1, 2, 4):
            raise ValueError("Unsupported bounded CPU execution settings")
        root = verify_profile(directory, profile)
        try:
            import torch
            from safetensors.torch import load_file
            from transformers import BertTokenizerFast
        except ImportError as error:
            raise ValueError("Install the isolated requirements-retrieval011.lock dependencies") from error
        torch.set_num_threads(threads)
        self.torch, self.batch_size = torch, batch_size
        module_name = "kairos_coderank011_" + REVISION
        package = types.ModuleType(module_name)
        package.__path__ = [str(root)]
        sys.modules[module_name] = package
        modules = {}
        for name in ("configuration_hf_nomic_bert", "modeling_hf_nomic_bert"):
            qualified = module_name + "." + name
            spec = importlib.util.spec_from_file_location(qualified, root / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[qualified] = module
            spec.loader.exec_module(module)
            modules[name] = module
        settings = json.loads((root / "config.json").read_text())
        settings.update(use_flash_attn=False, fused_bias_fc=False,
                        fused_dropout_add_ln=False, use_xentropy=False)
        config = modules["configuration_hf_nomic_bert"].NomicBertConfig(**settings)
        self.model = modules["modeling_hf_nomic_bert"].NomicBertModel(config, add_pooling_layer=False)
        self.model.load_state_dict(load_file(str(root / "model.fp16.safetensors")), strict=True)
        self.model.float().eval()
        self.tokenizer = BertTokenizerFast.from_pretrained(str(root), local_files_only=True)
        self.identity = {**profile, "runtime": {"torch": torch.__version__,
            "device": "cpu", "batch_size": batch_size, "threads": threads,
            "attention": "reviewed non-fused implementation", "normalization": "L2"}}
        self.last_metadata = {}

    def _encode(self, texts, *, queries):
        if not isinstance(texts, (tuple, list)) or len(texts) > 32:
            raise ValueError("Embedding inputs require a bounded text batch")
        prepared, metadata = [], []
        for original in texts:
            if not isinstance(original, str) or not original or len(original.encode()) > 32768:
                raise ValueError("Embedding input must be bounded nonempty text")
            text = (PREFIX if queries else "") + original
            complete = self.tokenizer(text, truncation=False, return_offsets_mapping=True,
                                      return_attention_mask=False, return_token_type_ids=False)
            used = self.tokenizer(text, truncation=True, max_length=512,
                                  return_offsets_mapping=True, return_attention_mask=False,
                                  return_token_type_ids=False)
            end = max((b for a, b in used["offset_mapping"]), default=0)
            prefix_size = len(PREFIX) if queries else 0
            original_end = max(0, end - prefix_size)
            truncated = len(complete["input_ids"]) > 512
            metadata.append({"input_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "input_tokens_with_special_and_prefix": len(complete["input_ids"]),
                "encoded_tokens": len(used["input_ids"]), "truncated": truncated,
                "included_character_end": original_end,
                "omitted_bytes": len(original[original_end:].encode()) if truncated else 0,
                "scope": "Encoding may omit trailing tokens; original source remains exact in the index"})
            prepared.append(text)
        result = []
        with self.torch.inference_mode():
            for start in range(0, len(prepared), self.batch_size):
                batch = self.tokenizer(prepared[start:start + self.batch_size], padding=True,
                    truncation=True, max_length=512, return_tensors="pt")
                output = self.model(**batch).last_hidden_state[:, 0]
                output = self.torch.nn.functional.normalize(output, p=2, dim=1)
                result.append(output.cpu().numpy().astype(np.float32))
        self.last_metadata = {"query_prefix_applied": queries, "max_tokens": 512,
                              "inputs": metadata}
        return np.concatenate(result) if result else np.empty((0, self.dimension), dtype=np.float32)

    def encode(self, texts):
        return self._encode(texts, queries=False)

    def encode_queries(self, texts):
        return self._encode(texts, queries=True)
