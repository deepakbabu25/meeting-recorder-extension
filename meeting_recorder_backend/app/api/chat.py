from fastapi import APIRouter, HTTPException
from app.state.meetings import MEETING_STATE
from app.rag.vector_store import has_chunks
from app.services.chat_service import ask_chat
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    meeting_id: str
    question: str


@router.post("/")
async def chat(req: ChatRequest):
    meeting_id = req.meeting_id
    question = req.question

    # Allow chat as long as RAG has at least one chunk (even during live meeting)
    if not await has_chunks(meeting_id):
        meeting = MEETING_STATE.get(meeting_id)
        if not meeting:
            return {"answer": "Meeting not found."}
        return {"answer": "Chat isn't ready yet — still processing the transcript. Please wait a moment."}

    try:
        answer = await ask_chat(meeting_id, question)
        return {"answer": answer}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
