/**
 * ESP32-S3 Firmware for BioAmp EXG Pill EEG Data Transmission
 *
 * Hardware Setup:
 * - BioAmp EXG Pill connected to ESP32-S3 analog pin
 * - ESP32-S3 connected to WiFi
 * - Optional: SD card for local logging
 *
 * This firmware:
 * 1. Reads analog voltage from BioAmp EXG Pill at 250Hz
 * 2. Sends raw data via UDP to your laptop's FastAPI server
 * 3. Optionally logs to SD card for ML dataset building
 *
 * Upload using Arduino IDE or PlatformIO
 */

#include <WiFi.h>
#include <WiFiUdp.h>
#include <SD.h>
#include <SPI.h>

// ============================================================================
// Configuration
// ============================================================================

// WiFi credentials
const char* WIFI_SSID = "YourWiFiSSID";
const char* WIFI_PASSWORD = "YourWiFiPassword";

// UDP target (your laptop's IP address)
const char* UDP_TARGET_IP = "192.168.1.100";  // CHANGE THIS to your laptop's IP
const int UDP_TARGET_PORT = 5005;

// EEG sensor configuration
const int EEG_PIN = 34;              // Analog pin connected to BioAmp EXG Pill
const int SAMPLE_RATE = 250;         // Hz (samples per second)
const int SAMPLE_INTERVAL_US = 1000000 / SAMPLE_RATE;  // 4000 microseconds

// SD card logging (optional)
const bool ENABLE_SD_LOGGING = true;
const int SD_CS_PIN = 5;             // SD card chip select pin
String currentLogFile = "";
unsigned long sessionStartTime = 0;

// ============================================================================
// Global Variables
// ============================================================================

WiFiUDP udp;
bool wifiConnected = false;
unsigned long lastSampleTime = 0;
unsigned long sampleCount = 0;
File dataFile;

// ============================================================================
// Setup
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("🧠 EEG Data Logger - ESP32-S3");
  Serial.println("================================");

  // Initialize analog pin
  pinMode(EEG_PIN, INPUT);
  analogSetAttenuation(ADC_11db);  // 0-3.3V range

  // Connect to WiFi
  connectWiFi();

  // Initialize SD card (optional)
  if (ENABLE_SD_LOGGING) {
    initSDCard();
  }

  Serial.println("✓ Initialization complete");
  Serial.println("📡 Starting EEG data transmission...\n");

  sessionStartTime = millis();
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
  unsigned long currentTime = micros();

  // Sample at precisely 250Hz
  if (currentTime - lastSampleTime >= SAMPLE_INTERVAL_US) {
    lastSampleTime = currentTime;

    // Read analog voltage from BioAmp EXG Pill
    int rawValue = analogRead(EEG_PIN);

    // Convert to voltage (0-3.3V)
    // The BioAmp EXG Pill outputs a centered signal around 1.65V
    float voltage = (rawValue / 4095.0) * 3.3;

    // Send via UDP
    if (wifiConnected) {
      sendUDP(voltage);
    }

    // Log to SD card (optional)
    if (ENABLE_SD_LOGGING && dataFile) {
      logToSD(voltage);
    }

    sampleCount++;

    // Print status every 1000 samples (4 seconds at 250Hz)
    if (sampleCount % 1000 == 0) {
      Serial.printf("📊 Samples: %lu | Voltage: %.3fV | WiFi: %s\n",
                    sampleCount, voltage, wifiConnected ? "✓" : "✗");
    }
  }

  // Check WiFi connection periodically
  if (millis() % 10000 == 0) {  // Every 10 seconds
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("⚠️  WiFi disconnected. Reconnecting...");
      wifiConnected = false;
      connectWiFi();
    }
  }
}

// ============================================================================
// WiFi Connection
// ============================================================================

void connectWiFi() {
  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\n✓ WiFi connected!");
    Serial.printf("📍 ESP32 IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("📡 Sending to: %s:%d\n", UDP_TARGET_IP, UDP_TARGET_PORT);

    udp.begin(UDP_TARGET_PORT);
  } else {
    wifiConnected = false;
    Serial.println("\n✗ WiFi connection failed!");
    Serial.println("⚠️  Will continue without network transmission");
  }
}

// ============================================================================
// UDP Transmission
// ============================================================================

void sendUDP(float voltage) {
  // Pack voltage as float32 for transmission
  uint8_t buffer[4];
  memcpy(buffer, &voltage, sizeof(float));

  udp.beginPacket(UDP_TARGET_IP, UDP_TARGET_PORT);
  udp.write(buffer, 4);
  udp.endPacket();
}

// ============================================================================
// SD Card Logging (Optional - for ML dataset)
// ============================================================================

void initSDCard() {
  Serial.println("Initializing SD card...");

  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("✗ SD card initialization failed!");
    Serial.println("⚠️  Continuing without SD logging");
    return;
  }

  Serial.println("✓ SD card initialized");

  // Create new log file with DSC prefix (not test_)
  // This matches the firmware's file-scanning logic mentioned in requirements
  int sessionId = millis() / 1000;  // Use timestamp as session ID
  currentLogFile = "/DSC_" + String(sessionId) + ".csv";

  dataFile = SD.open(currentLogFile.c_str(), FILE_WRITE);

  if (dataFile) {
    // Write CSV header
    dataFile.println("timestamp_ms,voltage_v,raw_value");
    dataFile.close();
    Serial.printf("✓ Logging to: %s\n", currentLogFile.c_str());
  } else {
    Serial.println("✗ Failed to create log file!");
  }
}

