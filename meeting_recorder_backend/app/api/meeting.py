from fastapi import APIRouter
from app.state.meetings import MEETING_STATE
from app.db.database import AsyncSessionLocal
from app.db.models import Meeting, MeetingSummary
from sqlalchemy import select

router = APIRouter(prefix="/meeting", tags=["Meeting"])


@router.get("/{meeting_id}/summary")
async def get_meeting_summary(meeting_id: str):
    # 1. Try fast in-memory state first
    meeting = MEETING_STATE.get(meeting_id)

    if meeting:
        status = meeting.get("status")

        if status == "IN_PROGRESS":
            return {"status": "RECORDING"}

        if status == "PROCESSING":
            return {"status": "PROCESSING"}

        return {
            "status": status or "READY",
            "meeting_id": meeting_id,
            "summary": meeting.get("final_summary")
        }

    # 2. Fall back to PostgreSQL (meeting ended and was cleared from memory)
    try:
        async with AsyncSessionLocal() as session:
            row = await session.get(Meeting, __import__("uuid").UUID(meeting_id))
            if not row:
                return {
                    "status": "NOT_FOUND",
                    "summary": {
                        "summary": "Meeting not found.",
                        "key_points": [], "action_items": [], "decisions": []
                    }
                }

            # Load the associated summary
            stmt = select(MeetingSummary).where(MeetingSummary.meeting_id == row.id)
            result = await session.execute(stmt)
            summary_row = result.scalar_one_or_none()

            return {
                "status": row.status or "READY",
                "meeting_id": meeting_id,
                "summary": {
                    "summary": summary_row.summary_text if summary_row else "",
                    "key_points": summary_row.key_points if summary_row else [],
                    "action_items": summary_row.action_items if summary_row else [],
                    "decisions": summary_row.decisions if summary_row else []
                }
            }
    except Exception as e:
        return {
            "status": "NOT_FOUND",
            "summary": {
                "summary": f"Error loading meeting: {e}",
                "key_points": [], "action_items": [], "decisions": []
            }
        }
