from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.stt.factory import get_stt_engine
from app.state.meetings import MEETING_STATE
from app.services.meeting_summary import generate_meeting_summary
import uuid
import json
import numpy as np
import time

router = APIRouter()

# ============================
# AUDIO CONFIG
# ============================

SAMPLE_RATE = 16000
CHUNK_SEC = 18
OVERLAP_SEC = 3

CHUNK_SAMPLES = CHUNK_SEC * SAMPLE_RATE
OVERLAP_SAMPLES = OVERLAP_SEC * SAMPLE_RATE
STEP_SAMPLES = CHUNK_SAMPLES - OVERLAP_SAMPLES

CHUNKS_PER_SUMMARY = 10
MIN_WORDS_REQUIRED = 5  # Stronger than char length check

MEETING_AUDIO_BUFFERS = {}


@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()
    meeting_id = str(uuid.uuid4())

    print(f"[{meeting_id}] WebSocket connection accepted")

    await websocket.send_text(json.dumps({
        "type": "MEETING_STARTED",
        "meeting_id": meeting_id
    }))

    stt_engine = get_stt_engine()
    MEETING_AUDIO_BUFFERS[meeting_id] = np.array([], dtype=np.float32)

    incremental_transcript: list[str] = []
    partial_summaries: list[str] = []
    last_ping = time.time()  # track last server→client keepalive

    try:
        while True:
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
                    print(f"[{meeting_id}] Meeting end received")

                    buffer = MEETING_AUDIO_BUFFERS.get(meeting_id)
                    final_text = ""

                    if buffer is not None and len(buffer) > OVERLAP_SAMPLES:
                        try:
                            final_text = stt_engine.transcribe_pcm(
                                buffer[OVERLAP_SAMPLES:]
                            )
                        except Exception as e:
                            print(f"[{meeting_id}] Final transcription failed:", str(e))

                    if final_text:
                        incremental_transcript.append(final_text)

                    full_transcript = " ".join(
                        t.strip() for t in incremental_transcript if t.strip()
                    ).strip()

                    print(f"\n[{meeting_id}] ========== FINAL TRANSCRIPT ==========")
                    print(full_transcript)
                    print(f"[{meeting_id}] =====================================\n")

                    MEETING_STATE[meeting_id] = {
                        "final_transcript": full_transcript,
                        "final_summary": None,
                        "chat_history": [],
                        "status": "PROCESSING"
                    }

                    await websocket.send_text(json.dumps({
                        "type": "MEETING_ENDED",
                        "meeting_id": meeting_id
                    }))

                    print(f"[{meeting_id}] Generating final summary...")

                    word_count = len(full_transcript.split())

                    try:
                        # ============================
                        # CASE 1: No speech
                        # ============================
                        if not full_transcript:
                            MEETING_STATE[meeting_id]["final_summary"] = {
                                "summary": "No discussion occurred in this meeting.",
                                "key_points": [],
                                "action_items": [],
                                "decisions": []
                            }

                        # ============================
                        # CASE 2: Too short
                        # ============================
                        elif word_count < MIN_WORDS_REQUIRED:
                            MEETING_STATE[meeting_id]["final_summary"] = {
                                "summary": "Not enough information was recorded to generate a meaningful summary.",
                                "key_points": [],
                                "action_items": [],
                                "decisions": []
                            }

                        # ============================
                        # CASE 3: Normal meeting
                        # ============================
                        else:
                            if partial_summaries:
                                combined_partial = "\n".join(
                                    s for s in partial_summaries if s.strip()
                                )
                                source_text = combined_partial if combined_partial else full_transcript
                            else:
                                source_text = full_transcript

                            summary_result = await generate_meeting_summary(source_text)
                            summary_dict = summary_result.model_dump()

                            # Ensure structure safety
                            MEETING_STATE[meeting_id]["final_summary"] = {
                                "summary": summary_dict.get("summary", ""),
                                "key_points": summary_dict.get("key_points", []),
                                "action_items": summary_dict.get("action_items", []),
                                "decisions": summary_dict.get("decisions", [])
                            }

                        MEETING_STATE[meeting_id]["status"] = "READY"
                        print(f"[{meeting_id}] Final summary generated successfully")

                    except Exception as e:
                        print(f"[{meeting_id}] Summary generation failed:", str(e))
                        MEETING_STATE[meeting_id]["final_summary"] = {
                            "summary": "Meeting analysis completed, but summary could not be generated.",
                            "key_points": [],
                            "action_items": [],
                            "decisions": []
                        }
                        MEETING_STATE[meeting_id]["status"] = "FAILED"

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
                print(f"[{meeting_id}]Buffered seconds:", round(len(buffer) / SAMPLE_RATE, 2))

                # Server→client keepalive every 20s to keep ngrok tunnel alive
                now = time.time()
                if now - last_ping >= 20:
                    try:
                        await websocket.send_text(json.dumps({"type": "KEEPALIVE"}))
                        last_ping = now
                    except Exception:
                        pass

                while len(buffer) >= CHUNK_SAMPLES:
                    chunk = buffer[:CHUNK_SAMPLES]

                    try:
                        text = stt_engine.transcribe_pcm(chunk)
                    except Exception as e:
                        print(f"[{meeting_id}] Chunk transcription failed:", str(e))
                        text = ""

                    if text:
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
        print(f"[{meeting_id}] Cleaned up")
