from pydantic_ai import Agent
from app.agent.util import get_prompt
from dotenv import load_dotenv
from app.agent.schemas import ChatResponse
load_dotenv()

chat_agent=Agent(
      "google-gla:gemini-2.5-flash-lite",
    system_prompt=get_prompt("chatPrompt.md"),
    output_type=ChatResponse,
    instrument=True,
)

async def runChatAgent(context: dict, question: str):
    agent_input = f"""
MEETING SUMMARY:
{context.get("final_summary", "")}

MEETING TRANSCRIPT:
{context.get("final_transcript", "")}

USER QUESTION:
{question}
"""

    result = await chat_agent.run(agent_input)
    return result.output
