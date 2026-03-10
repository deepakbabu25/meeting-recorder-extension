from app.agent.chat_agent import runChatAgent
from app.state.meetings import get_meeting_state, save_meeting_state
from app.rag.retriever import retrieve_context
from app.rag.vector_store import has_chunks as vs_has_chunks
from app.db.database import AsyncSessionLocal
from app.db.models import ChatMessage, Meeting
import uuid
import asyncio


async def ask_chat(meeting_id: str, question: str) -> str:
    # RAG context — available as soon as first chunk is indexed (during live meeting)
    rag_context = await retrieve_context(meeting_id, question)

    # Also pull summary if meeting is already finished
    m_state = get_meeting_state(meeting_id)
    
    # Safely extract the string summary from the dictionary if it exists
    final_summary_obj = m_state.get("final_summary")
    summary = final_summary_obj.get("summary", "") if isinstance(final_summary_obj, dict) else ""

    if not rag_context and not summary:
        if not await vs_has_chunks(meeting_id):
            return "Chat isn't ready yet — the transcript is still being processed. Please wait a moment."
        return "I couldn't find relevant information for that question in the transcript."

    agent_context = {
        "final_summary": summary or "",
        "final_transcript": rag_context,   # RAG chunks replace full transcript
        "chat_history": m_state.get("chat_history", []),
    }

    response = await runChatAgent(agent_context, question)

    # Persist chat history to disk-backed state (in-memory cache for ongoing meetings)
    m_state.setdefault("chat_history", []).append({
        "question": question,
        "answer": response.answer
    })
    save_meeting_state(meeting_id)

    # Always persist to PostgreSQL if the meeting row exists in DB.
    # We query the DB directly so this works even after in-memory state is cleared
    # (i.e. mid-meeting, post-meeting, and after server restarts all work correctly).
    async def _save_chat():
        try:
            async with AsyncSessionLocal() as session:
                # Only save if the Meeting row actually exists in DB
                meeting_row = await session.get(Meeting, uuid.UUID(meeting_id))
                if meeting_row:
                    session.add(ChatMessage(
                        meeting_id=uuid.UUID(meeting_id),
                        role="user",
                        content=question
                    ))
                    session.add(ChatMessage(
                        meeting_id=uuid.UUID(meeting_id),
                        role="assistant",
                        content=response.answer
                    ))
                    await session.commit()
                    print(f"[Chat DB] Saved Q&A for meeting {meeting_id}", flush=True)
        except Exception as e:
            print(f"[Chat DB Error] {e}")

    asyncio.create_task(_save_chat())

    return response.answer
