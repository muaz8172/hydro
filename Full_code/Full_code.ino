/*
 * Hydroponic ESP32 firmware - DHT22 + EC + pH -> JSON over USB serial
 *
 * Wiring:
 *   DHT22 : DATA -> GPIO15, VCC -> 3.3V, GND -> GND
 *   EC    : A0 -> GPIO34, VCC -> 3.3V, GND -> GND (T1 unconnected)
 *   pH    : Po -> 10k/20k divider -> GPIO35, V+ -> 5V, G -> GND
 *
 * Output (every 2 s, one line):
 *   {"temp":28.1,"hum":70.2,"ec":1.45,"ec_low":false,"ph":6.20,"level":null,"ec_mv":237,"po_mv":2650}
 * Lines starting with '#' or '>>>' are messages, not data.
 *
 * Serial commands (115200, line ending = Newline):
 *   EC : enterec -> (1413 buffer) calec -> (12.88 buffer) calec -> exitec
 *   pH : ph7 (probe in pH 7 buffer) -> ph4 (probe in pH 4 buffer)
 *        phreset = back to defaults
 *   status = show calibration values
 *   debug  = toggle human-readable lines
 *
 * Requires the patched DFRobot_EC.cpp
 */

#include <DHT.h>
#include <EEPROM.h>
#include "DFRobot_EC.h"

// ---------- Pins ----------
#define DHT_PIN        15
#define DHT_TYPE       DHT22
#define EC_PIN         34
#define PH_PIN         35

// ---------- Settings ----------
#define SEND_INTERVAL  2000     // ms between JSON lines
#define EC_SAMPLES     30
#define PH_SAMPLES     30
#define PH_DIVIDER     1.5      // (10k + 20k) / 20k
#define EEPROM_SIZE    32
#define EC_KADDR       0x0A     // EC library uses bytes 10-17
#define PH_ADDR_V7     0x14     // pH uses bytes 20-27
#define PH_ADDR_V4     0x18

DHT dht(DHT_PIN, DHT_TYPE);
DFRobot_EC ec;

float waterTemp    = 25.0;      // fixed until a DS18B20 is added
float ecVoltage    = 0;
bool  ecBelowRange = false;
float phV7 = 2500.0;            // Po (mV) at pH 7  - default
float phV4 = 3040.0;            // Po (mV) at pH 4  - default (~180 mV/pH)
bool  debugMode = false;

char    cmdBuf[32];
uint8_t cmdLen = 0;

// ================= EC =================
float readEcVoltage()
{
  analogSetPinAttenuation(EC_PIN, ADC_0db);      // low range, more accurate
  analogRead(EC_PIN);
  int raw = analogRead(EC_PIN);

  if (raw >= 3800) {                             // too high -> wide range
    analogSetPinAttenuation(EC_PIN, ADC_11db);
    analogRead(EC_PIN);
    raw = analogRead(EC_PIN);
  }

  if (raw == 0) {                                // below ESP32 ADC floor
    ecBelowRange = true;
    return 0;
  }
  ecBelowRange = false;

  uint32_t sum = 0;
  for (int i = 0; i < EC_SAMPLES; i++) {
    sum += analogReadMilliVolts(EC_PIN);
    delay(2);
  }
  return sum / (float)EC_SAMPLES;
}

// ================= pH =================
float readPhPo()                                 // returns real Po in mV
{
  int buf[PH_SAMPLES];
  for (int i = 0; i < PH_SAMPLES; i++) {
    buf[i] = analogReadMilliVolts(PH_PIN);
    delay(5);
  }
  for (int i = 0; i < PH_SAMPLES - 1; i++)       // sort
    for (int j = i + 1; j < PH_SAMPLES; j++)
      if (buf[i] > buf[j]) { int t = buf[i]; buf[i] = buf[j]; buf[j] = t; }

  long sum = 0;
  for (int i = 5; i < PH_SAMPLES - 5; i++) sum += buf[i];   // drop spikes
  return sum / (float)(PH_SAMPLES - 10) * PH_DIVIDER;
}

float phFromPo(float po)
{
  float slope = 3.0 / (phV4 - phV7);             // pH per mV
  return 7.0 + (phV7 - po) * slope;
}

void loadPhCal()
{
  float v7, v4;
  EEPROM.get(PH_ADDR_V7, v7);
  EEPROM.get(PH_ADDR_V4, v4);
  if (!isnan(v7) && v7 > 1000 && v7 < 4000) phV7 = v7;
  if (!isnan(v4) && v4 > 1000 && v4 < 4500) phV4 = v4;
  if (phV4 - phV7 < 250) phV4 = phV7 + 540;      // keep slope sane
}

