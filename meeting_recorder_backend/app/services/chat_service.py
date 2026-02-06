from app.agent.chat_agent import runChatAgent
from app.state.meetings import MEETING_STATE


async def ask_chat(meeting_id: str, question: str) -> str:
    context = MEETING_STATE.get(meeting_id)

    if not context:
        return "Meeting not found"
    if not context.get("final_transcript") or not context.get("final_summary"):
        return "Meeting is still being processed. Please try again later."
    agent_context = {
        "final_summary": context.get("final_summary", ""),
        "final_transcript": context.get("final_transcript", ""),
        "chat_history": context.get("chat_history", []),
    }

    response = await runChatAgent(agent_context, question)

    # store chat history (chatbot loop)
    context.setdefault("chat_history", []).append({
        "question": question,
        "answer": response.answer
    })

    return response.answer
