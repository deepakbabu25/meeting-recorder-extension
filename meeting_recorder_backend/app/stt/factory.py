from app.config import STT_provider
from app.stt.whisper_stt import WhisperSTT
#later
#from stt.google_stt import GoogleSTT


def get_stt_engine():
    if STT_provider == "whisper":
        return WhisperSTT()
    # elif STT_provider == "google":
    #     return GoogleSTT()
    else:
        raise ValueError(f"Unsupported STT provider: {STT_provider}")