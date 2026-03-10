import os
import json

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".cache_sessions"))
os.makedirs(CACHE_DIR, exist_ok=True)

MEETING_TRANSCRIPTS: dict[str, list[str]] = {}
MEETING_PCM_BUFFERS = {}
MEETING_STATE = {}
RAG_INDEX_STATE = {}   # meeting_id → {index, chunks, pointer, chunk_count}

def get_meeting_state(meeting_id: str) -> dict:
    if meeting_id in MEETING_STATE:
        return MEETING_STATE[meeting_id]
        
    path = os.path.join(CACHE_DIR, f"{meeting_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
                MEETING_STATE[meeting_id] = state
                return state
        except Exception:
            pass
            
    # Default empty state
    state = {
        "status": "LIVE",
        "chat_history": [],
        "incremental_transcript": [],
        "user_id": None
    }
    MEETING_STATE[meeting_id] = state
    return state

def save_meeting_state(meeting_id: str):
    if meeting_id in MEETING_STATE:
        path = os.path.join(CACHE_DIR, f"{meeting_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(MEETING_STATE[meeting_id], f)
        except Exception as e:
            print(f"Error saving state: {e}")

def clear_meeting_state(meeting_id: str):
    if meeting_id in MEETING_STATE:
        del MEETING_STATE[meeting_id]
    path = os.path.join(CACHE_DIR, f"{meeting_id}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
