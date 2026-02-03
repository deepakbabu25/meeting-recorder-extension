from stt.base import SpeechToText

class GoogleSTT(SpeechToText):

    def transcribe(self, audio_path: str) -> str:
        # call Google Speech-to-Text API here
        return "google transcript"
