# app/api/meeting.py

from fastapi import APIRouter
from app.state.meetings import MEETING_STATE

router = APIRouter(prefix="/meeting")

@router.get("/latest")
async def get_latest_meeting():
    if not MEETING_STATE:
        return {"status": "NONE"}

    # Return the most recent meeting that is no longer actively recording.
    # This prevents one user from seeing another user's in-progress session.
    for meeting_id in reversed(list(MEETING_STATE.keys())):
        state = MEETING_STATE[meeting_id]
        if state.get("status") != "RECORDING":
            return {
                "status": "FOUND",
                "meeting_id": meeting_id,
                "state": state["status"]
            }

    return {"status": "NONE"}
