from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.stt.factory import get_stt_engine
from app.state.meetings import MEETING_TRANSCRIPTS, MEETING_STATE
from app.services.meeting_summary import generate_meeting_summary
import uuid
import json
import numpy as np

router = APIRouter()

# PCM buffer per meeting
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

    try:
        while True:
            msg = await websocket.receive()

            # ===== MEETING END =====
            if msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "MEETING_END":
                    print("🔚 MEETING_END received")

                    pcm_audio = MEETING_AUDIO_BUFFERS.get(meeting_id)
                    final_transcript = ""

                    if pcm_audio is not None and len(pcm_audio) > 0:
                        final_transcript = stt_engine.transcribe_pcm(pcm_audio)

                    print("\n========== FINAL TRANSCRIPT ==========")
                    print(final_transcript)
                    print("=====================================\n")

                    if final_transcript.strip():
                        print("Generating meeting summary...")
                        summary_result = await generate_meeting_summary(final_transcript)
                        print(summary_result)

                        await websocket.send_text(json.dumps({
                            "type": "MEETING_SUMMARY",
                            "meeting_id": meeting_id,
                            "summary": summary_result.model_dump()
                        }))

                        print(" Summary sent to client")

                    break  #  exit loop AFTER sending summary

            # ===== AUDIO =====
            if msg.get("bytes"):
                pcm_chunk = np.frombuffer(msg["bytes"], dtype=np.float32)
                if pcm_chunk.size == 0:
                    continue

                MEETING_AUDIO_BUFFERS[meeting_id] = np.concatenate(
                    [MEETING_AUDIO_BUFFERS[meeting_id], pcm_chunk]
                )

                duration_sec = len(MEETING_AUDIO_BUFFERS[meeting_id]) / 16000
                print("buffered seconds:", round(duration_sec, 2))

                if duration_sec >= 8:
                    text = stt_engine.transcribe_pcm(MEETING_AUDIO_BUFFERS[meeting_id])
                    if text:
                        print("Transcribed so far:", text)

    except WebSocketDisconnect:
        print("🔌 Client disconnected")

    finally:
        MEETING_AUDIO_BUFFERS.pop(meeting_id, None)
        print(f"🧹 Cleaned up meeting {meeting_id}")
