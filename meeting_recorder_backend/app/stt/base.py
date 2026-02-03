from abc import ABC, abstractmethod

class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio_file_path: str) -> str:
        pass