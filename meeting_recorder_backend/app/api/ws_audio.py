from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.stt.factory import get_stt_engine
from app.state.meetings import MEETING_TRANSCRIPTS
# from app.utils.audio_decode import webm_bytes_to_pcm
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

    stt_engine = get_stt_engine()
    # Initialize meeting state
    MEETING_TRANSCRIPTS[meeting_id] = []
    MEETING_AUDIO_BUFFERS[meeting_id] = np.array([], dtype=np.float32)

    try:
        while True:
            msg = await websocket.receive()

            #  MEETING END
            if msg["type"] == "websocket.disconnect":
                print(" WebSocket disconnect frame")
                break

            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "MEETING_END":
                    print(" MEETING_END received")
                    break

            # ===== AUDIO=====
            if "bytes" in msg:
                pcm_chunk=np.frombuffer(msg["bytes"],dtype=np.float32)
                if pcm_chunk.size ==0:
                    print("Received empty PCM chunk")
                    continue

               
    

                print("pcm max amplitude:", float(np.max(np.abs(pcm_chunk))))

                # ACCUMULATE AUDIO
                MEETING_AUDIO_BUFFERS[meeting_id] = np.concatenate(
                    [MEETING_AUDIO_BUFFERS[meeting_id], pcm_chunk]
                )

                duration_sec=len(MEETING_AUDIO_BUFFERS[meeting_id]) / 16000
                print("buffered seconds:", round(duration_sec,2))

                if duration_sec >= 8:
                    text = stt_engine.transcribe_pcm(
                        MEETING_AUDIO_BUFFERS[meeting_id]
                    )

                    if text:
                        MEETING_TRANSCRIPTS[meeting_id] = [text]
                        print(f"Transcribed so far: {text}")

    except WebSocketDisconnect:
        print("WebSocket disconnected unexpectedly")

    finally:
        pcm_audio = MEETING_AUDIO_BUFFERS.get(meeting_id)
        final_transcript = ""
        if pcm_audio is not None and len(pcm_audio) > 0:
            final_transcript = stt_engine.transcribe_pcm(pcm_audio)

        print("\n========== FINAL MEETING TRANSCRIPT ==========")
        print(final_transcript)
        print("==============================================\n")


        #calling service here
        if final_transcript.strip():
            print(" sending transcript to meeting agent...")

            summary_result=await generate_meeting_summary(final_transcript)

            print("========MEETING SUMMARY=========")
            print(summary_result)
            print("---------------------------------")
        MEETING_TRANSCRIPTS.pop(meeting_id, None)
        MEETING_AUDIO_BUFFERS.pop(meeting_id, None)
        print(f"Cleaned up meeting {meeting_id}")
