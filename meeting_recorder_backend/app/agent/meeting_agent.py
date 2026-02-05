from pydantic_ai import Agent
from app.agent.schemas import MeetingInsights
from app.agent.util import get_prompt
from dotenv import load_dotenv
load_dotenv()

meeting_agent = Agent(
    "google-gla:gemini-2.5-flash-lite",
    system_prompt=get_prompt("meeting_summary.md"),
    output_type=MeetingInsights,
    instrument=True,
)


async def runMeetingAgent(transcript:str)->MeetingInsights:
    result =await meeting_agent.run(transcript)
    return result.output