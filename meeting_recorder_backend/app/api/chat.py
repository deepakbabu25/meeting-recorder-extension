from fastapi import APIRouter, HTTPException
from app.state.meetings import MEETING_STATE
from app.agent.chat_agent import runChatAgent
from app.services.chat_service import ask_chat
from pydantic import BaseModel

router =APIRouter(prefix="/chat", tags=["Chat"])

class ChatRequest(BaseModel):
  meeting_id:str
  question: str

@router.post("/")
async def chat(req: ChatRequest):
  meeting_id= req.meeting_id
  question = req.question

  context =MEETING_STATE.get(meeting_id)
  if not context:
    return{"answer":"Meeting not found"}
  try:
    answer = await ask_chat(meeting_id, question)
    return {"answer": answer}
  
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
