from app.agent.chat_agent import runChatAgent
from app.state.meetings import MEETING_STATE
from app.rag.retriever import retrieve_context
from app.rag.vector_store import has_chunks


async def ask_chat(meeting_id: str, question: str) -> str:
    # RAG context — available as soon as first chunk is indexed (during live meeting)
    rag_context = retrieve_context(meeting_id, question)

    # Also pull summary if meeting is already finished
    meeting = MEETING_STATE.get(meeting_id, {})
    summary = meeting.get("final_summary", "") if meeting else ""

    if not rag_context and not summary:
        if not has_chunks(meeting_id):
            return "Chat isn't ready yet — the transcript is still being processed. Please wait a moment."
        return "I couldn't find relevant information for that question in the transcript."

    agent_context = {
        "final_summary": summary or "",
        "final_transcript": rag_context,   # RAG chunks replace full transcript
        "chat_history": meeting.get("chat_history", []) if meeting else [],
    }

    response = await runChatAgent(agent_context, question)

    # Persist chat history when meeting state exists
    if meeting is not None:
        meeting.setdefault("chat_history", []).append({
            "question": question,
            "answer": response.answer
        })

    return response.answer
