

from fastapi import FastAPI
from app.api.transcribe import router as transcribe_router
from app.api.status import router as status_router

# ---------------- APP SETUP ----------------

app = FastAPI(
    title="Meeting Recorder Backend",
    description="Backend service for recording and transcribing meeting audio",
    version="1.0.0"
)



# ---------------- ROUTES ----------------

@app.get("/")
def test_route():
    return {"status": "Backend running"}

app.include_router(transcribe_router)
app.include_router(status_router)
