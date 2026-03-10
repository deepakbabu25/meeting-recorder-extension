"""
app/rag/vector_store.py

PostgreSQL + pgvector persistent vector store for meeting chunk retrieval.

Replaces the previous in-memory FAISS implementation. All embeddings are
now persisted to the `meeting_chunks` table using the pgvector extension.

Per-meeting pointer state (how many transcript turns have been indexed)
is still tracked in RAM via RAG_INDEX_STATE since it is only needed
during the live meeting session.
"""

import numpy as np
from typing import List, Dict, Any
from sqlalchemy import select, func, delete
from pgvector.sqlalchemy import Vector

from app.db.database import AsyncSessionLocal
from app.db.models import MeetingChunk
from app.state.meetings import RAG_INDEX_STATE

import uuid

EMBEDDING_DIM = 384   # all-MiniLM-L6-v2 output dimension
TOP_K_DEFAULT = 4     # chunks to retrieve per query


def _ensure_rag_state(meeting_id: str) -> None:
    """Initialise the per-meeting pointer dict if not already present."""
    if meeting_id not in RAG_INDEX_STATE:
        RAG_INDEX_STATE[meeting_id] = {
            "pointer": 0,
            "chunk_count": 0,
        }


async def add_chunks(meeting_id: str, chunks: List[Dict[str, Any]], embeddings: np.ndarray) -> None:
    """
    Persist new chunks and their embeddings to PostgreSQL via pgvector.

    Args:
        meeting_id:  The meeting session ID
        chunks:      List of chunk dicts from chunker.py
        embeddings:  numpy float32 array of shape (len(chunks), EMBEDDING_DIM)
    """
    _ensure_rag_state(meeting_id)

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    async with AsyncSessionLocal() as session:
        new_rows = []
        for i, chunk in enumerate(chunks):
            embedding_list = embeddings[i].tolist()
            new_rows.append(MeetingChunk(
                id=uuid.uuid4(),
                meeting_id=uuid.UUID(meeting_id),
                chunk_index=chunk.get("chunk_index", i),
                speakers=chunk.get("speakers", []),
                text=chunk.get("text", ""),
                start_time=chunk.get("start_time"),
                end_time=chunk.get("end_time"),
                embedding=embedding_list,
            ))
        session.add_all(new_rows)
        await session.commit()

    RAG_INDEX_STATE[meeting_id]["chunk_count"] += len(chunks)
    print(f"[pgvector] Saved {len(chunks)} chunks. Total: {RAG_INDEX_STATE[meeting_id]['chunk_count']}", flush=True)


async def search(meeting_id: str, query_embedding: np.ndarray, top_k: int = TOP_K_DEFAULT) -> List[Dict[str, Any]]:
    """
    Find the top-K most semantically similar chunks for a query using cosine similarity.

    Args:
        meeting_id:       The meeting session ID
        query_embedding:  1D or 2D float32 numpy array (384,)
        top_k:            Number of results to return

    Returns:
        List of chunk dicts (may be fewer than top_k if index is small)
    """
    if query_embedding.ndim == 2:
        query_embedding = query_embedding[0]

    query_list = query_embedding.tolist()

    async with AsyncSessionLocal() as session:
        stmt = (
            select(MeetingChunk)
            .where(MeetingChunk.meeting_id == uuid.UUID(meeting_id))
            .order_by(MeetingChunk.embedding.cosine_distance(query_list))
            .limit(top_k)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return [
        {
            "chunk_index": row.chunk_index,
            "speakers": row.speakers or [],
            "text": row.text,
            "start_time": row.start_time,
            "end_time": row.end_time,
        }
        for row in rows
    ]


async def has_chunks(meeting_id: str) -> bool:
    """Return True if at least one chunk has been indexed for this meeting."""
    async with AsyncSessionLocal() as session:
        stmt = select(func.count()).where(
            MeetingChunk.meeting_id == uuid.UUID(meeting_id)
        )
        result = await session.execute(stmt)
        count = result.scalar()
    return (count or 0) > 0


def get_pointer(meeting_id: str) -> int:
    """Return the incremental_transcript list index up to which we've processed."""
    state = RAG_INDEX_STATE.get(meeting_id)
    return state["pointer"] if state else 0


def set_pointer(meeting_id: str, pointer: int) -> None:
    """Update the pointer after processing new turns."""
    _ensure_rag_state(meeting_id)
    RAG_INDEX_STATE[meeting_id]["pointer"] = pointer


def get_chunk_count(meeting_id: str) -> int:
    """Return in-memory chunk count for this session (updated on every add_chunks call)."""
    state = RAG_INDEX_STATE.get(meeting_id)
    return state["chunk_count"] if state else 0


async def delete(meeting_id: str) -> None:
    """Remove all chunk rows for a meeting (cleanup after meeting ends)."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(MeetingChunk).where(MeetingChunk.meeting_id == uuid.UUID(meeting_id))
        )
        await session.commit()
    RAG_INDEX_STATE.pop(meeting_id, None)
