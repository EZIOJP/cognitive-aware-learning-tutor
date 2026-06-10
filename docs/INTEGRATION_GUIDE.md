# EEG AI Math Tutor - Integration Guide

> **Install & run today:** See [DEPENDENCIES.md](./DEPENDENCIES.md) and [SETUP_AND_COMMANDS.md](./SETUP_AND_COMMANDS.md).  
> Use `backend.main:app` (repo root), `npm install`, not `pnpm`.

## Overview

This React application is the frontend for your cognitive-aware AI math tutor. It displays real-time EEG data, provides a digital whiteboard for solving math problems, and features AI interventions based on your cognitive load.

## Architecture

```
ESP32-S3 (250Hz) → FastAPI Backend → WebSocket → React Frontend
                         ↓
                    SciPy FFT
                         ↓
                  Alpha/Beta/Gamma
                         ↓
                    LLaVA (Ollama)
```

## Current Implementation

The frontend currently uses **simulated data** for development. You need to replace the simulation code with actual WebSocket connections to your FastAPI backend.

## Integration Steps

### 1. FastAPI Backend WebSocket Setup

Your FastAPI backend should expose a WebSocket endpoint that streams biometric data:

```python
# backend/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

app = FastAPI()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/eeg")
async def websocket_eeg(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Get latest EEG data from your UDP receiver
            eeg_data = await get_latest_eeg_data()
            
            # Perform FFT to extract frequency bands
            alpha, beta, gamma = perform_fft(eeg_data)
            
            # Send to frontend
            await websocket.send_json({
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "timestamp": time.time() * 1000
            })
            
            await asyncio.sleep(0.1)  # 10Hz update rate
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

@app.post("/api/intervention")
async def handle_intervention(canvas_image: str, biometric_data: dict):
    """
    Triggered when frontend detects frustration.
    Sends canvas image to LLaVA for analysis.
    """
    # Save canvas image
    image_path = save_base64_image(canvas_image)
    
    # Call LLaVA via Ollama
    response = await query_llava(image_path, biometric_data)
    
    return {
        "intervention": response["intervention"],
        "question": response["question"],
        "detected_concept": response["concept"]
    }
```

### 2. Frontend WebSocket Connection

Replace the simulation code in `App.tsx` with a real WebSocket connection:

```typescript
// In App.tsx, replace the useEffect simulation with:

useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws/eeg');
  
  ws.onopen = () => {
    console.log('Connected to EEG stream');
    setIsConnected(true);
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const newData: BiometricData = {
      alpha: data.alpha,
      beta: data.beta,
      gamma: data.gamma,
      timestamp: data.timestamp,
    };
    
    setBiometricData((prev) => [...prev.slice(-100), newData]);
    
    // Calculate cognitive load
    const avgGamma = data.gamma;
    if (avgGamma > 60) {
      setCognitiveLoad("high");
    } else if (avgGamma > 35) {
      setCognitiveLoad("medium");
    } else {
      setCognitiveLoad("low");
    }
    
    // Check for intervention trigger
    const timeSinceLastUpdate = (Date.now() - lastCanvasUpdate) / 1000;
    if (avgGamma > 70 && timeSinceLastUpdate > 45 && !showIntervention) {
      triggerInterventionRequest(canvasImageData, data);
    }
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
    setIsConnected(false);
  };
  
  ws.onclose = () => {
    console.log('WebSocket closed');
    setIsConnected(false);
  };
  
  return () => {
    ws.close();
  };
}, []);

// Add function to request AI intervention
const triggerInterventionRequest = async (canvasData: string, biometricData: any) => {
  try {
    const response = await fetch('http://localhost:8000/api/intervention', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        canvas_image: canvasData,
        biometric_data: biometricData,
      }),
    });
    
    const result = await response.json();
    
    // Show intervention with AI response
    setShowIntervention(true);
    // Update intervention state with actual AI response
    
  } catch (error) {
    console.error('Failed to get AI intervention:', error);
  }
};
```

