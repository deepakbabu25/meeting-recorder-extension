"""
app/rag/parser.py

Parses raw transcript lines (as produced by ws_audio.py) into
structured speaker-turn dicts.

Input format (each element in incremental_transcript list):
  "Speaker 1: Let's discuss the deadline..."
  "Speaker 2: I think two more weeks..."
  or plain text (no speaker label) if diarization was off

Output:
  [{"speaker": "Speaker 1", "text": "Let's discuss the deadline...", "index": 0}, ...]
"""

import re
from typing import List, Dict, Any

SPEAKER_PATTERN = re.compile(r"^(Speaker\s+\d+):\s*(.+)$", re.DOTALL)


def parse_turns(incremental_transcript: List[str], start_index: int = 0) -> List[Dict[str, Any]]:
    """
    Parse a slice of the incremental_transcript list into structured turns.

    Args:
        incremental_transcript: The full list of transcript strings.
        start_index: Position to start parsing from (for incremental updates).

    Returns:
        List of turn dicts: {speaker, text, index}
    """
    turns = []
    for i, line in enumerate(incremental_transcript[start_index:], start=start_index):
        line = line.strip()
        if not line:
            continue

        # Handle multi-speaker segments (newline-separated within one entry)
        sub_lines = line.split("\n")
        for sub in sub_lines:
            sub = sub.strip()
            if not sub:
                continue
            match = SPEAKER_PATTERN.match(sub)
            if match:
                turns.append({
                    "speaker": match.group(1).strip(),
                    "text": match.group(2).strip(),
                    "index": i,
                })
            else:
                # No speaker label — treat as unknown speaker
                turns.append({
                    "speaker": "Unknown",
                    "text": sub,
                    "index": i,
                })
    return turns
