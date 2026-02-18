from fastapi import APIRouter
from app.state.meetings import MEETING_STATE

router = APIRouter(prefix="/meeting", tags=["Meeting"])


@router.get("/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    meeting = MEETING_STATE.get(meeting_id)

    if not meeting:
        return {
            "status": "NOT_FOUND",
            "summary": {
                "summary": "Meeting not found.",
                "key_points": [],
                "action_items": [],
                "decisions": []
            }
        }

    status = meeting.get("status")

    if status == "PROCESSING":
        return {
            "status": "PROCESSING"
        }

    if status == "FAILED":
        return {
            "status": "FAILED",
            "summary": meeting.get("final_summary")
        }

    return {
        "status": "READY",
        "meeting_id": meeting_id,
        "summary": meeting.get("final_summary")
    }
