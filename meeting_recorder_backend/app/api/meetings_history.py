from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional

from app.db.database import get_db
from app.db.models import User, Meeting, Transcript, MeetingSummary, ChatMessage
from app.api.deps import get_current_user

router = APIRouter()

# ---- Pydantic Models for the Import Payload ----
class ImportDataRequest(BaseModel):
    title: str = "Imported Meeting"
    transcript_chunks: List[Dict[str, Any]]
    summary: Dict[str, Any]
    qa_history: List[Dict[str, Any]]

@router.post("/import", response_model=dict)
async def import_meeting(
    payload: ImportDataRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Called after Guest Login. Takes the temporary IndexedDB data
    and securely persists it to the PostgreSQL database under the user's account.
    """
    # 1. Create the Meeting
    meeting = Meeting(
        user_id=current_user.id,
        title=payload.title,
        status="READY"
    )
    db.add(meeting)
    await db.flush()  # So we get the meeting.id

    # 2. Insert Transcripts
    for chunk in payload.transcript_chunks:
        # Sometimes indexeddb chunks might not have speaker labels depending on how they were stored
        # But this maps to our PostgreSQL model
        db.add(Transcript(
            meeting_id=meeting.id,
            speaker=chunk.get("speaker", "Unknown"),
            text=chunk.get("text", ""),
            start_time=chunk.get("start_time", 0.0),
            end_time=chunk.get("end_time", 0.0)
        ))

    # 3. Insert Summary
    db.add(MeetingSummary(
        meeting_id=meeting.id,
        summary_text=payload.summary.get("summary", ""),
        key_points=payload.summary.get("key_points", []),
        action_items=payload.summary.get("action_items", []),
        decisions=payload.summary.get("decisions", [])
    ))

    # 4. Insert QA History (Chat Messages)
    for qa in payload.qa_history:
        # Assuming format [{"role": "user", "content": "..."}]
        db.add(ChatMessage(
            meeting_id=meeting.id,
            role=qa.get("role", "user"),
            content=qa.get("content", "")
        ))

    # Commit all queries atomically
    await db.commit()
    
    return {"status": "success", "meeting_id": meeting.id}


@router.get("/", response_model=List[dict])
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a list of all meetings owned by the requesting authenticated user.
    """
    result = await db.execute(
        select(Meeting)
        .where(Meeting.user_id == current_user.id)
        .order_by(Meeting.created_at.desc())
    )
    meetings = result.scalars().all()
    
    # Return light-weight summary
    return [
        {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "created_at": m.created_at,
            "ended_at": m.ended_at
        } for m in meetings
    ]


@router.get("/{meeting_id}")
async def get_meeting_details(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the deep details (Transcript, Summary, Chat) of a specific past meeting.
    Ensures that the meeting actually belongs to the user requesting it!
    """
    # Verify ownership
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == current_user.id))
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or unauthorized.")

    # Fetch relationships
    # 1. Summary
    summ_res = await db.execute(select(MeetingSummary).where(MeetingSummary.meeting_id == meeting.id))
    summary = summ_res.scalar_one_or_none()

    # 2. Transcripts
    trans_res = await db.execute(select(Transcript).where(Transcript.meeting_id == meeting.id).order_by(Transcript.start_time.asc()))
    transcripts = trans_res.scalars().all()

    # 3. Chat History
    chat_res = await db.execute(select(ChatMessage).where(ChatMessage.meeting_id == meeting.id).order_by(ChatMessage.created_at.asc()))
    chats = chat_res.scalars().all()

    return {
        "meeting": {
            "id": meeting.id,
            "title": meeting.title,
            "created_at": meeting.created_at
        },
        "summary": {
            "summary_text": summary.summary_text if summary else "",
            "key_points": summary.key_points if summary else [],
            "action_items": summary.action_items if summary else [],
            "decisions": summary.decisions if summary else []
        },
        "transcripts": [
            {"speaker": t.speaker, "text": t.text, "start_time": t.start_time, "end_time": t.end_time} for t in transcripts
        ],
        "qa_history": [
            {"role": c.role, "content": c.content} for c in chats
        ]
    }


@router.delete("/{meeting_id}", response_model=dict)
async def delete_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a specific meeting and all its related cascades.
    """
    # Verify ownership
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == current_user.id))
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found or unauthorized.")
    
    # Cascade delete 
    await db.delete(meeting)
    await db.commit()
    
    return {"status": "success", "message": "Meeting deleted"}
