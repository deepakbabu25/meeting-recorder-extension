"""
app/rag/chunker.py

Sliding-window conversation chunker.

Takes a list of speaker turns and groups them into overlapping
windows of 3-8 turns (or ~200-350 words), with 1-2 turn overlap
between consecutive chunks to avoid losing context at boundaries.
"""

from typing import List, Dict, Any, Tuple

# Tunable parameters
MIN_TURNS_PER_CHUNK = 3
MAX_TURNS_PER_CHUNK = 8
TARGET_WORDS = 275        # aim for this word count per chunk
OVERLAP_TURNS = 2         # how many turns to share with next chunk


def _count_words(turns: List[Dict[str, Any]]) -> int:
    return sum(len(t["text"].split()) for t in turns)


def _turns_to_text(turns: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)


def _speakers_in(turns: List[Dict[str, Any]]) -> List[str]:
    seen = []
    for t in turns:
        if t["speaker"] not in seen:
            seen.append(t["speaker"])
    return seen


def build_chunks(turns: List[Dict[str, Any]], chunk_offset: int = 0) -> List[Dict[str, Any]]:
    """
    Build overlapping conversation window chunks from a list of turns.

    Args:
        turns: List of {speaker, text, index} dicts from parser.py
        chunk_offset: Starting chunk index (for incremental builds)

    Returns:
        List of chunk dicts:
          {
            chunk_index, text, speakers, turn_start, turn_end, word_count
          }
    """
    if not turns:
        return []

    chunks = []
    i = 0
    chunk_idx = chunk_offset

    while i < len(turns):
        window = []
        j = i

        # Grow window until max turns or target words reached
        while j < len(turns) and (
            len(window) < MIN_TURNS_PER_CHUNK
            or (len(window) < MAX_TURNS_PER_CHUNK and _count_words(window) < TARGET_WORDS)
        ):
            window.append(turns[j])
            j += 1

        if not window:
            break

        chunk = {
            "chunk_index": chunk_idx,
            "text": _turns_to_text(window),
            "speakers": _speakers_in(window),
            "turn_start": window[0]["index"],
            "turn_end": window[-1]["index"],
            "word_count": _count_words(window),
        }
        chunks.append(chunk)
        chunk_idx += 1

        # Slide forward, keeping OVERLAP_TURNS turns from end of this window
        advance = max(1, len(window) - OVERLAP_TURNS)
        i += advance

    return chunks


def get_pending_turns(
    all_turns: List[Dict[str, Any]],
    already_chunked_turn_index: int
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Return the subset of turns not yet chunked, with overlap prepended.

    Args:
        all_turns: Full list of parsed turns so far
        already_chunked_turn_index: The list index (in all_turns) up to which
                                    we've already chunked

    Returns:
        (turns_to_process, new_already_chunked_index)
        where turns_to_process includes OVERLAP_TURNS for overlap continuity.
    """
    if already_chunked_turn_index == 0:
        return all_turns, 0

    # Include OVERLAP_TURNS from the last chunk for sliding window continuity
    overlap_start = max(0, already_chunked_turn_index - OVERLAP_TURNS)
    return all_turns[overlap_start:], overlap_start
