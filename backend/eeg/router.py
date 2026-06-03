import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.eeg import service as eeg_service

router = APIRouter(tags=["eeg"])


@router.websocket("/ws/eeg")
async def websocket_eeg(websocket: WebSocket):
    await websocket.accept()
    eeg_service.register_ws(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        eeg_service.unregister_ws(websocket)
