"""
app/rag/retriever.py

Orchestrates the full RAG pipeline:
  1. live_indexer()         — async background task that indexes chunks during the meeting
  2. flush_remaining_turns() — called on MEETING_END to index any leftover turns
  3. retrieve_context()      — called by chat_service to get relevant context for a question

This is the only file ws_audio.py and chat_service.py need to import from the RAG layer.
"""

import asyncio
import logging
from typing import List, Optional, Callable, Awaitable

from app.rag.parser import parse_turns
from app.rag.chunker import build_chunks, get_pending_turns, MIN_TURNS_PER_CHUNK
from app.rag.embedder import encode
from app.rag import vector_store as vs

logger = logging.getLogger(__name__)

# How often (seconds) the indexer polls for new turns during the meeting
POLL_INTERVAL_SECONDS = 15


async def live_indexer(
    meeting_id: str,
    incremental_transcript: List[str],
    on_first_chunk: Optional[Callable[[], Awaitable[None]]] = None,
) -> None:
    """
    Background async task: watches incremental_transcript grow and indexes
    chunks as they accumulate. Meant to run as asyncio.create_task().

    Args:
        meeting_id:           The meeting session ID
        incremental_transcript: The shared list that ws_audio.py appends to
        on_first_chunk:       Optional async callback fired when the first chunk
                              is indexed (used to send CHAT_READY to frontend)
    """
    print(f"\n[RAG][{meeting_id}]  Live indexer started - polling every {POLL_INTERVAL_SECONDS}s", flush=True)
    first_chunk_fired = False

    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            await _index_new_turns(meeting_id, incremental_transcript)

            # Fire CHAT_READY as soon as we have at least one chunk
            if not first_chunk_fired and vs.has_chunks(meeting_id):
                first_chunk_fired = True
                print(f"[RAG][{meeting_id}]  First chunk indexed — chat is now available!", flush=True)
                if on_first_chunk:
                    try:
                        await on_first_chunk()
                    except Exception as e:
                        print(f"[RAG][{meeting_id}]  on_first_chunk callback failed: {e}", flush=True)

    except asyncio.CancelledError:
        print(f"[RAG][{meeting_id}]  Live indexer cancelled", flush=True)


async def flush_remaining_turns(
    meeting_id: str,
    incremental_transcript: List[str],
    on_first_chunk: Optional[Callable[[], Awaitable[None]]] = None,
) -> None:
    """
    Called on MEETING_END to index any turns not yet processed by live_indexer.
    Also handles cases where the meeting was so short that live_indexer never
    fired (total turns < MIN_TURNS_PER_CHUNK).
    """
    print(f"\n[RAG][{meeting_id}]  Flushing remaining turns before generating summary...", flush=True)
    first_had_chunks = vs.has_chunks(meeting_id)

    await _index_new_turns(meeting_id, incremental_transcript, force=True)

    if not first_had_chunks and vs.has_chunks(meeting_id) and on_first_chunk:
        try:
            await on_first_chunk()
        except Exception as e:
            print(f"[RAG][{meeting_id}]  on_first_chunk (flush) callback failed: {e}", flush=True)

    print(f"[RAG][{meeting_id}]  Flush complete. Total RAG chunks ready: {vs.get_chunk_count(meeting_id)}\n", flush=True)


async def _index_new_turns(
    meeting_id: str,
    incremental_transcript: List[str],
    force: bool = False,
) -> None:
    """
    Internal: parse unprocessed turns, build chunks, embed, and store.

    Args:
        force: If True, index even a partial (sub-minimum) chunk at the end.
               Used during flush on MEETING_END.
    """
    pointer = vs.get_pointer(meeting_id)
    total_turns_now = len(incremental_transcript)

    if total_turns_now <= pointer:
        return  # nothing new since last poll

    # Parse only new turns
    all_turns = parse_turns(incremental_transcript)

    if not all_turns:
        return

    # Get pending window (includes overlap from previous chunk)
    pending_turns, overlap_start = get_pending_turns(all_turns, pointer)

    if not pending_turns:
        return

    # Check we have enough turns for at least one chunk (unless forced)
    new_turn_count = len(all_turns) - pointer
    if not force and new_turn_count < MIN_TURNS_PER_CHUNK:
        return

    chunk_offset = vs.get_chunk_count(meeting_id)
    chunks = build_chunks(pending_turns, chunk_offset=chunk_offset)

    if not chunks:
        return

    # Embed all chunks (batch call — efficient)
    texts = [c["text"] for c in chunks]
    embeddings = encode(texts)

    # Add to FAISS index
    vs.add_chunks(meeting_id, chunks, embeddings)

    # Update pointer to the last turn we processed
    new_pointer = all_turns[-1]["index"] + 1
    vs.set_pointer(meeting_id, new_pointer)

    print(
        f"[RAG][{meeting_id}]  Transformed {len(pending_turns)} turns -> {len(chunks)} chunk(s). "
        f"Total chunks in FAISS index: {vs.get_chunk_count(meeting_id)}", flush=True
    )


def retrieve_context(meeting_id: str, question: str, top_k: int = 4) -> str:
    """
    Retrieve the most relevant transcript chunks for a question.
    Returns a formatted string ready to inject as LLM context.

    Args:
        meeting_id: The meeting session ID
        question:   The user's question
        top_k:      Number of chunks to retrieve

    Returns:
        Formatted context string, or empty string if no chunks indexed yet
    """
    if not vs.has_chunks(meeting_id):
        return ""

    query_embedding = encode(question)[0]
    chunks = vs.search(meeting_id, query_embedding, top_k=top_k)

    print(f"\n[RAG][{meeting_id}] 🔍 Found {len(chunks)} relevant chunk(s) for query: '{question}'", flush=True)

    if not chunks:
        return ""

    parts = []
    for i, chunk in enumerate(chunks, 1):
        speakers = ", ".join(chunk.get("speakers", []))
        parts.append(
            f"[Excerpt {i} | Speakers: {speakers}]\n{chunk['text']}"
        )

    return "\n\n---\n\n".join(parts)
