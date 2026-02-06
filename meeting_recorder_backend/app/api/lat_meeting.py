# app/api/meeting.py

from fastapi import APIRouter
from app.state.meetings import MEETING_STATE

router = APIRouter(prefix="/meeting")

@router.get("/latest")
async def get_latest_meeting():
    if not MEETING_STATE:
        return {"status": "NONE"}

    # get last inserted meeting
    meeting_id = list(MEETING_STATE.keys())[-1]
    return {
        "status": "FOUND",
        "meeting_id": meeting_id,
        "state": MEETING_STATE[meeting_id]["status"]
    }
