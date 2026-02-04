from fastapi import APIRouter, WebSocket, WebSocketDisconnect
router = APIRouter()

@router.websocket("/ws/test")
async def ws_test(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted")
    try:
        while True:
            msg=await websocket.receive_text()
            print(f"Received message: {msg}")

            await websocket.send_text(f"Echo: {msg}")
    except WebSocketDisconnect:
        print("WebSocket connection closed")