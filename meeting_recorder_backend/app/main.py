

from fastapi import FastAPI
from app.api.ws_test import router as ws_router
from app.api.ws_audio import router as ws_audio_router
from app.api.meeting_status import router as meeting_status_router
from app.api.chat import router as chat_agent
from app.api.meeting import router as meeting_router
from app.api.lat_meeting import router as latestMeeting
from fastapi.middleware.cors import CORSMiddleware
# ------- APP SETUP ----------------

app = FastAPI(
    title="Meeting Recorder Backend",
    description="Backend service for recording and transcribing meeting audio",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://obfpeflgmjfikanlnkebbliemicokecl",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

app.include_router(chat_agent)

app.include_router(meeting_router)
app.include_router(latestMeeting)