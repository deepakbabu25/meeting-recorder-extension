

from fastapi import FastAPI
from app.api.ws_test import router as ws_router
from app.api.ws_audio import router as ws_audio_router
from app.api.meeting_status import router as meeting_status_router
# ------- APP SETUP ----------------

app = FastAPI(
    title="Meeting Recorder Backend",
    description="Backend service for recording and transcribing meeting audio",
    version="1.0.0"
)



# ---------- ROUTES ----------------

@app.get("/")
def test_route():
    return {"status": "Backend running"}


# WebSocket routes

app.include_router(ws_router)
app.include_router(ws_audio_router)

#api routes
app.include_router(meeting_status_router)