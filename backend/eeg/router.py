from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.eeg import led_serial
from backend.eeg import service as eeg_service

router = APIRouter(prefix="/api/eeg", tags=["eeg"])


class LedBody(BaseModel):
    action: str = Field(..., description="off|on|slow|fast|double|heartbeat")
    port: str | None = None


@router.get("/status")
def eeg_status():
    """Soft status — never indicates stack failure when device is absent."""
    payload = eeg_service.status_payload()
    payload.update(led_serial.serial_status())
    return payload


@router.post("/led")
def eeg_led(body: LedBody):
    """Drive onboard RGB over USB serial. Soft-fail if board unplugged."""
    return led_serial.send_led(body.action, port=body.port)


@router.websocket("/ws/eeg")
async def websocket_eeg_prefixed(websocket: WebSocket):
    """Also available at /ws/eeg via legacy mount below."""
    await _ws_loop(websocket)


async def _ws_loop(websocket: WebSocket):
    await websocket.accept()
    eeg_service.register_ws(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        eeg_service.unregister_ws(websocket)


# Keep classic path used by frontend resolveWsUrl("/ws/eeg")
legacy_router = APIRouter(tags=["eeg"])


@legacy_router.websocket("/ws/eeg")
async def websocket_eeg(websocket: WebSocket):
    await _ws_loop(websocket)
