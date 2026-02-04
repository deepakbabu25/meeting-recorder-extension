import subprocess
import numpy as np

FFMPEG_PATH = r"C:\ffmpeg-2026-02-02-git-7e9fe341df-essentials_build\bin\ffmpeg.exe"

def webm_bytes_to_pcm(webm_bytes: bytes) -> np.ndarray | None:
    """
    Convert WebM (Opus) bytes to PCM float32 (16kHz mono) for Whisper
    """

    try:
        process = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-loglevel", "quiet",
                "-i", "pipe:0",
                "-f", "s16le",
                "-ar", "16000",
                "-ac", "1",
                "pipe:1"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        pcm_bytes, _ = process.communicate(input=webm_bytes)

        if not pcm_bytes:
            return None

        # 🔑 Correct dtype: int16
        pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)

        # 🔑 Normalize to [-1.0, 1.0] float32
        pcm_float32 = pcm_int16.astype(np.float32) / 32768.0

        return pcm_float32

    except Exception as e:
        print("FFmpeg decode error:", e)
        return None
