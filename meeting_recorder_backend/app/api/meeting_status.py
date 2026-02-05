from fastapi import APIRouter, HTTPException
from app.state.meetings import MEETING_STATE

router = APIRouter(prefix="/meeting", tags=["Meeting"])


@router.get("/{meeting_id}/status")
def get_meeting_status(meeting_id: str):
    if meeting_id not in MEETING_STATE:
        raise HTTPException(status_code=404, detail="meeting not found")
    return MEETING_STATE[meeting_id]