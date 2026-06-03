"""
Example FastAPI Backend for EEG AI Math Tutor

This is a complete reference implementation showing how to:
1. Receive UDP packets from ESP32-S3
2. Perform FFT to extract Alpha/Beta/Gamma bands
3. Stream data to frontend via WebSocket
4. Integrate with LLaVA for AI interventions
5. Log session data for ML training

Requirements:
    pip install fastapi uvicorn websockets scipy numpy pillow

Run with:
    uvicorn backend_example:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import base64
import time
import numpy as np
from scipy.fft import fft, fftfreq
from collections import deque
from typing import List
import struct
from io import BytesIO
from PIL import Image

app = FastAPI(title="EEG AI Math Tutor Backend")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global EEG data buffer
eeg_buffer = deque(maxlen=256)  # Store last 256 samples for FFT (about 1 second at 250Hz)


# ============================================================================
# Data Models
# ============================================================================

class BiometricData(BaseModel):
    alpha: float
    beta: float
    gamma: float
    timestamp: float


class InterventionRequest(BaseModel):
    canvas_image: str  # Base64 encoded
    biometric_data: BiometricData


class InterventionResponse(BaseModel):
    intervention: str
    question: str
    detected_concept: str
    confidence: float = 0.85


# ============================================================================
# UDP Receiver (runs in background)
# ============================================================================

class EEGUDPProtocol(asyncio.DatagramProtocol):
    """Receives raw EEG data from ESP32-S3 via UDP"""

    def datagram_received(self, data, addr):
        try:
            # Assuming ESP32 sends float32 voltage values
            # Adjust struct format based on your ESP32 firmware
            voltage = struct.unpack('f', data)[0]
            eeg_buffer.append(voltage)
        except Exception as e:
            print(f"Error parsing UDP packet: {e}")


async def start_udp_server():
    """Start UDP server to receive EEG data from ESP32"""
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: EEGUDPProtocol(),
        local_addr=('0.0.0.0', 5005)
    )
    print("UDP server listening on port 5005 for ESP32-S3 data...")
    return transport


# ============================================================================
# Signal Processing (FFT)
# ============================================================================

def extract_frequency_bands(samples: List[float], sample_rate: int = 250) -> tuple:
    """
    Perform FFT and extract Alpha, Beta, Gamma frequency bands

    Args:
        samples: List of raw EEG voltage samples
        sample_rate: Sampling rate in Hz (default 250)

    Returns:
        (alpha, beta, gamma) power values normalized to 0-100
    """
    if len(samples) < 128:
        return 0.0, 0.0, 0.0

    # Convert to numpy array and remove DC offset
    signal = np.array(samples)
    signal = signal - np.mean(signal)

    # Apply Hamming window to reduce spectral leakage
    window = np.hamming(len(signal))
    signal = signal * window

    # Perform FFT
    N = len(signal)
    yf = fft(signal)
    xf = fftfreq(N, 1 / sample_rate)

    # Get positive frequencies only
    positive_freqs = xf[:N//2]
    power = np.abs(yf[:N//2]) ** 2

    # Extract band powers
    alpha_power = extract_band_power(positive_freqs, power, 8, 13)    # Alpha: 8-13 Hz (relaxed)
    beta_power = extract_band_power(positive_freqs, power, 13, 30)    # Beta: 13-30 Hz (focused)
    gamma_power = extract_band_power(positive_freqs, power, 30, 100)  # Gamma: 30-100 Hz (stressed)

    # Normalize to 0-100 scale
    total_power = alpha_power + beta_power + gamma_power
    if total_power > 0:
        alpha = (alpha_power / total_power) * 100
        beta = (beta_power / total_power) * 100
        gamma = (gamma_power / total_power) * 100
    else:
        alpha = beta = gamma = 0.0

    return alpha, beta, gamma


def extract_band_power(freqs: np.ndarray, power: np.ndarray, low_freq: float, high_freq: float) -> float:
    """Extract total power in a specific frequency band"""
    band_mask = (freqs >= low_freq) & (freqs < high_freq)
    return float(np.sum(power[band_mask]))


# ============================================================================
# WebSocket Endpoint (streams to frontend)
# ============================================================================

@app.websocket("/ws/eeg")
async def websocket_eeg(websocket: WebSocket):
    """
    WebSocket endpoint that streams processed EEG data to frontend
    Sends Alpha, Beta, Gamma values at ~10Hz
    """
    await websocket.accept()
    print("Frontend connected via WebSocket")

    try:
        while True:
            # Get latest samples from buffer
            if len(eeg_buffer) >= 128:
                samples = list(eeg_buffer)

                # Perform FFT to extract frequency bands
                alpha, beta, gamma = extract_frequency_bands(samples)

                # Send to frontend
                await websocket.send_json({
                    "alpha": round(alpha, 2),
                    "beta": round(beta, 2),
                    "gamma": round(gamma, 2),
                    "timestamp": time.time() * 1000
                })
            else:
                # Not enough samples yet, send zeros
                await websocket.send_json({
                    "alpha": 0.0,
                    "beta": 0.0,
                    "gamma": 0.0,
                    "timestamp": time.time() * 1000
                })

            # Update at 10Hz (100ms interval)
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print("Frontend disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")


# ============================================================================
# AI Intervention Endpoint (LLaVA Integration)
# ============================================================================

@app.post("/api/intervention", response_model=InterventionResponse)
async def request_intervention(request: InterventionRequest):
    """
    Triggered when frontend detects frustration (high gamma + canvas inactivity)
    Analyzes the canvas image using LLaVA to provide targeted guidance
    """
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.canvas_image.split(',')[1])
        image = Image.open(BytesIO(image_data))

        # Save temporarily for LLaVA
        image_path = f"/tmp/canvas_{int(time.time())}.png"
        image.save(image_path)

        # Query LLaVA via Ollama
        intervention = await query_llava_ollama(image_path, request.biometric_data)

        return intervention

    except Exception as e:
        print(f"Intervention error: {e}")
        # Fallback response if LLaVA fails
        return InterventionResponse(
            intervention="I noticed your cognitive load increased significantly.",
            question="Would you like me to break down the problem into smaller steps?",
            detected_concept="General Problem Solving",
            confidence=0.5
        )


async def query_llava_ollama(image_path: str, biometric_data: BiometricData) -> InterventionResponse:
    """
    Query LLaVA model via Ollama to analyze the math whiteboard

    Install Ollama: https://ollama.ai/
    Then: ollama pull llava:13b

    For math-specific tasks, you can also try:
        ollama pull math-llava
    """
    import subprocess

    # Prepare prompt for LLaVA
    prompt = f"""You are an AI math tutor analyzing a student's handwritten work.