void savePhCal()
{
  EEPROM.put(PH_ADDR_V7, phV7);
  EEPROM.put(PH_ADDR_V4, phV4);
  EEPROM.commit();
}

// ================= Status / commands =================
void printStatus()
{
  float kLow, kHigh;
  EEPROM.get(EC_KADDR, kLow);
  EEPROM.get(EC_KADDR + 4, kHigh);
  Serial.printf("# EC  Klow=%.3f  Khigh=%.3f%s\n", kLow, kHigh,
                (kLow == 1.0 && kHigh == 1.0) ? "  (NOT calibrated)" : "");
  Serial.printf("# pH  V7=%.0fmV  V4=%.0fmV  slope=%.1fmV/pH\n",
                phV7, phV4, (phV4 - phV7) / 3.0);
}

void handleCommand(char* cmd)
{
  for (char* p = cmd; *p; p++) *p = toupper((unsigned char)*p);

  if (!strcmp(cmd, "ENTEREC") || !strcmp(cmd, "CALEC") || !strcmp(cmd, "EXITEC")) {
    ec.calibration(ecVoltage, waterTemp, cmd);

  } else if (!strcmp(cmd, "PH7")) {
    float po = readPhPo();
    if (po < 1500 || po > 3500) {
      Serial.printf("# pH7 rejected: Po=%.0fmV (expected ~2500)\n", po);
      return;
    }
    phV7 = po;
    if (phV4 - phV7 < 250 || phV4 - phV7 > 900) phV4 = phV7 + 540;
    savePhCal();
    Serial.printf("# pH7 saved: Po=%.0fmV. Now rinse, put in pH 4, wait 1-2 min, send ph4\n", po);

  } else if (!strcmp(cmd, "PH4")) {
    float po = readPhPo();
    float diff = po - phV7;
    if (diff < 250 || diff > 900) {
      Serial.printf("# pH4 rejected: Po=%.0fmV, diff from pH7=%.0fmV (expected ~540). Do ph7 first / check buffer\n", po, diff);
      return;
    }
    phV4 = po;
    savePhCal();
    Serial.printf("# pH4 saved: Po=%.0fmV  slope=%.1fmV/pH. pH calibration done\n", po, diff / 3.0);

  } else if (!strcmp(cmd, "PHRESET")) {
    phV7 = 2500.0; phV4 = 3040.0;
    savePhCal();
    Serial.println("# pH calibration reset to defaults");

  } else if (!strcmp(cmd, "STATUS")) {
    printStatus();

  } else if (!strcmp(cmd, "DEBUG")) {
    debugMode = !debugMode;
    Serial.printf("# debug %s\n", debugMode ? "ON" : "OFF");

  } else if (cmd[0] != '\0') {
    Serial.printf("# unknown command: %s\n", cmd);
  }
}

void readSerialCommands()
{
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      handleCommand(cmdBuf);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = c;
    }
  }
}

// ================= JSON helper =================
void printField(const char* key, float val, int dec, bool first = false)
{
  if (!first) Serial.print(',');
  Serial.print('"'); Serial.print(key); Serial.print("\":");
  if (isnan(val)) Serial.print("null");
  else            Serial.print(val, dec);
}

// ================= Main =================
void setup()
{
  Serial.begin(115200);
  delay(500);
  EEPROM.begin(EEPROM_SIZE);
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
  dht.begin();
  ec.begin();
  loadPhCal();

  Serial.println();
  Serial.println("# Hydro ESP32 ready");
  printStatus();
  Serial.println("# Commands: enterec calec exitec | ph7 ph4 phreset | status | debug");
}

void loop()
{
  readSerialCommands();

  static unsigned long last = 0;
  if (millis() - last >= SEND_INTERVAL) {
    last = millis();

    float hum  = dht.readHumidity();
    float temp = dht.readTemperature();

    ecVoltage     = readEcVoltage();
    float ecValue = ec.readEC(ecVoltage, waterTemp);

    float po = readPhPo();
    float ph = phFromPo(po);

    // ---- JSON line for the Pi ----
    Serial.print('{');
    printField("temp", temp, 1, true);
    printField("hum",  hum,  1);
    printField("ec",   ecValue, 2);
    Serial.print(",\"ec_low\":"); Serial.print(ecBelowRange ? "true" : "false");
    printField("ph",   ph,   2);
    Serial.print(",\"level\":null");              // HC-SR04 not added yet
    printField("ec_mv", ecVoltage, 0);
    printField("po_mv", po, 0);
    Serial.println('}');

    if (debugMode) {
      Serial.printf("# T=%.1fC H=%.1f%%  EC=%.2f (%.0fmV%s)  pH=%.2f (Po %.0fmV)\n",
                    temp, hum, ecValue, ecVoltage, ecBelowRange ? " LOW" : "", ph, po);
    }
  }
}