### 3. ESP32-S3 UDP to FastAPI Bridge

Your FastAPI backend should have a UDP listener that receives the 250Hz data from the ESP32-S3:

```python
# backend/udp_receiver.py
import asyncio
import struct
from collections import deque

class EEGDataReceiver:
    def __init__(self, host='0.0.0.0', port=5005):
        self.host = host
        self.port = port
        self.buffer = deque(maxlen=256)  # Store last 256 samples for FFT
        
    async def start(self):
        """Start UDP listener"""
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: EEGProtocol(self),
            local_addr=(self.host, self.port)
        )
        
    def add_sample(self, sample):
        """Add raw EEG sample to buffer"""
        self.buffer.append(sample)
        
    def get_latest_samples(self):
        """Get samples for FFT processing"""
        return list(self.buffer)

class EEGProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver):
        self.receiver = receiver
        
    def datagram_received(self, data, addr):
        # Assuming ESP32 sends float32 voltage values
        voltage = struct.unpack('f', data)[0]
        self.receiver.add_sample(voltage)
```

### 4. FFT Processing for Frequency Bands

```python
# backend/signal_processing.py
import numpy as np
from scipy.signal import butter, filtfilt
from scipy.fft import fft, fftfreq

def extract_frequency_bands(samples, sample_rate=250):
    """
    Extract Alpha, Beta, and Gamma frequency bands from raw EEG samples
    """
    # Convert to numpy array
    signal = np.array(samples)
    
    # Perform FFT
    N = len(signal)
    yf = fft(signal)
    xf = fftfreq(N, 1 / sample_rate)
    
    # Get positive frequencies only
    positive_freqs = xf[:N//2]
    power = np.abs(yf[:N//2]) ** 2
    
    # Extract band powers
    alpha_power = extract_band_power(positive_freqs, power, 8, 13)   # Alpha: 8-13 Hz
    beta_power = extract_band_power(positive_freqs, power, 13, 30)   # Beta: 13-30 Hz
    gamma_power = extract_band_power(positive_freqs, power, 30, 100) # Gamma: 30-100 Hz
    
    # Normalize to 0-100 scale
    total_power = alpha_power + beta_power + gamma_power
    if total_power > 0:
        alpha = (alpha_power / total_power) * 100
        beta = (beta_power / total_power) * 100
        gamma = (gamma_power / total_power) * 100
    else:
        alpha = beta = gamma = 0
        
    return alpha, beta, gamma

def extract_band_power(freqs, power, low_freq, high_freq):
    """Extract power in a specific frequency band"""
    band_mask = (freqs >= low_freq) & (freqs < high_freq)
    return np.sum(power[band_mask])
```

### 5. LLaVA Integration via Ollama

```python
# backend/llava_integration.py
import subprocess
import json
import base64

async def query_llava(image_path: str, biometric_data: dict):
    """
    Query LLaVA model via Ollama to analyze the math whiteboard
    """
    # Prepare prompt for LLaVA
    prompt = f"""
    You are an AI math tutor analyzing a student's work.
    
    The student's cognitive load is HIGH (Gamma waves: {biometric_data['gamma']:.1f}).
    They haven't made progress on this problem for 45 seconds.
    
    Analyze the math problem shown in the image and:
    1. Identify what concept they're working on
    2. Determine where they likely got stuck
    3. Ask a targeted question to help them (don't give the answer)
    
    Respond in JSON format:
    {{
      "concept": "the math concept being worked on",
      "intervention": "brief observation about where they're stuck",
      "question": "a targeted question to guide them"
    }}
    """
    
    # Call Ollama with LLaVA model
    result = subprocess.run(
        [
            "ollama", "run", "llava:13b",
            "--format", "json",
            prompt
        ],
        input=open(image_path, 'rb').read(),
        capture_output=True,
        text=True
    )
    
    return json.loads(result.stdout)
```

### 6. Post-Session Logging

For building your ML dataset, log all session data:

