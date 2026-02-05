from app.agent.meeting_agent import runMeetingAgent
import logging


logger = logging.getLogger(__name__)
async def generate_meeting_summary(transcript:str):
    if not transcript.strip():
        logger.warning("Empty transcript received, skipping agent call")
        return None
    

    logger.info("calling meeting summary agent")

    result = await runMeetingAgent(transcript)

    logger.info("Meeting summary generated successfully")

    return result
