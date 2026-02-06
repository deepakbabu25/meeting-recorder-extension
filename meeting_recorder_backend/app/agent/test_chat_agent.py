import asyncio
from app.agent.chat_agent import runChatAgent


TEST_CONTEXT ={
    "final_summary": """
The team discussed the backend architecture.
Decision was made to use FastAPI.
Deployment date was not finalized.
""",
    "final_transcript": """
Alice: We should use FastAPI for the backend.
Bob: Agreed, Flask might be too limited.
Alice: Deployment date we can decide later.
"""  
}
async def main():
    question = "Which backend framework was decided?"
    answer = await runChatAgent(TEST_CONTEXT, question)
    print("ANSWER:", answer)

    question2 = "What is the deployment date?"
    answer2 = await runChatAgent(TEST_CONTEXT, question2)
    print("ANSWER:", answer2)

if __name__ == "__main__":
    asyncio.run(main())