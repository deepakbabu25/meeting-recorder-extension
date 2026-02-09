from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.stt.factory import get_stt_engine
from app.state.meetings import MEETING_STATE
from app.services.meeting_summary import generate_meeting_summary
import uuid
import json
import numpy as np

router = APIRouter()


# AUDIO CONFIG

SAMPLE_RATE = 16000
CHUNK_SEC = 30
OVERLAP_SEC = 5

CHUNK_SAMPLES = CHUNK_SEC * SAMPLE_RATE
OVERLAP_SAMPLES = OVERLAP_SEC * SAMPLE_RATE
STEP_SAMPLES = CHUNK_SAMPLES - OVERLAP_SAMPLES

MEETING_AUDIO_BUFFERS = {}


@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()
    meeting_id = str(uuid.uuid4())

    print(f" WebSocket connection accepted for meeting {meeting_id}")

    await websocket.send_text(json.dumps({
        "type": "MEETING_STARTED",
        "meeting_id": meeting_id
    }))

    stt_engine = get_stt_engine()
    MEETING_AUDIO_BUFFERS[meeting_id] = np.array([], dtype=np.float32)
    incremental_transcript: list[str] = []

    try:
        while True:
            # 🔒 SAFE RECEIVE (FIX #1)
            try:
                msg = await websocket.receive()
            except (WebSocketDisconnect, RuntimeError):
                break

            # ============================
            # MEETING END
            # ============================
            if msg.get("text"):
                data = json.loads(msg["text"])

                if data.get("type") == "MEETING_END":
                    print("Meeting end received")

                    buffer = MEETING_AUDIO_BUFFERS.get(meeting_id)
                    final_text = ""

                    # Transcribe ONLY new audio beyond overlap
                    if buffer is not None and len(buffer) > OVERLAP_SAMPLES:
                        final_text = stt_engine.transcribe_pcm(
                            buffer[OVERLAP_SAMPLES:]
                        )

                    full_transcript = " ".join(
                        t.strip() for t in incremental_transcript if t.strip()
                    )

                    if final_text:
                        full_transcript = (
                            full_transcript + " " + final_text
                            if full_transcript else final_text
                        )

                    MEETING_STATE[meeting_id] = {
                        "final_transcript": full_transcript.strip(),
                        "final_summary": None,
                        "chat_history": [],
                        "status": "PROCESSING"
                    }

                    await websocket.send_text(json.dumps({
                        "type": "MEETING_ENDED",
                        "meeting_id": meeting_id
                    }))

                    print("\n========== FINAL TRANSCRIPT ==========")
                    print(full_transcript)
                    print("=====================================\n")

                    if full_transcript.strip():
                        print("Generating meeting summary...")
                        summary_result = await generate_meeting_summary(full_transcript)

                        MEETING_STATE[meeting_id]["final_summary"] = (
                            summary_result.model_dump()
                        )
                        MEETING_STATE[meeting_id]["status"] = "READY"

                        print(" Summary generated and stored")

                    # 🔒 CLOSE SOCKET + EXIT LOOP (FIX #2)
                    await websocket.close()
                    break

            # ============================
            # AUDIO CHUNKS
            # ============================
            if msg.get("bytes"):
                pcm_chunk = np.frombuffer(msg["bytes"], dtype=np.float32)
                if pcm_chunk.size == 0:
                    continue

                MEETING_AUDIO_BUFFERS[meeting_id] = np.concatenate(
                    [MEETING_AUDIO_BUFFERS[meeting_id], pcm_chunk]
                )

                buffer = MEETING_AUDIO_BUFFERS[meeting_id]
                print("Buffered seconds:", round(len(buffer) / SAMPLE_RATE, 2))

                while len(buffer) >= CHUNK_SAMPLES:
                    chunk = buffer[:CHUNK_SAMPLES]

                    text = stt_engine.transcribe_pcm(chunk)
                    if text:
                        print("Transcribed chunk:", text)
                        incremental_transcript.append(text)

                        await websocket.send_text(json.dumps({
                            "type": "PARTIAL_TRANSCRIPT",
                            "meeting_id": meeting_id,
                            "text": text
                        }))

                    buffer = buffer[STEP_SAMPLES:]
                    MEETING_AUDIO_BUFFERS[meeting_id] = buffer

    finally:
        MEETING_AUDIO_BUFFERS.pop(meeting_id, None)
        print(f" Cleaned up meeting {meeting_id}")