void logToSD(float voltage) {
  // Write to SD card every 10 samples to reduce wear
  static int logCounter = 0;
  static String logBuffer = "";

  unsigned long timestamp = millis() - sessionStartTime;
  int rawValue = analogRead(EEG_PIN);

  // Add to buffer
  logBuffer += String(timestamp) + "," + String(voltage, 4) + "," + String(rawValue) + "\n";
  logCounter++;

  // Flush buffer every 10 samples
  if (logCounter >= 10) {
    dataFile = SD.open(currentLogFile.c_str(), FILE_APPEND);
    if (dataFile) {
      dataFile.print(logBuffer);
      dataFile.close();
    }
    logBuffer = "";
    logCounter = 0;
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

void printStatus() {
  Serial.println("\n================================");
  Serial.println("Status:");
  Serial.printf("  Session Time: %lu seconds\n", (millis() - sessionStartTime) / 1000);
  Serial.printf("  Total Samples: %lu\n", sampleCount);
  Serial.printf("  Sample Rate: %d Hz\n", SAMPLE_RATE);
  Serial.printf("  WiFi: %s\n", wifiConnected ? "Connected" : "Disconnected");

  if (ENABLE_SD_LOGGING) {
    Serial.printf("  SD Logging: %s\n", dataFile ? "Active" : "Inactive");
    Serial.printf("  Log File: %s\n", currentLogFile.c_str());
  }

  Serial.println("================================\n");
}

// ============================================================================
// Optional: Serial Commands
// ============================================================================

void serialEvent() {
  if (Serial.available()) {
    char cmd = Serial.read();

    switch (cmd) {
      case 's':
        printStatus();
        break;

      case 'r':
        Serial.println("Restarting ESP32...");
        ESP.restart();
        break;

      case 'c':
        Serial.println("Reconnecting WiFi...");
        connectWiFi();
        break;

      case 'h':
        Serial.println("\nCommands:");
        Serial.println("  s - Show status");
        Serial.println("  r - Restart ESP32");
        Serial.println("  c - Reconnect WiFi");
        Serial.println("  h - Show this help\n");
        break;
    }
  }
}

/**
 * HARDWARE CONNECTION GUIDE
 * ==========================
 *
 * BioAmp EXG Pill to ESP32-S3:
 * - VCC → 3.3V
 * - GND → GND
 * - OUT → GPIO 34 (analog input)
 *
 * Electrode Placement (for EEG):
 * - Reference electrode → Earlobe or mastoid process
 * - Ground electrode → Forehead (Fpz location)
 * - Active electrode → Frontal lobe (Fp1 or Fp2 location)
 *   - Attach to sports sweatband with dry electrode
 *
 * SD Card (Optional):
 * - CS → GPIO 5
 * - MOSI → GPIO 23
 * - MISO → GPIO 19
 * - SCK → GPIO 18
 * - VCC → 3.3V
 * - GND → GND
 *
 * CONFIGURATION CHECKLIST
 * =======================
 *
 * Before uploading:
 * 1. ✓ Change WIFI_SSID and WIFI_PASSWORD
 * 2. ✓ Change UDP_TARGET_IP to your laptop's IP address
 *    - Find on Windows: ipconfig
 *    - Find on Mac/Linux: ifconfig or ip addr
 * 3. ✓ Verify EEG_PIN matches your wiring
 * 4. ✓ Set ENABLE_SD_LOGGING based on your setup
 *
 * UPLOAD INSTRUCTIONS
 * ===================
 *
 * Arduino IDE:
 * 1. Install ESP32 board support: https://docs.espressif.com/projects/arduino-esp32/
 * 2. Select board: "ESP32S3 Dev Module"
 * 3. Select port: Your ESP32's COM/serial port
 * 4. Click Upload
 *
 * PlatformIO (platformio.ini):
 *
 * [env:esp32-s3-devkitc-1]
 * platform = espressif32
 * board = esp32-s3-devkitc-1
 * framework = arduino
 * monitor_speed = 115200
 *
 * TROUBLESHOOTING
 * ===============
 *
 * No data received on laptop:
 * - Check ESP32 IP address matches your network
 * - Verify laptop firewall allows UDP port 5005
 * - Ensure ESP32 and laptop are on same WiFi network
 * - Check Serial Monitor for connection status
 *
 * Noisy EEG signal:
 * - Ensure proper electrode contact (use conductive gel if using wet electrodes)
 * - Check for 50/60Hz interference from power lines
 * - Verify ground electrode is properly connected
 * - Keep wires away from power cables
 *
 * SD card not detected:
 * - Verify SD card is formatted as FAT32
 * - Check CS pin matches your wiring
 * - Ensure 3.3V power supply (NOT 5V!)
 * - Try a different SD card
 */
