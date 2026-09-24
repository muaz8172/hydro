/*
 * ESP32 Indoor Vertical Garden - Sensor Integration
 * Sensors: pH (Analog, Gravity-style), EC (Analog, Gravity-style), DHT22 (air temp/humidity)
 * Reserved for later: HC-SR04 ultrasonic (water level)
 *
 * Required libraries (install via Arduino Library Manager):
 *   - DHT sensor library (Adafruit) + Adafruit Unified Sensor
 *   - DFRobot_EC        (https://github.com/DFRobot/DFRobot_EC)
 *   - DFRobot_PH        (https://github.com/DFRobot/DFRobot_PH)
 *
 * Serial calibration commands (open Serial Monitor @ 115200 baud):
 *   EC:  enterec -> calec (in 1413us/cm) -> calec (in 12.88ms/cm) -> exitec
 *   PH:  enterph -> calph (in pH 4.0 buffer) -> calph (in pH 7.0 buffer) -> exitph
 */

#include "DFRobot_EC.h"
#include "DFRobot_PH.h"
#include <EEPROM.h>
#include <DHT.h>

// ---------------- Pin definitions (matches project schematic) ----------------
#define EC_PIN   35   // EC/TDS sensor AO  -> ESP32 GPIO35 (ADC1, WiFi-safe)
#define PH_PIN   34   // pH sensor AO      -> ESP32 GPIO34 (ADC1, WiFi-safe)
#define DHT_PIN  4    // DHT22 DATA        -> ESP32 GPIO4
#define DHT_TYPE DHT22

// Reserved for later - HC-SR04 ultrasonic water level sensor
// #define TRIG_PIN 32   // ESP32 GPIO32
// #define ECHO_PIN 33   // ESP32 GPIO33 (needs a voltage divider - HC-SR04 echo is 5V, ESP32 GPIO max is 3.3V)

// ---------------- ADC settings ----------------
#define VREF    3300.0   // ESP32 ADC reference in mV
#define ADC_RES 4095.0   // ESP32 12-bit ADC

DHT dht(DHT_PIN, DHT_TYPE);
DFRobot_EC ec;
DFRobot_PH ph;

float voltageEC, voltagePH, ecValue, phValue;
float temperature = 25.0;  // fixed for now - update this if/when you add a DS18B20 or similar

void setup()
{
  Serial.begin(115200);
  EEPROM.begin(32);         // REQUIRED on ESP32 before any EEPROM read/write (used internally by both libraries)
  analogReadResolution(12); // ensure 12-bit ADC (0-4095)

  dht.begin();
  ec.begin();
  ph.begin();
}

void loop()
{
  static unsigned long timepoint = millis();
  if (millis() - timepoint > 1000U)  // every 1 second
  {
    timepoint = millis();

    // --- DHT22: room air temperature & humidity ---
    float airTemp = dht.readTemperature();
    float airHum  = dht.readHumidity();

    // --- EC ---
    voltageEC = analogRead(EC_PIN) / ADC_RES * VREF;
    ecValue = ec.readEC(voltageEC, temperature);

    // --- pH ---
    voltagePH = analogRead(PH_PIN) / ADC_RES * VREF;
    phValue = ph.readPH(voltagePH, temperature);

    // --- Print everything on one line ---
    Serial.print("Air Temp: ");
    if (isnan(airTemp)) Serial.print("ERR"); else Serial.print(airTemp, 1);
    Serial.print(" C  |  Humidity: ");
    if (isnan(airHum)) Serial.print("ERR"); else Serial.print(airHum, 1);
    Serial.print(" %  |  EC: ");
    Serial.print(ecValue, 2);
    Serial.print(" mS/cm  |  pH: ");
    Serial.println(phValue, 2);
  }

  // --- Calibration: type commands into Serial Monitor at any time ---
  char cmd[16];
  if (readSerialCommand(cmd))
  {
    if (strstr(cmd, "ec")) ec.calibration(voltageEC, temperature, cmd);
    if (strstr(cmd, "ph")) ph.calibration(voltagePH, temperature, cmd);
  }
}

// Reads one line typed into Serial Monitor (ended by Enter) into cmd[]
bool readSerialCommand(char* cmd)
{
  static char buffer[16];
  static byte idx = 0;
  if (Serial.available() > 0)
  {
    char c = Serial.read();
    if (c == '\n' || c == '\r')
    {
      if (idx > 0)
      {
        buffer[idx] = '\0';
        strcpy(cmd, buffer);
        idx = 0;
        return true;
      }
    }
    else if (idx < 15)
    {
      buffer[idx++] = c;
    }
  }
  return false;
}
