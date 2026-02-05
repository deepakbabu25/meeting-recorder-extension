from fastapi import APIRouter
from app.state.meetings import MEETING_STATE
from app.agent.chat_agent import runChatAgent

router =APIRouter(prefix="/chat")

@router.post("/")
async def chat(meeting_id: str, question: str):
    context=MEETING_STATE.get(meeting_id)

    if not context:
        return {"error": "Meeting not found"}
    

    answer = await runChatAgent(context, question)

    context["chat_history"].append({
        "q":question,
        "a":answer
    })

    return {"answer": answer}
