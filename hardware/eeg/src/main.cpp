/**
 * CALT EEG logger — ESP32-S3 + BioAmp EXG Pill
 *
 * Principles:
 *  - Sampling never blocks on WiFi/SD failures (after setup)
 *  - SD CSV is the durable dump (timestamped)
 *  - UDP to CALT is best-effort
 *  - Soft-fail everywhere; Serial status only
 *
 * Setup:
 *  1. copy src/secrets.h.example → src/secrets.h and edit
 *     (or run scripts\flash_eeg.bat / pio run — auto-creates secrets.h)
 *  2. scripts\flash_eeg.bat  OR  pio run -t upload
 *
 * Serial (while sampling):
 *  s = status, c = reconnect WiFi, n = NTP retry, r = restart, h = help
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <SD.h>
#include <SPI.h>
#include <time.h>
#include <string.h>
#include "esp32-hal-rgb-led.h"

#include "secrets.h"

// Defaults if an older secrets.h omits SPI pin overrides
#ifndef SD_SCK_PIN
#define SD_SCK_PIN 12
#endif
#ifndef SD_MISO_PIN
#define SD_MISO_PIN 13
#endif
#ifndef SD_MOSI_PIN
#define SD_MOSI_PIN 11
#endif

// Onboard RGB (WS2812) — ESP32-S3-DevKitC-1 is often GPIO 38 or 48
#ifndef RGB_LED_PIN
#if defined(RGB_BUILTIN)
#define RGB_LED_PIN RGB_BUILTIN
#else
#define RGB_LED_PIN 38
#endif
#endif

static_assert(SAMPLE_RATE_HZ >= 50 && SAMPLE_RATE_HZ <= 500, "sample rate out of range");

namespace {

constexpr uint32_t kSampleIntervalUs = 1000000UL / SAMPLE_RATE_HZ;
constexpr size_t kSdFlushEvery = 25;  // ~100 ms at 250 Hz
constexpr uint32_t kWifiRetryMs = 15000;
constexpr uint32_t kNtpRetryMs = 60000;
constexpr uint32_t kNtpTimeoutMs = 8000;
constexpr const char *kNtpServer = "pool.ntp.org";
constexpr size_t kCsvLineMax = 96;
constexpr size_t kCsvBufMax = kCsvLineMax * (kSdFlushEvery + 2);

WiFiUDP gUdp;
bool gWifiOk = false;
bool gNtpOk = false;
bool gSdOk = false;
char gLogPath[40] = {0};
File gLogFile;

unsigned long gSessionStartMs = 0;
unsigned long gLastSampleUs = 0;
unsigned long gLastWifiAttemptMs = 0;
unsigned long gLastNtpAttemptMs = 0;
uint32_t gSampleCount = 0;
uint32_t gUdpFail = 0;
uint32_t gSdFail = 0;

char gCsvBuf[kCsvBufMax];
size_t gCsvLen = 0;
size_t gCsvLines = 0;

uint8_t gLedR = 0;
uint8_t gLedG = 0;
uint8_t gLedB = 0;
uint8_t gLedHoldR = 0;
uint8_t gLedHoldG = 0;
uint8_t gLedHoldB = 0;

// 0=off/solid hold, 1=slow blink, 2=fast blink, 3=double, 4=heartbeat
uint8_t gLedPattern = 0;
unsigned long gLedPatMs = 0;
uint8_t gLedPatStep = 0;

void applyLed(uint8_t r, uint8_t g, uint8_t b) {
  gLedR = r;
  gLedG = g;
  gLedB = b;
  // Drive common S3 DevKit RGB pins (board revisions differ)
  neopixelWrite(RGB_LED_PIN, r, g, b);
#if RGB_LED_PIN != 48
  neopixelWrite(48, r, g, b);
#endif
#if RGB_LED_PIN != 38
  neopixelWrite(38, r, g, b);
#endif
}

void setLedSolid(uint8_t r, uint8_t g, uint8_t b) {
  gLedPattern = 0;
  gLedPatStep = 0;
  gLedHoldR = r;
  gLedHoldG = g;
  gLedHoldB = b;
  applyLed(r, g, b);
  Serial.printf("[eeg] LED %s\n", (r | g | b) ? "ON" : "OFF");
}

void setLedPattern(uint8_t pattern) {
  gLedPattern = pattern;
  gLedPatMs = millis();
  gLedPatStep = 0;
  if (pattern == 0) {
    applyLed(0, 0, 0);
    gLedHoldR = gLedHoldG = gLedHoldB = 0;
    Serial.println("[eeg] LED pattern OFF");
    return;
  }
  // Patterns use white system LED only
  gLedHoldR = gLedHoldG = gLedHoldB = 255;
  applyLed(255, 255, 255);
  Serial.printf("[eeg] LED pattern=%u\n", pattern);
}

void serviceLed() {
  if (gLedPattern == 0) {
    return;
  }
  const unsigned long now = millis();
  const unsigned long elapsed = now - gLedPatMs;

  auto white = [](bool on) { applyLed(on ? 255 : 0, on ? 255 : 0, on ? 255 : 0); };

  if (gLedPattern == 1) {
    // slow blink ~1 Hz
    white((elapsed / 500) % 2 == 0);
  } else if (gLedPattern == 2) {
    // fast blink ~4 Hz
    white((elapsed / 125) % 2 == 0);
  } else if (gLedPattern == 3) {
    // double blink every 1.2s: on 120, off 120, on 120, off rest
    const unsigned long t = elapsed % 1200;
    white(t < 120 || (t >= 240 && t < 360));
  } else if (gLedPattern == 4) {
    // heartbeat: short-short-pause
    const unsigned long t = elapsed % 1000;
    white(t < 80 || (t >= 160 && t < 240));
  }
}

void pulseLed(uint8_t r, uint8_t g, uint8_t b, uint32_t ms = 250) {
  // Ignore one-shot flashes while a pattern is running
  if (gLedPattern != 0) {
    return;
  }
  (void)r;
  (void)g;
  (void)b;
  (void)ms;
  // no-op in on/off mode — keep sampling non-blocking
}

uint64_t nowUnixMs() {
  if (!gNtpOk) {
    return 0;
  }
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  return (uint64_t)tv.tv_sec * 1000ULL + (uint64_t)(tv.tv_usec / 1000);
}

uint64_t sampleUnixMs() {
  if (gNtpOk) {
    return nowUnixMs();
  }
  // Relative timeline until NTP — still useful for ordering
  return (uint64_t)(millis() - gSessionStartMs);
}

void tryNtp() {
  if (!gWifiOk) {
    gNtpOk = false;
    return;
  }
  gLastNtpAttemptMs = millis();
  configTime(0, 0, kNtpServer);  // UTC
  const unsigned long start = millis();
  time_t now = 0;
  while (millis() - start < kNtpTimeoutMs) {
    time(&now);
    if (now > 1700000000) {  // sanity: after 2023
      gNtpOk = true;
      Serial.println("[eeg] NTP synced (UTC)");
      return;
    }
    delay(200);
  }
  gNtpOk = false;
  Serial.println("[eeg] NTP timeout — logging boot_ms only until sync");
}

void maybeRetryNtp() {
#if ENABLE_WIFI
  if (!gWifiOk || gNtpOk) {
    return;
  }
  const unsigned long now = millis();
  if (now - gLastNtpAttemptMs < kNtpRetryMs) {
    return;
  }
  Serial.println("[eeg] NTP retry...");
  tryNtp();
#endif
}

bool connectWifi(bool blocking) {
#if !ENABLE_WIFI
  (void)blocking;
  gWifiOk = false;
  return false;
#else
  if (WiFi.status() == WL_CONNECTED) {
    gWifiOk = true;
    return true;
  }
  Serial.printf("[eeg] WiFi connecting: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  const int maxAttempts = blocking ? 40 : 10;
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < maxAttempts) {
    delay(250);
    Serial.print('.');
    attempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    gWifiOk = true;
    Serial.printf("[eeg] WiFi OK  ip=%s  → udp %s:%d\n",
                  WiFi.localIP().toString().c_str(), UDP_TARGET_IP, UDP_TARGET_PORT);
    gUdp.begin(0);  // ephemeral local port
    tryNtp();
    return true;
  }

  gWifiOk = false;
  gNtpOk = false;
  Serial.println("[eeg] WiFi failed — continuing (SD / local sample only)");
  return false;
#endif
}

void maybeReconnectWifi() {
#if ENABLE_WIFI
  if (WiFi.status() == WL_CONNECTED) {
    gWifiOk = true;
    maybeRetryNtp();
    return;
  }
  gWifiOk = false;
  gNtpOk = false;
  const unsigned long now = millis();
  if (now - gLastWifiAttemptMs < kWifiRetryMs) {
    return;
  }
  gLastWifiAttemptMs = now;
  connectWifi(false);
#endif
}

bool openNewLogFile() {
  if (gNtpOk) {
    time_t now = time(nullptr);
    struct tm t;
    gmtime_r(&now, &t);
    snprintf(gLogPath, sizeof(gLogPath), "/DSC_%04d%02d%02d_%02d%02d%02d.csv",
             t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
  } else {
    snprintf(gLogPath, sizeof(gLogPath), "/DSC_boot_%lu.csv", (unsigned long)(millis() / 1000));
  }
  gLogFile = SD.open(gLogPath, FILE_WRITE);
  if (!gLogFile) {
    Serial.printf("[eeg] SD open failed: %s\n", gLogPath);
    gSdOk = false;
    return false;
  }
  gLogFile.println("unix_ms,boot_ms,voltage_v,raw_adc,wifi,ntp");
  gLogFile.flush();
  Serial.printf("[eeg] SD logging → %s\n", gLogPath);
  return true;
}

void initSd() {
#if !ENABLE_SD_LOGGING
  gSdOk = false;
  return;
#else
  Serial.println("[eeg] SD init...");
  SPI.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, SD_CS_PIN);
  if (!SD.begin(SD_CS_PIN, SPI)) {
    Serial.println("[eeg] SD missing/failed — continuing without log dump");
    gSdOk = false;
    return;
  }
  gSdOk = openNewLogFile();
#endif
}

void flushSdBuffer() {
  if (!gSdOk || gCsvLines == 0) {
    return;
  }
  if (!gLogFile) {
    gLogFile = SD.open(gLogPath, FILE_APPEND);
  }
  if (!gLogFile) {
    gSdFail++;
    gCsvLen = 0;
    gCsvLines = 0;
    return;
  }
  gLogFile.write(reinterpret_cast<const uint8_t *>(gCsvBuf), gCsvLen);
  gLogFile.flush();
  gCsvLen = 0;
  gCsvLines = 0;
}

void logSample(uint64_t unixMs, unsigned long bootMs, float voltage, int raw) {
#if !ENABLE_SD_LOGGING
  (void)unixMs;
  (void)bootMs;
  (void)voltage;
  (void)raw;
  return;
#else
  if (!gSdOk) {
    return;
  }
  char line[kCsvLineMax];
  const int n = snprintf(line, sizeof(line), "%llu,%lu,%.4f,%d,%d,%d\n",
                         (unsigned long long)unixMs, bootMs, voltage, raw, gWifiOk ? 1 : 0,
                         gNtpOk ? 1 : 0);
  if (n <= 0 || (size_t)n >= sizeof(line)) {
    return;
  }
  if (gCsvLen + (size_t)n >= sizeof(gCsvBuf)) {
    flushSdBuffer();
  }
  memcpy(gCsvBuf + gCsvLen, line, (size_t)n);
  gCsvLen += (size_t)n;
  gCsvLines++;
  if (gCsvLines >= kSdFlushEvery) {
    flushSdBuffer();
  }
#endif
}

void sendUdp(float voltage) {
#if !ENABLE_UDP
  (void)voltage;
  return;
#else
  if (!gWifiOk || WiFi.status() != WL_CONNECTED) {
    return;
  }
  uint8_t buf[4];
  memcpy(buf, &voltage, sizeof(float));
  if (!gUdp.beginPacket(UDP_TARGET_IP, UDP_TARGET_PORT)) {
    gUdpFail++;
    return;
  }
  gUdp.write(buf, 4);
  if (!gUdp.endPacket()) {
    gUdpFail++;
  }
#endif
}

float readVoltage(int *rawOut) {
#if SELF_TEST_MODE
  // Quiet baseline ~1.65 V with a sharp "snap" pulse every N seconds
  static unsigned long lastSnapMs = 0;
  static unsigned long snapUntilUs = 0;
  const unsigned long nowMs = millis();
  const unsigned long nowUs = micros();
  if (lastSnapMs == 0) {
    lastSnapMs = nowMs;
  }
  if (nowMs - lastSnapMs >= (unsigned long)SELF_TEST_SNAP_EVERY_S * 1000UL) {
    lastSnapMs = nowMs;
    snapUntilUs = nowUs + 8000UL;  // ~8 ms spike at 250 Hz (~2 samples)
    Serial.println("[eeg] SELF_TEST SNAP");
    pulseLed(0, 255, 80, 180);  // green flash on each self-test snap
  }
  float voltage = 1.65f;
  if (nowUs < snapUntilUs) {
    voltage = 2.85f;  // clear transient above baseline
  } else {
    // tiny noise so FFT has something
    voltage += ((int)(nowUs % 17) - 8) * 0.002f;
  }
  const int raw = (int)constrain(voltage / 3.3f * 4095.0f, 0.0f, 4095.0f);
  if (rawOut) {
    *rawOut = raw;
  }
  return voltage;
#else
  const int raw = analogRead(EEG_PIN);
  if (rawOut) {
    *rawOut = raw;
  }
  return (raw / 4095.0f) * 3.3f;
#endif
}

void printHeartbeat() {
  Serial.printf(
      "[eeg] n=%lu  wifi=%s ntp=%s sd=%s  udp_fail=%lu sd_fail=%lu  v=~live\n",
      (unsigned long)gSampleCount,
      gWifiOk ? "ok" : "off",
      gNtpOk ? "ok" : "off",
      gSdOk ? "ok" : "off",
      (unsigned long)gUdpFail,
      (unsigned long)gSdFail);
}

void printStatus() {
  Serial.println("================================");
  Serial.printf("  session_s=%lu  samples=%lu  rate=%d Hz\n",
                (millis() - gSessionStartMs) / 1000UL, (unsigned long)gSampleCount, SAMPLE_RATE_HZ);
  Serial.printf("  wifi=%s  ntp=%s  sd=%s  pin=%d\n", gWifiOk ? "ok" : "off", gNtpOk ? "ok" : "off",
                gSdOk ? "ok" : "off", EEG_PIN);
  Serial.printf("  udp=%s:%d  fails=%lu\n", UDP_TARGET_IP, UDP_TARGET_PORT, (unsigned long)gUdpFail);
  if (gSdOk) {
    Serial.printf("  sd_file=%s  sd_fail=%lu\n", gLogPath, (unsigned long)gSdFail);
  }
#if SELF_TEST_MODE
  Serial.println("  mode=SELF_TEST (set SELF_TEST_MODE 0 for BioAmp)");
#else
  Serial.println("  mode=LIVE_ADC");
#endif
  Serial.println("================================");
}

void handleSerial() {
  while (Serial.available()) {
    const char cmd = (char)Serial.read();
    switch (cmd) {
      case 's':
      case 'S':
        printStatus();
        break;
      case 'c':
      case 'C':
        Serial.println("[eeg] WiFi reconnect...");
        gLastWifiAttemptMs = 0;
        connectWifi(true);
        break;
      case 'n':
      case 'N':
        Serial.println("[eeg] NTP force...");
        gLastNtpAttemptMs = 0;
        tryNtp();
        break;
      case 'x':
      case 'X':
        Serial.println("[eeg] restart...");
        delay(100);
        ESP.restart();
        break;
      case '0':
        setLedSolid(0, 0, 0);
        break;
      case '1':
        setLedSolid(255, 255, 255);
        break;
      case '2':
        setLedPattern(1);  // slow blink
        break;
      case '3':
        setLedPattern(2);  // fast blink
        break;
      case '4':
        setLedPattern(3);  // double
        break;
      case '5':
        setLedPattern(4);  // heartbeat
        break;
      case 'h':
      case 'H':
      case '?':
        Serial.println("cmds: 0=off 1=on 2=slow 3=fast 4=double 5=heartbeat");
        Serial.println("      s=status c=wifi n=ntp x=restart h=help");
        break;
      case 'r':
      case 'R':
        Serial.println("[eeg] restart...");
        delay(100);
        ESP.restart();
        break;
      default:
        break;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(800);
  Serial.println();
  Serial.println("=== CALT EEG (BioAmp EXG Pill / ESP32-S3) ===");
  Serial.println("Soft-fail mode: WiFi/SD optional; sampling always runs.");
#if SELF_TEST_MODE
  Serial.println("[eeg] SELF_TEST_MODE=1 — synthetic snaps (no BioAmp). Set 0 for real Pill.");
#else
  Serial.println("[eeg] LIVE ADC — BioAmp on EEG_PIN");
#endif

  analogReadResolution(12);
#if !SELF_TEST_MODE
  analogSetPinAttenuation(EEG_PIN, ADC_11db);
  pinMode(EEG_PIN, INPUT);
#endif

  setLedSolid(0, 0, 0);  // start off — webapp turns on
  Serial.printf("[eeg] system LED pin=%d (also tries 38/48) — on/off + patterns\n", RGB_LED_PIN);

  gSessionStartMs = millis();
  gLastWifiAttemptMs = 0;
  gLastNtpAttemptMs = 0;
  gCsvBuf[0] = '\0';

  connectWifi(true);
  initSd();

  gLastSampleUs = micros();
  Serial.printf("[eeg] sampling %d Hz  pin=%d  udp=%s:%d\n", SAMPLE_RATE_HZ, EEG_PIN, UDP_TARGET_IP,
                UDP_TARGET_PORT);
  Serial.println("[eeg] ready — LED: 0=off 1=on 2-5=patterns");
}

void loop() {
  handleSerial();
  serviceLed();

  const unsigned long nowUs = micros();
  if (nowUs - gLastSampleUs < kSampleIntervalUs) {
    maybeReconnectWifi();
    return;
  }
  // Catch up if we slipped (avoid burst storms: take one sample)
  gLastSampleUs = nowUs;

  int raw = 0;
  const float voltage = readVoltage(&raw);
  const unsigned long bootMs = millis() - gSessionStartMs;
  const uint64_t unixMs = sampleUnixMs();

  sendUdp(voltage);
  logSample(unixMs, bootMs, voltage, raw);

  gSampleCount++;
  if (gSampleCount % (SAMPLE_RATE_HZ * 4) == 0) {
    printHeartbeat();
    flushSdBuffer();
  }

  maybeReconnectWifi();
}
