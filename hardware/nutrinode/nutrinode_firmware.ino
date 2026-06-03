/*
 * NutriNode Firmware v1.0
 * Hardware: ESP32-CAM (AI-Thinker) + HX711 Load Cell
 *
 * Wiring:
 *   HX711 DOUT → GPIO 14
 *   HX711 SCK  → GPIO 15
 *   (GPIO 4 = Flash LED, used for photo lighting)
 *
 * Libraries needed (install in Arduino IDE):
 *   - HX711 by Bogdan Necula (Library Manager)
 *   - ESP32 board support by Espressif
 *
 * Board: AI Thinker ESP32-CAM
 * Partition scheme: Huge APP (3MB No OTA)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "HX711.h"

// ── Pinout (AI-Thinker ESP32-CAM) ───────────────────────────────────────────
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define FLASH_LED_PIN      4

// ── HX711 ────────────────────────────────────────────────────────────────────
#define LOADCELL_DOUT_PIN 14
#define LOADCELL_SCK_PIN  15
HX711 scale;

// ── Network config — CHANGE THESE ────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASS     = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL    = "http://192.168.1.X:8000/api/nutrition/log";
const char* LOCATION_TAG  = "home";  // e.g. "restaurant_xyz", "office", "home"

// ── Calibration — run calibration sketch first ───────────────────────────────
// Replace this with your load cell's calibration factor
float CALIBRATION_FACTOR = 2280.0f;

// ── Thresholds ────────────────────────────────────────────────────────────────
const float MIN_PLATE_WEIGHT_G  = 50.0f;   // ignore anything lighter
const float TRIGGER_DELTA_G     = 20.0f;   // trigger when weight increases by this much
const float EMPTY_PLATE_G       = 10.0f;   // consider plate removed below this

// ── State ─────────────────────────────────────────────────────────────────────
float     lastWeight      = 0.0f;
bool      platePresent    = false;
uint32_t  lastSendMs      = 0;
const uint32_t COOLDOWN_MS = 10000;  // 10s cooldown between sends

// ─────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n🚀 NutriNode Booting...");

  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);

  // ── Init Camera ──
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_VGA;   // 640×480, good balance of quality/speed
  config.jpeg_quality = 12;              // 10–63, lower = higher quality
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed: 0x%x\n", err);
    delay(5000);
    ESP.restart();
  }

  // Improve image quality settings
  sensor_t* s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_contrast(s, 1);
  s->set_saturation(s, 0);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_exposure_ctrl(s, 1);
  s->set_aec2(s, 1);
  Serial.println("✅ Camera initialized");

  // ── Init Scale ──
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  scale.set_scale(CALIBRATION_FACTOR);
  scale.tare();
  Serial.println("✅ Scale tared (zeroed)");

  // ── Connect WiFi ──
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("📡 Connecting to WiFi");
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n✅ WiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n⚠️ WiFi failed. Running in offline mode (no uploads).");
  }

  Serial.println("👁️  Watching for food...\n");
}

// ─────────────────────────────────────────────────────────────────────────────
void loop() {
  if (!scale.is_ready()) { delay(100); return; }

  float weight = scale.get_units(5);  // average 5 readings
  if (weight < 0) weight = 0;

  uint32_t now = millis();

  // ── Plate removed ──
  if (weight < EMPTY_PLATE_G && platePresent) {
    Serial.println("🍽️  Plate removed. Resetting.");
    platePresent = false;
    lastWeight   = 0.0f;
  }

  // ── New food detected ──
  bool significantWeight = weight > MIN_PLATE_WEIGHT_G;
  bool bigEnoughDelta    = (weight - lastWeight) > TRIGGER_DELTA_G;
  bool cooledDown        = (now - lastSendMs) > COOLDOWN_MS;

  if (significantWeight && bigEnoughDelta && cooledDown) {
    Serial.printf("🔍 Detected %.1fg on plate. Capturing...\n", weight);
    platePresent = true;
    lastWeight   = weight;
    lastSendMs   = now;

    // Flash LED for photo lighting
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(100);  // let exposure adjust

    camera_fb_t* fb = esp_camera_fb_get();

    digitalWrite(FLASH_LED_PIN, LOW);

    if (!fb) {
      Serial.println("❌ Camera capture failed");
      return;
    }

    Serial.printf("📷 Photo captured: %u bytes\n", fb->len);

    if (WiFi.status() == WL_CONNECTED) {
      sendToServer(fb->buf, fb->len, weight);
    } else {
      Serial.println("⚠️ No WiFi — skipping upload");
    }

    esp_camera_fb_return(fb);
  }

  delay(1000);
}

// ─────────────────────────────────────────────────────────────────────────────
void sendToServer(uint8_t* imageData, size_t imageLen, float weight) {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.setTimeout(15000);

  String boundary = "----NutriNodeBoundary7382";
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  // ── Build multipart body ──
  String partWeight = "--" + boundary + "\r\n"
    "Content-Disposition: form-data; name=\"weight_grams\"\r\n\r\n" +
    String(weight, 1) + "\r\n";

  String partLocation = "--" + boundary + "\r\n"
    "Content-Disposition: form-data; name=\"location_tag\"\r\n\r\n" +
    String(LOCATION_TAG) + "\r\n";

  String partSource = "--" + boundary + "\r\n"
    "Content-Disposition: form-data; name=\"source\"\r\n\r\n"
    "esp32_cam\r\n";

  String partImageHeader = "--" + boundary + "\r\n"
    "Content-Disposition: form-data; name=\"image\"; filename=\"plate.jpg\"\r\n"
    "Content-Type: image/jpeg\r\n\r\n";

  String bodyEnd = "\r\n--" + boundary + "--\r\n";

  size_t totalLen = partWeight.length() + partLocation.length() +
                    partSource.length() + partImageHeader.length() +
                    imageLen + bodyEnd.length();

  // ── Allocate and build payload ──
  uint8_t* payload = (uint8_t*)ps_malloc(totalLen);  // use PSRAM
  if (!payload) {
    Serial.println("❌ Out of memory for payload");
    return;
  }

  size_t offset = 0;
  auto appendStr = [&](const String& s) {
    memcpy(payload + offset, s.c_str(), s.length());
    offset += s.length();
  };

  appendStr(partWeight);
  appendStr(partLocation);
  appendStr(partSource);
  appendStr(partImageHeader);
  memcpy(payload + offset, imageData, imageLen);  offset += imageLen;
  appendStr(bodyEnd);

  // ── Send ──
  Serial.printf("📤 Sending %.1fg + %u byte image to server...\n", weight, imageLen);
  int httpCode = http.POST(payload, totalLen);
  free(payload);

  if (httpCode == 200) {
    String response = http.getString();
    Serial.printf("✅ Server response (%d): %s\n", httpCode, response.c_str());

    // Parse and display result
    DynamicJsonDocument doc(512);
    if (deserializeJson(doc, response) == DeserializationError::Ok) {
      Serial.printf("🍽️  Identified: %s | %.0f kcal\n",
        doc["food_item"].as<const char*>(),
        doc["total_kcal"].as<float>());
    }
  } else {
    Serial.printf("❌ Server error: %d\n", httpCode);
    Serial.println(http.getString());
  }

  http.end();
}
