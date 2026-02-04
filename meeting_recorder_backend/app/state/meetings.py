import numpy as np

MEETING_TRANSCRIPTS: dict[str, list[str]] = {}
MEETING_PCM_BUFFERS = {}


# """
# Shared in-memory storage for active meeting sessions.

# Stores temporary audio buffers and transcription text for each
# ongoing meeting, keyed by meeting ID. Data is created when a
# meeting starts and removed when the meeting ends.
# """
