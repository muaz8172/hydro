/*
 * EC sensor (EC V2.1) on ESP32 - measurement + calibration
 * Wiring: A0 -> GPIO34, VCC -> 3.3V, GND -> GND, T1 unconnected
 * Requires the patched DFRobot_EC.cpp (saves both K values, commits EEPROM)
 *
 * Serial Monitor: 115200 baud, line ending = Newline
 * Calibration:
 *   enterec -> probe in 1413 us/cm  -> wait 20 s -> calec
 *   rinse   -> probe in 12.88 ms/cm -> wait 20 s -> calec
 *   exitec  (saves both points)
 */

#include "DFRobot_EC.h"
#include <EEPROM.h>

#define EC_PIN      34      // A0 -> GPIO34 (ADC1)
#define SAMPLES     30      // readings averaged per measurement
#define KVALUEADDR  0x0A    // same address the library uses

float voltage = 0, ecValue = 0;
float temperature = 25.0;   // no DS18B20 yet -> fixed 25 C
int   rawValue = 0;
const char* adcRange = "0dB";
bool  belowRange = false;
DFRobot_EC ec;

// Read EC voltage in mV, choosing the best ADC range automatically
float readVoltage_mV()
{
  analogSetPinAttenuation(EC_PIN, ADC_0db);    // low range ~100-950 mV (more accurate)
  analogRead(EC_PIN);                          // dummy read after range change
  rawValue = analogRead(EC_PIN);

  if (rawValue < 3800) {
    adcRange = "0dB";
  } else {
    analogSetPinAttenuation(EC_PIN, ADC_11db); // wide range ~150-3100 mV
    analogRead(EC_PIN);
    rawValue = analogRead(EC_PIN);
    adcRange = "11dB";
  }

  // signal below the ESP32 ADC floor (~100 mV) -> report 0 instead of a fake value
  if (rawValue == 0) {
    belowRange = true;
    return 0;
  }
  belowRange = false;

  uint32_t sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogReadMilliVolts(EC_PIN);
    delay(2);
  }
  return sum / (float)SAMPLES;
}

void printStoredK()
{
  float kLow, kHigh;
  EEPROM.get(KVALUEADDR, kLow);
  EEPROM.get(KVALUEADDR + 4, kHigh);
  Serial.print("Stored calibration -> Klow: ");
  Serial.print(kLow, 3);
  Serial.print("  Khigh: ");
  Serial.println(kHigh, 3);
  if (kLow == 1.0 && kHigh == 1.0) {
    Serial.println("(default values - sensor NOT calibrated yet)");
  }
}

void setup()
{
  Serial.begin(115200);
  delay(500);
  EEPROM.begin(32);            // required on ESP32
  analogReadResolution(12);
  ec.begin();

  Serial.println();
  Serial.println("=== EC Sensor ready ===");
  printStoredK();
  Serial.println("Commands: enterec | calec | exitec");
  Serial.println();
}

void loop()
{
  static unsigned long timepoint = millis();
  if (millis() - timepoint > 1000U)            // every 1 s
  {
    timepoint = millis();
    voltage = readVoltage_mV();
    ecValue = ec.readEC(voltage, temperature);

    Serial.print("raw:");
    Serial.print(rawValue);
    Serial.print("  range:");
    Serial.print(adcRange);
    Serial.print("  V:");
    Serial.print(voltage, 0);
    Serial.print("mV  temp:");
    Serial.print(temperature, 1);
    Serial.print("^C  EC:");
    if (belowRange) {
      Serial.println("<0.6 ms/cm (below ESP32 ADC range)");
    } else {
      Serial.print(ecValue, 2);
      Serial.println(" ms/cm");
    }
  }

  ec.calibration(voltage, temperature);        // handles enterec / calec / exitec
}