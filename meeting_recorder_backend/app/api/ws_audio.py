from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import DEEPGRAM_API_KEY
from app.state.meetings import MEETING_STATE
from app.services.meeting_summary import generate_meeting_summary
from app.rag.retriever import live_indexer, flush_remaining_turns
import asyncio
import uuid
import json
import numpy as np
import time
import websockets

router = APIRouter()

SAMPLE_RATE = 16000
MIN_WORDS_REQUIRED = 5

DEEPGRAM_URL = (
    f"wss://api.deepgram.com/v1/listen"
    f"?model=nova-2"           # Best accuracy model
    f"&encoding=linear16"
    f"&sample_rate={SAMPLE_RATE}"
    f"&channels=1"
    f"&interim_results=true"
    f"&smart_format=true"
    f"&diarize=true"
    f"&endpointing=500"        # Increased from 300ms → less mid-sentence cutoffs
    f"&utterance_end_ms=1000"  # Wait 1s of silence before finalising utterance
)


@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()
    meeting_id = str(uuid.uuid4())

    print(f"[{meeting_id}] WebSocket connection accepted", flush=True)

    await websocket.send_text(json.dumps({
        "type": "MEETING_STARTED",
        "meeting_id": meeting_id
    }))

    incremental_transcript: list[str] = []
    last_ping = time.time()
    meeting_ended = False
    indexer_task = None

    # ============================
    # CONNECT TO DEEPGRAM
    # ============================
    dg_headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_URL, additional_headers=dg_headers) as dg_ws:
            print(f"[{meeting_id}] Connected to Deepgram", flush=True)

            # ── Launch RAG live indexer ────────────────────────────────────
            async def _on_first_chunk():
                """Called by live_indexer when first chunk is indexed → enable chat in UI."""
                try:
                    await websocket.send_text(json.dumps({
                        "type": "CHAT_READY",
                        "meeting_id": meeting_id
                    }))
                    print(f"[{meeting_id}] CHAT_READY sent to frontend", flush=True)
                except Exception:
                    pass

            indexer_task = asyncio.create_task(
                live_indexer(meeting_id, incremental_transcript, on_first_chunk=_on_first_chunk)
            )

            # Task: receive transcripts from Deepgram and forward to extension
            async def receive_from_deepgram():
                nonlocal meeting_ended
                try:
                    async for message in dg_ws:
                        if isinstance(message, str):
                            data = json.loads(message)
                            msg_type = data.get("type", "")

                            if msg_type == "Results":
                                is_final = data.get("is_final", False)
                                try:
                                    alternative = data["channel"]["alternatives"][0]
                                    words = alternative.get("words", [])
                                    transcript = alternative.get("transcript", "")
                                except (KeyError, IndexError):
                                    words = []
                                    transcript = ""

                                if is_final and transcript.strip():
                                    # Build speaker-labelled segments from word-level diarization
                                    if words and any("speaker" in w for w in words):
                                        segments = []
                                        current_speaker = None
                                        current_words = []
                                        for w in words:
                                            spk = w.get("speaker", 0)
                                            if spk != current_speaker:
                                                if current_words:
                                                    segments.append(
                                                        f"Speaker {current_speaker + 1}: {' '.join(current_words)}"
                                                    )
                                                current_speaker = spk
                                                current_words = []
                                            current_words.append(w.get("punctuated_word") or w.get("word", ""))
                                        if current_words:
                                            segments.append(
                                                f"Speaker {current_speaker + 1}: {' '.join(current_words)}"
                                            )
                                        txt = "\n".join(segments)
                                    else:
                                        txt = transcript.strip()

                                    last = incremental_transcript[-1] if incremental_transcript else ""
                                    # Guard: last must be non-empty before dedup check.
                                    # "anything".endswith("") is ALWAYS True in Python!
                                    is_dup = last and (
                                        txt == last
                                        or last.endswith(txt)
                                        or txt.endswith(last)
                                    )
                                    if is_dup:
                                        print(f"[{meeting_id}] Skipping dup: '{txt[:50]}'")
                                    else:
                                        incremental_transcript.append(txt)
                                        print(f"[{meeting_id}] Live ✅: {txt}")
                                        try:
                                            await websocket.send_text(json.dumps({
                                                "type": "PARTIAL_TRANSCRIPT",
                                                "meeting_id": meeting_id,
                                                "text": txt
                                            }))
                                        except Exception:
                                            pass

                            elif msg_type == "Metadata":
                                print(f"[{meeting_id}] Deepgram metadata received")
                            elif msg_type == "Error":
                                print(f"[{meeting_id}] Deepgram error: {data}")
                except Exception as e:
                    if not meeting_ended:
                        print(f"[{meeting_id}] Deepgram receive error: {e}")

            dg_receiver = asyncio.create_task(receive_from_deepgram())

            try:
                while True:
                    try:
                        msg = await websocket.receive()
                    except (WebSocketDisconnect, RuntimeError):
                        break

                    # ── TEXT MESSAGES ──────────────────────────────────────────
                    if msg.get("text"):
                        data = json.loads(msg["text"])

                        if data.get("type") == "PING":
                            continue

                        if data.get("type") == "MEETING_END":
                            print(f"[{meeting_id}] Meeting end — closing Deepgram")
                            meeting_ended = True

                            # Tell Deepgram to flush remaining audio
                            try:
                                await dg_ws.send(json.dumps({"type": "CloseStream"}))
                                await asyncio.sleep(1.5)  # wait for final transcripts
                            except Exception:
                                pass

                            dg_receiver.cancel()

                            # ── Stop live indexer + flush remaining turns ──
                            if indexer_task and not indexer_task.done():
                                indexer_task.cancel()
                            await flush_remaining_turns(
                                meeting_id, incremental_transcript, on_first_chunk=_on_first_chunk
                            )

                            full_transcript = " ".join(
                                t.strip() for t in incremental_transcript if t.strip()
                            ).strip()

                            print(f"\n[{meeting_id}] ===== FINAL TRANSCRIPT =====")
                            print(full_transcript)
                            print(f"[{meeting_id}] ============================\n")

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

                            # ── Generate Summary ───────────────────────────────
                            word_count = len(full_transcript.split())
                            try:
                                if not full_transcript:
                                    MEETING_STATE[meeting_id]["final_summary"] = {
                                        "summary": "No discussion occurred in this meeting.",
                                        "key_points": [], "action_items": [], "decisions": []
                                    }
                                elif word_count < MIN_WORDS_REQUIRED:
                                    MEETING_STATE[meeting_id]["final_summary"] = {
                                        "summary": "Not enough information was recorded to generate a meaningful summary.",
                                        "key_points": [], "action_items": [], "decisions": []
                                    }
                                else:
                                    summary_result = await generate_meeting_summary(full_transcript)
                                    summary_dict = summary_result.model_dump()
                                    MEETING_STATE[meeting_id]["final_summary"] = {
                                        "summary": summary_dict.get("summary", ""),
                                        "key_points": summary_dict.get("key_points", []),
                                        "action_items": summary_dict.get("action_items", []),
                                        "decisions": summary_dict.get("decisions", [])
                                    }

                                MEETING_STATE[meeting_id]["status"] = "READY"
                                print(f"[{meeting_id}] Summary generated successfully")

                            except Exception as e:
                                print(f"[{meeting_id}] Summary generation failed: {e}")
                                MEETING_STATE[meeting_id]["final_summary"] = {
                                    "summary": "Meeting analysis completed, but summary could not be generated.",
                                    "key_points": [], "action_items": [], "decisions": []
                                }
                                MEETING_STATE[meeting_id]["status"] = "FAILED"

                            await websocket.close()
                            break

                    # ── AUDIO CHUNKS → forward to Deepgram ────────────────────
                    if msg.get("bytes"):
                        pcm_float = np.frombuffer(msg["bytes"], dtype=np.float32)
                        if pcm_float.size == 0:
                            continue

                        # Convert Float32 PCM → Int16 (Deepgram expects linear16)
                        pcm_int16 = (pcm_float * 32767).clip(-32768, 32767).astype(np.int16)
                        audio_bytes = pcm_int16.tobytes()
                        try:
                            await dg_ws.send(audio_bytes)
                        except Exception as e:
                            print(f"[{meeting_id}] Failed to send to Deepgram: {e}")

                        # Keep ngrok alive every 20s
                        now = time.time()
                        if now - last_ping >= 20:
                            try:
                                await websocket.send_text(json.dumps({"type": "KEEPALIVE"}))
                                last_ping = now
                            except Exception:
                                pass

            finally:
                dg_receiver.cancel()
                print(f"[{meeting_id}] Cleaned up")

    except Exception as e:
        print(f"[{meeting_id}] Failed to connect to Deepgram: {e}")
        await websocket.close()
