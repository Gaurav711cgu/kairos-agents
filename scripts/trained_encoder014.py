"""Use the measured retrieval head for both indexed code and live query vectors."""
import copy
import hashlib
from pathlib import Path
from scripts.build_functions014 import canonical


class TrainedCodeEncoder014:
    dimension = 768

    def __init__(self, base_encoder, adapter_directory, manifest_sha256):
        from scripts.retrieval_adapter014 import APPROVED_PROFILE_SHA256, load_inference_projection
        profile = {k: v for k, v in base_encoder.identity.items() if k != 'runtime'}
        if hashlib.sha256(canonical(profile)).hexdigest() != APPROVED_PROFILE_SHA256:
            raise ValueError('Trained head requires its exact frozen base encoder profile')
        if getattr(base_encoder, 'dimension', None) != self.dimension:
            raise ValueError('Base encoder dimension differs')
        self.head, artifact = load_inference_projection(Path(adapter_directory), manifest_sha256)
        self.base = base_encoder
        self.identity = {**copy.deepcopy(base_encoder.identity), 'learned_projection014': {
            'manifest_sha256': manifest_sha256, 'dimension': self.dimension,
            'rank': artifact['config']['rank'], 'selected_step': artifact['config']['selected_step'],
            'transform': artifact['config']['transform'], 'applies_to': ['code', 'query']}}
        self.last_metadata = {}

    def _encode(self, texts, queries):
        import numpy as np
        import torch
        method = self.base.encode_queries if queries else self.base.encode
        vectors = np.asarray(method(texts), dtype=np.float32)
        if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
            raise ValueError('Base encoder returned invalid vectors')
        if len(vectors) and not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=0.01):
            raise ValueError('Base encoder vectors must be normalized')
        with torch.no_grad():
            projected = self.head(torch.from_numpy(vectors)).cpu().numpy()
        if not np.isfinite(projected).all():
            raise ValueError('Trained projection returned invalid vectors')
        self.last_metadata = {**copy.deepcopy(self.base.last_metadata),
            'learned_projection014': {**self.identity['learned_projection014'], 'role': 'query' if queries else 'code'}}
        return projected

    def encode(self, texts):
        return self._encode(texts, False)

    def encode_queries(self, texts):
        return self._encode(texts, True)
