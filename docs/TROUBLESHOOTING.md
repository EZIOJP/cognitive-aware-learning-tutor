# 🔧 Troubleshooting Guide

Common issues and their solutions for the EEG AI Math Tutor system.

---

## Table of Contents

1. [Frontend Issues](#frontend-issues)
2. [Backend Issues](#backend-issues)
3. [ESP32/Hardware Issues](#esp32hardware-issues)
4. [WebSocket Connection Issues](#websocket-connection-issues)
5. [LLaVA/AI Issues](#llavaai-issues)
6. [EEG Signal Quality Issues](#eeg-signal-quality-issues)

---

## Frontend Issues

### Canvas not displaying correctly

**Symptoms:** Whiteboard appears blank or drawing doesn't work

**Solutions:**
1. Check browser console for errors
2. Ensure `react-sketch-canvas` is installed:
   ```bash
   pnpm install
   ```
3. Try refreshing the page
4. Check if you're using a supported browser (Chrome, Firefox, Edge)

### Charts not rendering

**Symptoms:** Biometric charts are empty or frozen

**Solutions:**
1. Ensure `recharts` is installed
2. Check that data is being received:
   ```javascript
   console.log(biometricData);
   ```
3. Verify data format matches `BiometricData` interface
4. Check browser console for errors

### WebSocket won't connect (showing "Disconnected")

See [WebSocket Connection Issues](#websocket-connection-issues)

---

## Backend Issues

### FastAPI won't start

**Symptoms:** `uvicorn backend_example:app` fails

**Solutions:**

1. **Port already in use:**
   ```bash
   # Check what's using port 8000
   # Linux/Mac:
   lsof -i :8000
   # Windows:
   netstat -ano | findstr :8000

   # Kill the process or use different port:
   uvicorn backend_example:app --port 8001
   ```

2. **Missing dependencies:**
   ```bash
   pip install fastapi uvicorn websockets scipy numpy pillow
   ```

3. **Python version too old:**
   ```bash
   python --version  # Need 3.8+
   ```

### UDP packets not received from ESP32

**Symptoms:** `eeg_buffer_size` stays at 0 in `/health` endpoint

**Solutions:**

1. **Check firewall:**
   ```bash
   # Windows: Allow UDP port 5005
   # Control Panel → Windows Defender Firewall → Advanced Settings → Inbound Rules → New Rule

   # Mac:
   # System Preferences → Security & Privacy → Firewall → Firewall Options

   # Linux:
   sudo ufw allow 5005/udp
   ```

2. **Verify ESP32 is sending to correct IP:**
   ```bash
   # Find your laptop's IP
   # Windows:
   ipconfig
   # Mac/Linux:
   ifconfig
   # Look for IP on same network as ESP32 (e.g., 192.168.1.x)
   ```

3. **Test UDP reception manually:**
   ```bash
   # Listen on UDP port 5005
   nc -ul 5005
   # You should see data if ESP32 is transmitting
   ```

### FFT returns all zeros

**Symptoms:** Alpha/Beta/Gamma are always 0.0

**Solutions:**

1. **Not enough samples:**
   - FFT requires at least 128 samples
   - Wait a few seconds after starting

2. **DC offset too large:**
   - Verify signal is being de-meaned:
     ```python
     signal = signal - np.mean(signal)
     ```

3. **Check sample values:**
   ```python
   print(f"Buffer size: {len(eeg_buffer)}")
   print(f"Sample range: {min(eeg_buffer)} to {max(eeg_buffer)}")
   ```

---

## ESP32/Hardware Issues

### ESP32 won't connect to WiFi

**Symptoms:** Serial monitor shows "WiFi connection failed"

**Solutions:**

1. **Check credentials:**
   ```cpp
   const char* WIFI_SSID = "YourActualSSID";  // Case sensitive!
   const char* WIFI_PASSWORD = "YourPassword";
   ```

2. **WiFi network issues:**
   - Ensure 2.4GHz network (ESP32 doesn't support 5GHz)
   - Check network is not hidden
   - Try a different network

3. **ESP32 too far from router:**
   - Move closer temporarily
   - Check WiFi signal strength in Serial Monitor

4. **Reset network settings:**
   ```cpp
   // Add to setup():
   WiFi.disconnect(true);
   delay(1000);
   WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
   ```

### No EEG readings / all readings are 0

**Symptoms:** Serial monitor shows 0.0V or constant value

**Solutions:**

1. **Check wiring:**
   ```
   BioAmp EXG Pill → ESP32-S3
   VCC → 3.3V
   GND → GND
   OUT → GPIO 34 (or your configured pin)
   ```

2. **Verify pin configuration:**
   ```cpp
   const int EEG_PIN = 34;  // Must be ADC-capable pin
   ```

3. **Test analog input:**
   ```cpp
   // Simple test in loop():
   int raw = analogRead(EEG_PIN);
   Serial.println(raw);  // Should vary between 0-4095
   ```

4. **Check BioAmp power:**
   - Verify 3.3V is present on VCC pin
   - Try replacing BioAmp if available

### ESP32 keeps disconnecting

**Symptoms:** WiFi connects then drops repeatedly

**Solutions:**

1. **Power supply issues:**
   - Use 5V/2A USB power adapter (not computer USB)
   - Try different USB cable

2. **WiFi signal too weak:**
   - Move closer to router
   - Reduce WiFi power save:
     ```cpp
     WiFi.setSleep(false);
     ```

3. **Watchdog timeout:**
   - Add in loop():
     ```cpp
     yield();  // Or delay(1)
     ```

### SD card not detected

**Symptoms:** "SD card initialization failed"

**Solutions:**

1. **Verify wiring:**
   ```
   SD Card → ESP32-S3
   CS → GPIO 5
   MOSI → GPIO 23
   MISO → GPIO 19
   SCK → GPIO 18
   VCC → 3.3V
   GND → GND
   ```

2. **Format card:**
   - Must be FAT32
   - 32GB or smaller recommended

3. **Check SPI pins:**
   ```cpp
   SPI.begin(18, 19, 23, 5);  // SCK, MISO, MOSI, CS
   ```

---

## WebSocket Connection Issues

### "WebSocket connection failed" error

**Solutions:**

1. **Backend not running:**
   ```bash
   # In backend directory:
   python backend_example.py
   # Should see: "Uvicorn running on http://0.0.0.0:8000"
   ```

2. **Wrong URL:**
   ```typescript
   // Check src/config.ts:
   websocketUrl: 'ws://localhost:8000/ws/eeg'  // Not 'wss://' or 'http://'
   ```

3. **CORS issues:**
   ```python
   # In backend_example.py, verify:
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # Or specific frontend URL
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

4. **Firewall blocking:**
   - Allow port 8000 in firewall
   - Try temporarily disabling firewall to test

### Connection keeps dropping

**Solutions:**

1. **Increase timeout:**
   ```python
   # In backend WebSocket handler:
   await asyncio.sleep(0.1)  # Don't make this too large
   ```

2. **Network issues:**
   - Check for VPN interference
   - Try localhost instead of IP address

3. **Backend crashing:**
   - Check backend logs for errors
   - Ensure all dependencies installed

---

## LLaVA/AI Issues

### "ollama command not found"

**Solutions:**

1. **Install Ollama:**
   ```bash
   # Mac/Linux:
   curl https://ollama.ai/install.sh | sh

   # Windows:
   # Download from https://ollama.ai/download
   ```

2. **Add to PATH:**
   ```bash
   # Linux/Mac:
   export PATH=$PATH:/usr/local/bin

   # Windows:
   # Add to System Environment Variables
   ```

### LLaVA model not found

**Symptoms:** "model 'llava:13b' not found"

**Solutions:**

1. **Pull the model:**
   ```bash
   ollama pull llava:13b

   # Or smaller/faster version:
   ollama pull llava:7b
   ```

2. **Check installed models:**
   ```bash
   ollama list
   ```

3. **Disk space:**
   - LLaVA 13B needs ~8GB disk space
   - Check with: `df -h`

### AI interventions too slow

**Symptoms:** 30+ second delay for interventions

**Solutions:**

1. **Use smaller model:**
   ```bash
   ollama pull llava:7b
   ```

2. **Enable GPU acceleration:**
   ```bash
   # Check GPU is detected:
   nvidia-smi  # Should show your RTX 5060

   # Ensure CUDA is installed
   nvcc --version
   ```

3. **Increase GPU layers:**
   ```bash
   export OLLAMA_NUM_GPU_LAYERS=35
   ollama serve
   ```

4. **Run async:**
   ```python
   # In backend, use asyncio to avoid blocking:
   asyncio.create_task(query_llava_ollama(...))
   ```

### AI gives nonsensical responses

**Solutions:**

1. **Check prompt engineering:**
   - Ensure prompt is clear and specific
   - Add examples to prompt

2. **Temperature too high:**
   ```bash
   ollama run llava:13b --temperature 0.7
   ```

3. **Image quality poor:**
   - Ensure canvas exports at good resolution
   - Check image isn't too compressed

---

## EEG Signal Quality Issues

### Signal is too noisy

**Symptoms:** Charts show erratic, random fluctuations

**Solutions:**

1. **50/60Hz interference:**
   ```python
   # Add notch filter in backend:
   from scipy.signal import iirnotch
   b, a = iirnotch(60, 30, 250)  # 60Hz for US, 50Hz for EU
   filtered = filtfilt(b, a, signal)
   ```

2. **Poor electrode contact:**
   - Clean skin with alcohol wipe
   - Use electrode gel (for wet electrodes)
   - Ensure tight contact with sweatband

3. **EMG contamination:**
   - Relax facial muscles
   - Avoid jaw clenching
   - Keep head still

4. **Improve grounding:**
   - Ensure ground electrode is properly placed
   - Try different ground location

### All frequency bands show same values

**Symptoms:** Alpha, Beta, Gamma are identical

**Solutions:**

1. **DC offset issue:**
   ```python
   signal = signal - np.mean(signal)  # Remove DC offset
   ```

2. **Windowing not applied:**
   ```python
   window = np.hamming(len(signal))
   signal = signal * window
   ```

3. **Wrong FFT calculation:**
   - Verify using positive frequencies only
   - Check frequency bins are correct

### Readings don't change over time

**Symptoms:** Values are static, not updating

**Solutions:**

1. **ESP32 frozen:**
   - Check Serial Monitor for activity
   - Press reset button on ESP32

2. **Buffer not updating:**
   ```python
   print(f"Buffer size: {len(eeg_buffer)}")  # Should grow over time
   ```

3. **Frontend not receiving updates:**
   - Check WebSocket messages in browser DevTools
   - Network tab → WS → Messages

---

## General Debugging Tips

### Enable debug mode

1. **Frontend:**
   ```typescript
   // In src/config.ts:
   dev: {
     debug: true,
   }
   ```

2. **Backend:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **ESP32:**
   ```cpp
   Serial.setDebugOutput(true);
   ```

### Check system health

```bash
# Backend health check:
curl http://localhost:8000/health

# Should return:
# {
#   "status": "healthy",
#   "eeg_buffer_size": 256,
#   "receiving_data": true
# }
```

### Monitor network traffic

```bash
# Watch UDP packets (Linux/Mac):
sudo tcpdump -i any udp port 5005

# Watch WebSocket (browser):
# DevTools → Network → WS → Select connection → Messages
```

---

## Still Having Issues?

### Create a detailed bug report with:

1. **System info:**
   - OS and version
   - Python version
   - Node.js version
   - Browser and version

2. **Error messages:**
   - Full error text
   - Stack traces
   - Screenshots

3. **What you've tried:**
   - List troubleshooting steps attempted
   - Any changes that had an effect

4. **Hardware details:**
   - ESP32 board model
   - BioAmp version
   - WiFi router info

### Useful diagnostic commands:

```bash
# System info
python --version
node --version
npm --version

# Python packages
pip list | grep -E "fastapi|scipy|numpy"

# Check ports
netstat -tuln | grep -E "5005|8000"

# WiFi info
iwconfig  # Linux
# OR
networksetup -getairportnetwork en0  # Mac

# Process info
ps aux | grep python
ps aux | grep ollama
```

---

## Quick Reference

| Issue | Most Common Cause | Quick Fix |
|-------|------------------|-----------|
| No WebSocket connection | Backend not running | `python backend_example.py` |
| ESP32 won't connect | Wrong WiFi SSID/password | Double-check credentials |
| No EEG data | Wiring wrong | Verify pin connections |
| LLaVA errors | Model not downloaded | `ollama pull llava:13b` |
| Noisy signal | Poor electrode contact | Clean skin, tighten sweatband |
| Charts frozen | Frontend not updating | Refresh page, check console |

---

**Remember:** Most issues are configuration problems, not bugs. Double-check all settings before assuming hardware failure.
