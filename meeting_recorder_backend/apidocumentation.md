@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    """
    WebSocket endpoint for real-time meeting audio transcription.

    This endpoint accepts a WebSocket connection from a client that streams
    raw PCM audio data (Float32, 16 kHz). Each connection is treated as an
    independent meeting session with a unique meeting ID.

    Workflow:
    1. Accepts a WebSocket connection and creates a unique meeting session.
    2. Initializes a speech-to-text (STT) engine for the session.
    3. Continuously receives messages from the client:
       - Binary messages containing PCM audio chunks.
       - Text messages for control signals (e.g., MEETING_END).
    4. Buffers incoming PCM audio per meeting.
    5. Once buffered audio exceeds a fixed duration threshold (e.g., 8 seconds),
       performs incremental transcription using the STT engine.
    6. On meeting end or disconnection, performs a final transcription pass.
    7. Cleans up all in-memory buffers and session state.

    Message Types:
    - Binary (`bytes`): Float32 PCM audio chunks at 16 kHz.
    - Text (`text`): JSON control messages (e.g., {"type": "MEETING_END"}).

    Session State:
    - MEETING_AUDIO_BUFFERS: Stores accumulated PCM audio per meeting.
    - MEETING_TRANSCRIPTS: Stores partial or final transcription text.

    Notes:
    - This endpoint is designed for streaming use cases (e.g., live meetings).
    - Audio buffering and transcription are done per WebSocket connection.
    - Long-running transcription work can later be offloaded to background
      workers (e.g., Celery) if needed for scalability.

    Args:
        websocket (WebSocket): Active WebSocket connection from the client.
    """
