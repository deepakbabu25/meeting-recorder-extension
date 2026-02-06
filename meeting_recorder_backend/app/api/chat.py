from fastapi import APIRouter, HTTPException
from app.state.meetings import MEETING_STATE
from app.agent.chat_agent import runChatAgent
from app.services.chat_service import ask_chat

router =APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/")
async def chat(meeting_id: str, question: str):
  try:
    answer = await ask_chat(meeting_id, question)
    return {"answer": answer}
  
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
