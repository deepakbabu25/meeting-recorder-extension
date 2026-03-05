"""
app/rag/embedder.py

Loads the sentence-transformer model once at module import time
and exposes a simple encode() function used by the rest of the RAG pipeline.

Model: all-MiniLM-L6-v2
  - ~80MB, runs on CPU, no API key needed
  - 384-dimensional embeddings
  - Good balance of speed and quality for semantic search
"""

import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer

# Load once at startup — not per request
_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[RAG] Loading embedding model: {_MODEL_NAME}")
        _model = SentenceTransformer(_MODEL_NAME)
        print(f"[RAG] Embedding model loaded ✅")
    return _model


def encode(texts: Union[str, List[str]]) -> np.ndarray:
    """
    Encode one or more texts into embedding vectors.

    Args:
        texts: A single string or list of strings.

    Returns:
        numpy array of shape (n, 384) — float32
    """
    model = _get_model()
    if isinstance(texts, str):
        texts = [texts]
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype(np.float32)