Student's current state:
- Gamma waves (stress): {biometric_data.gamma:.1f}/100
- They haven't made progress for 45+ seconds
- This indicates they are stuck and frustrated

Analyze the math problem in the image and respond in this EXACT JSON format:
{{
  "detected_concept": "the specific math concept (e.g., Matrix Multiplication, Derivatives, etc.)",
  "intervention": "a brief, empathetic observation about where they appear stuck (1 sentence)",
  "question": "a targeted Socratic question to guide them forward without giving the answer",
  "confidence": 0.85
}}

Important:
- DO NOT give the answer
- Ask a question that helps them discover the next step
- Be encouraging and specific
- Focus on the exact step where they stopped
"""

    try:
        # Call Ollama with LLaVA
        # Note: This is a simplified example. In production, use Ollama's Python API
        result = subprocess.run(
            ["ollama", "run", "llava:13b", prompt],
            input=open(image_path, 'rb').read(),
            capture_output=True,
            text=True,
            timeout=30
        )

        # Parse JSON response
        response_data = json.loads(result.stdout)

        return InterventionResponse(
            intervention=response_data["intervention"],
            question=response_data["question"],
            detected_concept=response_data["detected_concept"],
            confidence=response_data.get("confidence", 0.85)
        )

    except Exception as e:
        print(f"LLaVA error: {e}")
        # Fallback response
        return InterventionResponse(
            intervention="Your cognitive load spiked on this problem.",
            question="What part of this problem feels most challenging right now?",
            detected_concept="Unknown",
            confidence=0.3
        )


# ============================================================================
# Session Logging (for ML dataset)
# ============================================================================

@app.post("/api/log-session")
async def log_session(session_data: dict):
    """
    Log session data for later ML analysis
    Saves unified payload (biometric + canvas + interventions) to JSONL
    """
    import os
    from datetime import datetime

    log_dir = "session_logs"
    os.makedirs(log_dir, exist_ok=True)

    session_id = session_data.get("session_id", int(time.time()))
    log_file = f"{log_dir}/session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    with open(log_file, 'a') as f:
        f.write(json.dumps(session_data) + '\n')

    return {"status": "logged", "file": log_file}


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Start UDP server when FastAPI starts"""
    asyncio.create_task(start_udp_server())
    try:
        from backend.vocab_backend import router as vocab_router
        app.include_router(vocab_router)
        print("📚 Vocab cycle API mounted at /api/vocab/*")
    except Exception as e:
        print(f"⚠️ Vocab API not loaded: {e}")
    print("🧠 EEG AI Math Tutor Backend Started")
    print("📡 Waiting for ESP32-S3 connection on UDP port 5005...")
    print("🌐 WebSocket endpoint: ws://localhost:8000/ws/eeg")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "eeg_buffer_size": len(eeg_buffer),
        "receiving_data": len(eeg_buffer) > 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
