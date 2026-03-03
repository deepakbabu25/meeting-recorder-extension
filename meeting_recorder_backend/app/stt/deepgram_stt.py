from app.stt.base import SpeechToText

class DeepgramSTT(SpeechToText):
    """
    Deepgram STT — streaming is handled directly in ws_audio.py.
    This class satisfies the factory interface but is not used for live audio.
    """

    def transcribe(self, audio_file_path: str) -> str:
        raise NotImplementedError("Deepgram uses live streaming via ws_audio.py")

    def transcribe_pcm(self, pcm_audio) -> str:
        raise NotImplementedError("Deepgram uses live streaming via ws_audio.py")
