import os
import uuid
import shutil
import subprocess

from fastapi import FastAPI, UploadFile, HTTPException
from app.services.transcription import transcribe_audio

# ---------------- APP SETUP ----------------

app = FastAPI(
    title="Meeting Recorder Backend",
    description="Backend service for recording and transcribing meeting audio",
    version="1.0.0"
)

UPLOAD_DIR = "uploads"
PROCESSED_DIR = "processed"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# ✅ ABSOLUTE FFMPEG PATH (WINDOWS SAFE)
FFMPEG_PATH = r"C:\ffmpeg-2026-02-02-git-7e9fe341df-essentials_build\bin\ffmpeg.exe"


# ---------------- ROUTES ----------------

@app.get("/")
def test_route():
    return {"status": "Backend running"}


@app.post("/transcribe")
async def transcribe(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # 1️⃣ Save uploaded file
    ext = os.path.splitext(file.filename)[-1] or ".wav"
    raw_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")

    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 🔴 SAFETY CHECK
    if os.path.getsize(raw_path) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # 2️⃣ Convert audio → Whisper-safe WAV
    processed_path = os.path.join(PROCESSED_DIR, f"{uuid.uuid4()}.wav")

    command = [
        FFMPEG_PATH,
        "-y",
        "-vn",
        "-i", raw_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        processed_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="ignore"
    )

    if result.returncode != 0:
        print("FFMPEG STDOUT:", result.stdout)
        print("FFMPEG STDERR:", result.stderr)
        raise HTTPException(status_code=500, detail="FFmpeg failed to process audio")

    # 3️⃣ Transcribe converted audio
    transcript = transcribe_audio(processed_path)

    return {
        "status": "success",
        "transcript": transcript
    }