```python
# backend/session_logger.py
import json
from datetime import datetime
import os

def log_session_data(session_id, unified_payload):
    """
    Log unified payload to file for later ML training
    Format: {biometric_data, canvas_image, timestamp, interventions}
    """
    log_dir = "session_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = f"{log_dir}/session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(unified_payload) + '\n')
```

## Environment Setup

### Backend Requirements

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn websockets scipy numpy opencv-python

# Install Ollama (for LLaVA)
curl https://ollama.ai/install.sh | sh

# Pull LLaVA model
ollama pull llava:13b
# Or for math-specific model:
ollama pull math-llava
```

### Frontend Setup

The frontend is already set up. To run it:

```bash
# In this directory
pnpm install  # Already done
# Dev server is already running via Figma Make
```

## Running the Full System

1. **Start ESP32-S3**: Flash your firmware and ensure it's sending UDP packets to your laptop's IP on port 5005

2. **Start FastAPI Backend**:
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Frontend**: Already running in Figma Make preview

4. **Test Connection**: Check the connection status indicator in the top-right of the UI

## Customization Points

### Adjusting Intervention Triggers

In `App.tsx`, modify the intervention logic:

```typescript
// Current: triggers if gamma > 70 and no activity for 45s
if (avgGamma > 70 && timeSinceLastUpdate > 45 && !showIntervention) {
  triggerIntervention(avgGamma);
}

// Customize thresholds:
const GAMMA_THRESHOLD = 70;        // Adjust based on your baseline
const INACTIVITY_THRESHOLD = 45;   // Seconds of no canvas activity
```

### Cognitive Load Calculation

Customize the cognitive load mapping in `App.tsx`:

```typescript
// Current mapping
if (avgGamma > 60) setCognitiveLoad("high");
else if (avgGamma > 35) setCognitiveLoad("medium");
else setCognitiveLoad("low");

// You may want to use a weighted formula:
const cognitiveScore = (gamma * 0.6) + (beta * 0.3) - (alpha * 0.1);
```

## SD Card Logging (ESP32-S3)

If you want to log raw EEG data to SD card for ML dataset:

```cpp
// In your ESP32 firmware
void logToSDCard(float voltage) {
  File dataFile = SD.open("/DSC_" + String(sessionId) + ".csv", FILE_APPEND);
  if (dataFile) {
    dataFile.println(String(millis()) + "," + String(voltage));
    dataFile.close();
  }
}
```

**Important**: The integration guide mentions using `DSC` prefix for file names instead of `test_` to match your scanning logic.

## Troubleshooting

### WebSocket Connection Fails
- Ensure FastAPI CORS is configured correctly
- Check firewall settings on your laptop
- Verify the WebSocket URL matches your FastAPI host

### No EEG Data Received
- Confirm ESP32 is connected to the same network
- Check UDP port 5005 is not blocked
- Verify ESP32 is sending to correct IP address

### LLaVA Intervention Too Slow
- Use smaller LLaVA model (7b instead of 13b)
- Consider running intervention analysis asynchronously
- Cache common intervention patterns

### Canvas Export Issues
- Ensure react-sketch-canvas has proper permissions
- Check browser console for CORS errors on image export

## Next Steps

1. Build your FastAPI backend using the code snippets above
2. Flash your ESP32-S3 with the UDP transmission firmware
3. Replace the simulation code in App.tsx with real WebSocket connection
4. Test the full pipeline with actual EEG data
5. Fine-tune the cognitive load thresholds based on your baseline readings
6. Customize LLaVA prompts for your specific math curriculum

## Performance Optimization

- **EEG Sampling**: The ESP32 sends at 250Hz, but you can downsample to 50-100Hz for the visualization
- **FFT Window**: Use 256 samples (about 1 second of data) for reliable frequency extraction
- **Canvas Updates**: Debounce canvas changes to avoid overwhelming the backend
- **WebSocket Buffering**: Implement reconnection logic for robustness

Good luck with your cognitive-aware math tutor! This system has the potential to revolutionize personalized learning.
