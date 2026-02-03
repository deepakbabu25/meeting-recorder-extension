from faster_whisper import WhisperModel
from app.stt.base import SpeechToText

class WhisperSTT(SpeechToText):

    def __init__(self):
        self.model=WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

    def transcribe(self, audio_path: str) -> str:
        segments, _=self.model.transcribe(audio_path)

        transcript=""
        for segment in segments:
            transcript+=segment.text + " "
        return transcript.strip()
