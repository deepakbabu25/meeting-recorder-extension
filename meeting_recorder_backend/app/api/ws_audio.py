from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.config import DEEPGRAM_API_KEY
from app.state.meetings import MEETING_STATE, get_meeting_state, save_meeting_state, clear_meeting_state
from app.services.meeting_summary import generate_meeting_summary
from app.rag.retriever import live_indexer, flush_remaining_turns
from app.core.security import verify_access_token
from app.db.database import AsyncSessionLocal
from app.db.models import Meeting, Transcript, MeetingSummary
from app.rag.parser import parse_turns
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
async def ws_audio(websocket: WebSocket, token: str = Query(None), meeting_id: str = Query(None)):
    await websocket.accept()
    
    is_reconnect = False
    if meeting_id:
        is_reconnect = True
        print(f"[{meeting_id}] Resuming existing connection...")
    else:
        meeting_id = str(uuid.uuid4())

    # Try to extract authenticated user
    user_id = None
    if token:
        user_id = verify_access_token(token)

    auth_status = "Authenticated" if user_id else "Guest"
    print(f"[{meeting_id}] WebSocket connection accepted ({auth_status})", flush=True)

    if not is_reconnect:
        await websocket.send_text(json.dumps({
            "type": "MEETING_STARTED",
            "meeting_id": meeting_id
        }))

    # ====== PERSISTENT RECOVERY ======
    m_state = get_meeting_state(meeting_id)
    if user_id:
        m_state["user_id"] = user_id
    incremental_transcript = m_state.setdefault("incremental_transcript", [])
    save_meeting_state(meeting_id)

    # ====== CREATE MEETING ROW EARLY (so RAG FK constraint is satisfied) ======
    # The Meeting row must exist BEFORE chunks are inserted by the live indexer.
    # We create it immediately at session start and update its status at the end.
    if user_id and not is_reconnect:
        try:
            async with AsyncSessionLocal() as session:
                new_meeting = Meeting(
                    id=uuid.UUID(meeting_id),
                    user_id=uuid.UUID(user_id),
                    title="Recorded Meeting",
                    status="IN_PROGRESS"
                )
                session.add(new_meeting)
                await session.commit()
                print(f"[{meeting_id}] Meeting row created in DB", flush=True)
        except Exception as db_start_err:
            print(f"[{meeting_id}] Could not pre-create meeting row: {db_start_err}")

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
            # To avoid recreating duplicate live indexers if it's a reconnect,
            # we check if one is already running. For simplicity now, we re-bind it 
            # to the current Websocket session so CHAT_READY events go to the right client.
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

            # Only launch indexer if not already running for this meeting (or if we lost it across WS drops)
            # In a robust system we'd track this in MEETING_STATE, but starting a new task mapped to the new WS avoids dead sockets.
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
                                        m_state["incremental_transcript"] = incremental_transcript
                                        save_meeting_state(meeting_id)
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

                            m_state["final_transcript"] = full_transcript
                            m_state["final_summary"] = None
                            m_state["status"] = "PROCESSING"
                            save_meeting_state(meeting_id)

                            await websocket.send_text(json.dumps({
                                "type": "MEETING_ENDED",
                                "meeting_id": meeting_id
                            }))

                            # ── Generate Summary ───────────────────────────────
                            word_count = len(full_transcript.split())
                            try:
                                if not full_transcript:
                                    m_state["final_summary"] = {
                                        "summary": "No discussion occurred in this meeting.",
                                        "key_points": [], "action_items": [], "decisions": []
                                    }
                                elif word_count < MIN_WORDS_REQUIRED:
                                    m_state["final_summary"] = {
                                        "summary": "Not enough information was recorded to generate a meaningful summary.",
                                        "key_points": [], "action_items": [], "decisions": []
                                    }
                                else:
                                    summary_result = await generate_meeting_summary(full_transcript)
                                    summary_dict = summary_result.model_dump()
                                    m_state["final_summary"] = {
                                        "summary": summary_dict.get("summary", ""),
                                        "key_points": summary_dict.get("key_points", []),
                                        "action_items": summary_dict.get("action_items", []),
                                        "decisions": summary_dict.get("decisions", [])
                                    }

                                m_state["status"] = "READY"
                                save_meeting_state(meeting_id)
                                print(f"[{meeting_id}] Summary generated successfully")

                            except Exception as e:
                                print(f"[{meeting_id}] Summary generation failed: {e}")
                                m_state["final_summary"] = {
                                    "summary": "Meeting analysis completed, but summary could not be generated.",
                                    "key_points": [], "action_items": [], "decisions": []
                                }
                                m_state["status"] = "FAILED"
                                save_meeting_state(meeting_id)

                            # ── PERSIST IF AUTHENTICATED ─────────────────────
                            if user_id:
                                print(f"[{meeting_id}] Saving authenticated meeting to DB...")
                                try:
                                    async with AsyncSessionLocal() as session:
                                        # Fetch existing row (created at session start)
                                        meeting_row = await session.get(Meeting, uuid.UUID(meeting_id))
                                        if meeting_row:
                                            meeting_row.status = m_state["status"]
                                        else:
                                            # Fallback: create if somehow missing
                                            meeting_row = Meeting(
                                                id=uuid.UUID(meeting_id),
                                                user_id=uuid.UUID(user_id),
                                                title="Recorded Meeting",
                                                status=m_state["status"]
                                            )
                                            session.add(meeting_row)

                                        # Parse the raw lines strictly into speakers
                                        all_turns = parse_turns(incremental_transcript)
                                        for t in all_turns:
                                            session.add(Transcript(
                                                meeting_id=new_meeting.id,
                                                speaker=t.get("speaker", "Unknown"),
                                                text=t.get("text", "")
                                            ))

                                        # Add Summary
                                        fin_sum = m_state["final_summary"]
                                        if fin_sum:
                                            session.add(MeetingSummary(
                                                meeting_id=new_meeting.id,
                                                summary_text=fin_sum.get("summary", ""),
                                                key_points=fin_sum.get("key_points", []),
                                                action_items=fin_sum.get("action_items", []),
                                                decisions=fin_sum.get("decisions", [])
                                            ))

                                        # Add Chat QA History
                                        chat_hist = m_state.get("chat_history", [])
                                        for qa in chat_hist:
                                            session.add(ChatMessage(
                                                meeting_id=new_meeting.id,
                                                role="user",
                                                content=qa.get("question", "")
                                            ))
                                            session.add(ChatMessage(
                                                meeting_id=new_meeting.id,
                                                role="assistant",
                                                content=qa.get("answer", "")
                                            ))

                                        await session.commit()
                                        print(f"[{meeting_id}] Successfully saved to PostgreSQL!")
                                except Exception as db_err:
                                    print(f"[{meeting_id}] DB Save Error: {db_err}")
                                
                                # Safe to delete cache after DB save!
                                clear_meeting_state(meeting_id)

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
