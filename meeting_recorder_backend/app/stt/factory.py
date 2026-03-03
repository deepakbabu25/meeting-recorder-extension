from app.config import STT_provider
from app.stt.whisper_stt import WhisperSTT
from app.stt.deepgram_stt import DeepgramSTT


def get_stt_engine():
    if STT_provider == "whisper":
        return WhisperSTT()
    elif STT_provider == "deepgram":
        return DeepgramSTT()
    else:
        raise ValueError(f"Unsupported STT provider: {STT_provider}")