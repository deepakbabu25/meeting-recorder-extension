from app.stt.factory import get_stt_engine

def transcribe_audio(audio_path: str) -> str:
    stt_engine = get_stt_engine()
    return stt_engine.transcribe(audio_path)
