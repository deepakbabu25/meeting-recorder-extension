"""
app/rag/vector_store.py

In-memory FAISS vector store for meeting chunk retrieval.

This is THE single swap point for future PostgreSQL + pgvector migration.
Everything above this layer (retriever, chunker, embedder) remains unchanged.

Per-meeting state stored in RAG_INDEX_STATE (from state/meetings.py):
  {
    "index":    faiss.IndexFlatIP,   # cosine similarity (normalized vectors)
    "chunks":   List[Dict],          # chunk metadata in insertion order
    "pointer":  int,                 # how many turns from incremental_transcript have been processed
    "chunk_count": int,              # total indexed chunks so far
  }
"""

import numpy as np
import faiss
from typing import List, Dict, Any, Optional
from app.state.meetings import RAG_INDEX_STATE

EMBEDDING_DIM = 384   # all-MiniLM-L6-v2 output dimension
TOP_K_DEFAULT = 4     # chunks to retrieve per query


def _ensure_index(meeting_id: str) -> None:
    """Initialise the per-meeting state dict if not already present."""
    if meeting_id not in RAG_INDEX_STATE:
        RAG_INDEX_STATE[meeting_id] = {
            "index": faiss.IndexFlatIP(EMBEDDING_DIM),  # inner product = cosine for normalised vecs
            "chunks": [],
            "pointer": 0,       # index into incremental_transcript list
            "chunk_count": 0,
        }


def add_chunks(meeting_id: str, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
    """
    Add new chunks + their embeddings to the FAISS index.

    Args:
        meeting_id:  The meeting session ID
        chunks:      List of chunk dicts from chunker.py
        embeddings:  numpy float32 array of shape (len(chunks), EMBEDDING_DIM)
    """
    _ensure_index(meeting_id)
    state = RAG_INDEX_STATE[meeting_id]

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    state["index"].add(embeddings)
    state["chunks"].extend(chunks)
    state["chunk_count"] += len(chunks)


def search(meeting_id: str, query_embedding: np.ndarray, top_k: int = TOP_K_DEFAULT) -> List[Dict[str, Any]]:
    """
    Find the top-K most semantically similar chunks for a query.

    Args:
        meeting_id:       The meeting session ID
        query_embedding:  1D or 2D float32 numpy array (384,)
        top_k:            Number of results to return

    Returns:
        List of chunk dicts (may be fewer than top_k if index is small)
    """
    state = RAG_INDEX_STATE.get(meeting_id)
    if not state or state["chunk_count"] == 0:
        return []

    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)

    actual_k = min(top_k, state["chunk_count"])
    _, indices = state["index"].search(query_embedding, actual_k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(state["chunks"]):
            results.append(state["chunks"][idx])
    return results


def has_chunks(meeting_id: str) -> bool:
    """Return True if at least one chunk has been indexed for this meeting."""
    state = RAG_INDEX_STATE.get(meeting_id)
    return bool(state and state["chunk_count"] > 0)


def get_pointer(meeting_id: str) -> int:
    """Return the incremental_transcript list index up to which we've already processed."""
    state = RAG_INDEX_STATE.get(meeting_id)
    return state["pointer"] if state else 0


def set_pointer(meeting_id: str, pointer: int) -> None:
    """Update the pointer after processing new turns."""
    _ensure_index(meeting_id)
    RAG_INDEX_STATE[meeting_id]["pointer"] = pointer


def get_chunk_count(meeting_id: str) -> int:
    state = RAG_INDEX_STATE.get(meeting_id)
    return state["chunk_count"] if state else 0


def delete(meeting_id: str) -> None:
    """Remove all RAG state for a meeting (cleanup)."""
    RAG_INDEX_STATE.pop(meeting_id, None)
