from fastapi import APIRouter
from app.state.meetings import MEETING_STATE

router = APIRouter(prefix="/meeting", tags=["Meeting"])


@router.get("/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    meeting = MEETING_STATE.get(meeting_id)

    if not meeting:
        return {"status": "NOT_FOUND"}
    
    status = meeting["status"]
    if status == "PROCESSING":
        return {"status": "PROCESSING"}
    if status == "FAILED":
        return {"status": "FAILED"}
    
    

    return {
        "status": "READY",
        "meeting_id": meeting_id,
        "summary": meeting["final_summary"]
    }
