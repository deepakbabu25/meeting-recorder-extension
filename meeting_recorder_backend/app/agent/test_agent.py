import asyncio
from app.agent.meeting_agent import runMeetingAgent

test_text ="""
We discussed deploying the backend using Docker.
Decided to use FastAPI with WebSockets.
Alice will work on transcription.
Bob will handle the frontend.
"""

async def main():
    result = await runMeetingAgent(test_text)
    print(result.model_dump)

asyncio.run(main())