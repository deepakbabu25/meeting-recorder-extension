import os
from dotenv import load_dotenv

load_dotenv()

STT_provider = "deepgram"
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")