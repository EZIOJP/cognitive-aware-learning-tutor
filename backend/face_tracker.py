import json
import os
import signal
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = str(_ROOT / "assets" / "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
STATUS_URL = os.getenv("FACE_TRACKER_STATUS_URL", "http://localhost:8000/api/vocab/face/status")
# Optional JWT from login — enables hub face_attention readings (POST /api/vocab/face/status).
FACE_TRACKER_TOKEN = os.getenv("FACE_TRACKER_TOKEN", "").strip()
_stop_requested = False


def _opencv_gui_available() -> bool:
    if os.getenv("FACE_TRACKER_HEADLESS", "").strip().lower() in ("1", "true", "yes"):
        return False
    try:
        cv2.namedWindow("__face_tracker_probe__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__face_tracker_probe__")
        return True
    except cv2.error:
        return False


def _request_stop(*_args) -> None:
    global _stop_requested
    _stop_requested = True


def post_status(payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if FACE_TRACKER_TOKEN:
        headers["Authorization"] = f"Bearer {FACE_TRACKER_TOKEN}"
    req = urllib.request.Request(
        STATUS_URL,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=0.5).read()
    except Exception:
        pass


def blendshape_map(result) -> dict[str, float]:
    if not result.face_blendshapes:
        return {}
    return {
        category.category_name: float(category.score)
        for category in result.face_blendshapes[0]
    }


def infer_status(scores: dict[str, float], blink_rate: float, face_detected: bool) -> dict:
    if not face_detected:
        return {
            "attention": 0,
            "attitude": "away",
            "blink_rate": blink_rate,
            "face_detected": False,
            "details": scores,
        }

    blink = (scores.get("eyeBlinkLeft", 0) + scores.get("eyeBlinkRight", 0)) / 2
    look_down = (scores.get("eyeLookDownLeft", 0) + scores.get("eyeLookDownRight", 0)) / 2
    look_out = max(
        scores.get("eyeLookOutLeft", 0),
        scores.get("eyeLookOutRight", 0),
        scores.get("eyeLookInLeft", 0),
        scores.get("eyeLookInRight", 0),
    )
    smile = (scores.get("mouthSmileLeft", 0) + scores.get("mouthSmileRight", 0)) / 2
    brow_down = (scores.get("browDownLeft", 0) + scores.get("browDownRight", 0)) / 2

    attention = 100
    attention -= min(45, look_out * 90)
    attention -= min(30, blink * 45)
    attention -= min(20, max(0, blink_rate - 25) * 1.5)
    attention += min(10, look_down * 12)
    attention = max(0, min(100, attention))

    if blink_rate > 32:
        attitude = "tired"
    elif brow_down > 0.35:
        attitude = "strained"
    elif smile > 0.25:
        attitude = "positive"
    elif attention < 45:
        attitude = "distracted"
    else:
        attitude = "focused"

    return {
        "attention": round(attention, 1),
        "attitude": attitude,
        "blink_rate": round(blink_rate, 1),
        "face_detected": True,
        "details": {
            "blink": round(blink, 3),
            "look_down": round(look_down, 3),
            "look_out": round(look_out, 3),
            "smile": round(smile, 3),
            "brow_down": round(brow_down, 3),
        },
    }


if not os.path.exists(MODEL_PATH):
    print("Downloading Face Landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Download complete.")

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.FaceLandmarkerOptions(
    base_options=base_options,
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
    num_faces=1,
)

detector = vision.FaceLandmarker.create_from_options(options)
cap = cv2.VideoCapture(0)

blink_events = 0
blink_was_closed = False
window_started = time.time()
last_post = 0.0
last_console = 0.0
show_window = _opencv_gui_available()

signal.signal(signal.SIGINT, _request_stop)
if hasattr(signal, "SIGBREAK"):
    signal.signal(signal.SIGBREAK, _request_stop)

if show_window:
    print("Starting MediaPipe attention tracker. Press ESC to exit.")
else:
    print("OpenCV GUI unavailable (opencv-python-headless is installed).")
    print("Running headless — attention data still posts to the hub. Press Ctrl+C to stop.")
    print("For the mirror window: pip uninstall opencv-python-headless  (then restart this script)")
print(f"Posting status to {STATUS_URL}")

while cap.isOpened() and not _stop_requested:
    success, frame = cap.read()
    if not success:
        continue

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    result = detector.detect(mp_image)
    scores = blendshape_map(result)
    face_detected = bool(result.face_landmarks)

    blink_score = (scores.get("eyeBlinkLeft", 0) + scores.get("eyeBlinkRight", 0)) / 2
    if blink_score > 0.55 and not blink_was_closed:
        blink_events += 1
        blink_was_closed = True
    elif blink_score < 0.25:
        blink_was_closed = False

    elapsed = max(1, time.time() - window_started)
    blink_rate = (blink_events / elapsed) * 60

    if elapsed >= 60:
        blink_events = 0
        window_started = time.time()

    status = infer_status(scores, blink_rate, face_detected)

    now = time.time()
    if now - last_post > 1:
        post_status(status)
        last_post = now

    label = f"{status['attitude']} | attention {status['attention']}% | blinks {status['blink_rate']}/min"

    if show_window:
        # Mirror video like a physical mirror; draw overlays AFTER flip so text stays readable.
        mirrored = cv2.flip(frame, 1)
        h, w = mirrored.shape[:2]

        if face_detected:
            for face_landmarks in result.face_landmarks:
                for landmark in face_landmarks:
                    x = int((1.0 - landmark.x) * w)
                    y = int(landmark.y * h)
                    cv2.circle(mirrored, (x, y), 1, (0, 255, 0), -1)

        cv2.putText(mirrored, label, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imshow("Focus Mirror - Python (ESC to close)", mirrored)
        if cv2.waitKey(5) & 0xFF == 27:
            break
    else:
        if now - last_console > 2:
            print(label)
            last_console = now
        time.sleep(0.03)

post_status({
    "attention": 0,
    "attitude": "stopped",
    "blink_rate": 0,
    "face_detected": False,
    "details": {},
})

cap.release()
if show_window:
    cv2.destroyAllWindows()
else:
    print("Face tracker stopped.")

