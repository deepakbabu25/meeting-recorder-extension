from faster_whisper import WhisperModel
from app.stt.base import SpeechToText
import numpy as np

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
    
    #newmethond (foe live meeting)
    def transcribe_pcm(self, pcm_audio:np.ndarray)-> str:

       
            #concatenate all audio chunks
            

            segements, _=self.model.transcribe(pcm_audio,
                                               vad_filter=True,
                                               language="en"
                                               )
            transcript=""
            for segment in segements:
                transcript+=segment.text + " "
            return transcript.strip()
            

