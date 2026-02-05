from pydantic_ai import Agent
from app.agent.util import get_prompt
from dotenv import load_dotenv
from app.agent.schemas import chatResponse
load_dotenv()

chat_agent=Agent(
      "google-gla:gemini-2.5-flash-lite",
    system_prompt=get_prompt("chatPrompt.md"),
    output_type=chatResponse,
    instrument=True,
)

async def runChatAgent(context: dict, question: str):
    result=await chat_agent.run(question)
    return result.output