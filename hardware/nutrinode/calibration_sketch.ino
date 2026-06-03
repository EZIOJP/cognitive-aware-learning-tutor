/*
 * NutriNode — Scale Calibration Sketch
 *
 * Run this ONCE before flashing the main firmware.
 * Steps:
 *   1. Flash this sketch to the ESP32-CAM
 *   2. Open Serial Monitor at 115200 baud
 *   3. Follow the prompts — put a known-weight object on the scale
 *   4. Copy the calibration factor into nutrinode_firmware.ino → CALIBRATION_FACTOR
 */

#include "HX711.h"

#define LOADCELL_DOUT_PIN 14
#define LOADCELL_SCK_PIN  15

HX711 scale;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== NutriNode Scale Calibration ===\n");

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

  Serial.println("Step 1: Remove everything from the scale.");
  Serial.println("        Press any key when ready...");
  while (!Serial.available()) delay(100);
  Serial.read();

  scale.set_scale();
  scale.tare();
  Serial.println("✅ Scale zeroed.\n");

  Serial.println("Step 2: Place a known weight on the scale.");
  Serial.println("        Enter the weight in GRAMS in Serial Monitor and press Enter.");
  Serial.println("        (e.g. use a 200g known weight, a water bottle you weighed, etc.)");

  while (!Serial.available()) delay(100);
  float knownWeight = Serial.parseFloat();
  Serial.printf("Known weight entered: %.1f g\n\n", knownWeight);

  Serial.println("Measuring raw reading (10 samples)...");
  long rawReading = scale.get_units(10);
  Serial.printf("Raw reading: %ld\n", rawReading);

  float calibrationFactor = (float)rawReading / knownWeight;
  Serial.printf("\n✅ YOUR CALIBRATION FACTOR: %.2f\n", calibrationFactor);
  Serial.println("   Copy this into nutrinode_firmware.ino → CALIBRATION_FACTOR\n");

  // Verify
  scale.set_scale(calibrationFactor);
  Serial.println("Verification (leave the weight on):");
  for (int i = 0; i < 5; i++) {
    Serial.printf("  Reading: %.1f g\n", scale.get_units(5));
    delay(1000);
  }

  Serial.println("\nCalibration complete! Flash the main firmware now.");
}

void loop() {
  // Show live readings for verification
  if (scale.is_ready()) {
    Serial.printf("Live: %.1f g\n", scale.get_units(5));
  }
  delay(1000);
}
