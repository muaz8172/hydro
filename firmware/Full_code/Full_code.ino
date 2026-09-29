/*
 * Hydroponic ESP32 firmware - DHT22 + EC + pH + HC-SR04 -> JSON over USB serial
 *
 * Wiring:
 *   DHT22   : DATA -> GPIO15, VCC -> 3.3V, GND -> GND
 *   EC      : A0 -> GPIO34, VCC -> 3.3V, GND -> GND (T1 unconnected)
 *   pH      : Po -> 10k/20k divider -> GPIO35, V+ -> 5V, G -> GND
 *   HC-SR04 : TRIG -> GPIO32, ECHO -> 1k/2k divider -> GPIO33, VCC -> 5V, GND -> GND
 *   Relay 1 (2ch) : IN1 (Pump A) -> GPIO25, IN2 (Pump B) -> GPIO26, VCC -> 5V, GND -> GND
 *   Relay 2 (2ch) : IN1 (sampling pump) -> GPIO27, IN2 spare (not connected), VCC -> 5V, GND -> GND
 *
 * Output (every 2 s, one line):
 *   {"temp":28.1,"hum":70.2,"ec":1.45,"ec_low":false,"ph":6.20,"level":9.8,
 *    "level_pct":72,"level_low":false,"ec_mv":237,"po_mv":2650,"dist_cm":10.2,
 *    "pump_a":true,"pump_b":true,"pump_auto":true,"pump_sample":true,"temp_ok":true}
 *   temp_ok: air temperature inside TEMP_MIN-TEMP_MAX (25-36 C), null if the DHT22 gives no reading.
 *   Only reported: nothing on the ESP32 heats or cools.
 * Lines starting with '#' or '>>>' are messages, not data.
 *
 * Pumps (auto): Pump A + Pump B run until EC AND pH both reach the target
 *   (EC 1.2-1.8 mS/cm and pH 5.5-6.5), then stop. They start again when
 *   either one goes lower or higher than the target. Auto mode at boot. Bad pH reading -> OFF.
 *   Sampling pump: runs all the time. sampleoff / sampleon to stop/start.
 *   Start delay: after every ESP32 boot (Pi reboot, bridge restart or USB replug) the sampling
 *   pump waits SAMPLE_START_DELAY and Pump A/B wait PUMP_START_DELAY before auto turns them on.
 *   Manual commands (pumpaon, pumpbon, sampleon) are not delayed.
 *   Tank low (level_low, once tank is calibrated) -> ALL pumps OFF, even in manual.
 *
 * Serial commands (115200, line ending = Newline):
 *   EC   : enterec -> (1413 buffer) calec -> (12.88 buffer) calec -> exitec
 *   pH   : ph7 (pH 7 buffer) -> ph4 (pH 4 buffer), phreset
 *   Tank : tankempty (tank EMPTY) -> tankfull (tank at MAX level), tankreset
 *   Pump : pumpaon pumpaoff pumpbon pumpboff (manual), pumpauto (back to auto)
 *          sampleon sampleoff (sampling pump)
 *   status = show calibration values
 *   debug  = toggle human-readable lines
 *
 * EC conversion and calibration are done here (same maths as DFRobot_EC); that library's
 * calibration() corrupted the ESP32 flash lock, see the EC section.
 */

#include <DHT.h>
#include <EEPROM.h>

// ---------- Pins ----------
#define DHT_PIN        15
#define DHT_TYPE       DHT22
#define EC_PIN         34
#define PH_PIN         35
#define TRIG_PIN       32
#define ECHO_PIN       33
#define PUMP_A_PIN     25       // relay 1 IN1
#define PUMP_B_PIN     26       // relay 1 IN2
#define SAMPLE_PIN     27       // relay 2 IN1 (sampling pump)

// ---------- Pump control ----------
#define RELAY_ACTIVE_LOW  true  // both 2-ch relays: LOW = ON. Set false if reversed
// Target ranges: pumps run while EC or pH is below/above, stop when both inside
#define EC_MIN         1.2      // mS/cm
#define EC_MAX         1.8      // mS/cm
#define PH_MIN         5.5
#define PH_MAX         6.5
// Air temperature target (DHT22), reported as temp_ok; no pump or relay acts on it
#define TEMP_MIN       25.0     // C
#define TEMP_MAX       36.0     // C
// Start delay after ESP32 boot (Pi reboot / USB replug both restart the ESP32)
#define SAMPLE_START_DELAY  30000UL   // ms before the sampling pump starts
#define PUMP_START_DELAY    60000UL   // ms before Pump A/B auto control starts

// ---------- Settings ----------
#define SEND_INTERVAL  2000     // ms between JSON lines
#define EC_SAMPLES     30
#define PH_SAMPLES     30
#define PH_DIVIDER     1.5      // (10k + 20k) / 20k
#define US_SAMPLES     5        // ultrasonic pings per reading (median)
#define US_TIMEOUT     30000UL  // us, ~5 m max
#define LOW_LEVEL_PCT  20.0     // level_low alarm below this %

// ---------- EEPROM layout ----------
#define EEPROM_SIZE      48
#define EC_KADDR         0x0A   // EC K values: bytes 10-17 (same place DFRobot_EC used)
#define PH_ADDR_V7       0x14   // pH: bytes 20-27
#define PH_ADDR_V4       0x18
#define TANK_ADDR_EMPTY  0x1C   // tank: bytes 28-35
#define TANK_ADDR_FULL   0x20

DHT dht(DHT_PIN, DHT_TYPE);

float waterTemp    = 25.0;      // fixed until a DS18B20 is added
float lastAirTemp  = 25.0;      // from DHT22, used for sound speed
float ecVoltage    = 0;
bool  ecBelowRange = false;
float phV7 = 2500.0;            // Po (mV) at pH 7 - default
float phV4 = 3040.0;            // Po (mV) at pH 4 - default (~180 mV/pH)
float tankEmptyDist = 20.0;     // cm, sensor -> bottom (empty tank) - default
float tankFullDist  = 5.0;      // cm, sensor -> water at MAX level  - default
bool  tankCalibrated = false;
bool  debugMode = false;
bool  pumpAuto  = true;         // false = manual (serial commands)
bool  pumpAOn   = false;
bool  pumpBOn   = false;
bool  sampleOn  = false;        // sampling pump relay state
bool  sampleEnabled = true;     // sampling pump runs all the time unless sampleoff
bool  tankStop  = false;        // true = tank low, pumps locked OFF
uint8_t ecBootBytes[8];         // EC K bytes as read from flash at boot (FF = never saved), shown by status

char    cmdBuf[32];
uint8_t cmdLen = 0;

// ================= EC =================
// EC is read on 11 dB, the same range as pH. analogReadMilliVolts() converts with a calibration
// made once for the global attenuation (11 dB by default), so reading this pin on 0 dB gave
// millivolts about 3x too high (1413 uS/cm buffer showed ~680 mV instead of ~230 mV).
float readEcVoltage()
{
  analogRead(EC_PIN);
  int raw = analogRead(EC_PIN);

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

// ---------- EC conversion and calibration ----------
// Same maths and command replies as DFRobot_EC (K=1 probe, RES2 820, ECREF 200, so raw EC in
// mS/cm = mV / 164), written out here because that library's calibration() corrupted the ESP32
// flash mutex: even "calec" outside calibration mode made the next flash access assert in
// spi_flash_op_lock, so no EC save ever reached flash.
#define EC_MV_PER_MS 164.0      // 820 * 200 / 1000
float ecKLow = 1.0, ecKHigh = 1.0, ecK = 1.0;   // K for the 1413 and 12.88 ranges, K in use
bool  ecCalMode = false;
float ecNewLow = NAN, ecNewHigh = NAN;          // captured this session, saved by exitec

void loadEcCal()
{
  EEPROM.get(EC_KADDR, ecKLow);
  EEPROM.get(EC_KADDR + 4, ecKHigh);
  if (!(ecKLow  > 0.5 && ecKLow  < 1.5)) ecKLow  = 1.0;   // also catches FF (never saved)
  if (!(ecKHigh > 0.5 && ecKHigh < 1.5)) ecKHigh = 1.0;
  ecK = ecKLow;
}

float ecFromMv(float mv, float temp)
{
  float raw = mv / EC_MV_PER_MS;
  float v = raw * ecK;                           // switch range with a little hysteresis
  if (v > 2.5)      ecK = ecKHigh;
  else if (v < 2.0) ecK = ecKLow;
  return raw * ecK / (1.0 + 0.0185 * (temp - 25.0));
}

bool ecIsLowBuffer(float raw)  { return raw > 0.9 && raw < 1.9; }    // 1413 uS/cm
bool ecIsHighBuffer(float raw) { return raw > 9.0 && raw < 16.8; }   // 12.88 mS/cm

void ecCommand(const char* cmd, float mv, float temp)
{
  if (!strcmp(cmd, "ENTEREC")) {
    ecCalMode = true;
    ecNewLow = ecNewHigh = NAN;
    Serial.println(">>>Enter EC Calibration Mode<<<");
    Serial.println(">>>Please put the probe into the 1413us/cm or 12.88ms/cm buffer solution<<<");
    return;
  }
  if (!ecCalMode) {                              // calec / exitec without enterec
    Serial.println(">>>Command Error<<<");
    return;
  }
  if (!strcmp(cmd, "CALEC")) {
    float raw = mv / EC_MV_PER_MS, buffer;
    if (ecIsLowBuffer(raw))       buffer = 1.413;
    else if (ecIsHighBuffer(raw)) buffer = 12.88;
    else { Serial.println(">>>Buffer Solution Error Try Again<<<"); return; }
    float k = buffer * (1.0 + 0.0185 * (temp - 25.0)) * EC_MV_PER_MS / mv;
    if (!(k > 0.5 && k < 1.5)) { Serial.println(">>>Failed,Try Again<<<"); return; }
    if (buffer < 2) ecNewLow = k; else ecNewHigh = k;
    Serial.printf(">>>Successful,K:%.2f, Send EXITEC to Save and Exit<<<\n", k);
    return;
  }
  // EXITEC: save every K captured this session (the other one keeps its stored value)
  ecCalMode = false;
  if (isnan(ecNewLow) && isnan(ecNewHigh)) {
    Serial.println(">>>Calibration Failed,Exit EC Calibration Mode<<<");
    return;
  }
  if (!isnan(ecNewLow))  ecKLow  = ecNewLow;
  if (!isnan(ecNewHigh)) ecKHigh = ecNewHigh;
  ecK = ecKLow;
  EEPROM.put(EC_KADDR, ecKLow);
  EEPROM.put(EC_KADDR + 4, ecKHigh);
  bool saved = EEPROM.commit();
  Serial.println(saved ? "# EC K values written to flash" : "# EC K values NOT written to flash (EEPROM.commit failed)");
  Serial.println(">>>Calibration Successful,Exit EC Calibration Mode<<<");
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

// ================= Ultrasonic (water level) =================
float readDistanceCm(float airTemp)
{
  if (isnan(airTemp)) airTemp = 25.0;
  float speed = 331.3 + 0.606 * airTemp;         // speed of sound, m/s

  float d[US_SAMPLES];
  int n = 0;
  for (int i = 0; i < US_SAMPLES; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    unsigned long us = pulseIn(ECHO_PIN, HIGH, US_TIMEOUT);
    if (us > 0) {
      float cm = us * speed / 20000.0;           // (us * m/s) / 2 -> cm
      if (cm >= 2.0 && cm <= 400.0) d[n++] = cm;
    }
    delay(60);                                   // let echoes die out
  }
  if (n == 0) return NAN;

  for (int i = 0; i < n - 1; i++)                // sort -> median
    for (int j = i + 1; j < n; j++)
      if (d[i] > d[j]) { float t = d[i]; d[i] = d[j]; d[j] = t; }
  return d[n / 2];
}

void computeLevel(float dist, float &levelCm, float &levelPct)
{
  if (isnan(dist)) { levelCm = NAN; levelPct = NAN; return; }

  levelCm = tankEmptyDist - dist;                // water height above bottom
  if (levelCm < 0) levelCm = 0;

  float range = tankEmptyDist - tankFullDist;
  levelPct = (tankEmptyDist - dist) / range * 100.0;
  if (levelPct < 0)   levelPct = 0;
  if (levelPct > 100) levelPct = 100;
}

void loadTankCal()
{
  float e, f;
  EEPROM.get(TANK_ADDR_EMPTY, e);
  EEPROM.get(TANK_ADDR_FULL, f);
  if (!isnan(e) && !isnan(f) && e > 2 && e < 400 && f > 2 && f < 400 && (e - f) >= 3) {
    tankEmptyDist  = e;
    tankFullDist   = f;
    tankCalibrated = true;
  }
}

void saveTankCal()
{
  EEPROM.put(TANK_ADDR_EMPTY, tankEmptyDist);
  EEPROM.put(TANK_ADDR_FULL, tankFullDist);
  EEPROM.commit();
}

// ================= Pumps (relay) =================
void setPump(uint8_t pin, bool &state, bool on)
{
  digitalWrite(pin, (on == RELAY_ACTIVE_LOW) ? LOW : HIGH);
  if (state != on) {
    state = on;
    const char* name = pin == PUMP_A_PIN ? "Pump A" : pin == PUMP_B_PIN ? "Pump B" : "Sampling pump";
    Serial.printf("# %s %s\n", name, on ? "ON" : "OFF");
  }
}

void updatePumps(float ecValue, float ph, bool levelLow)
{
  // dry-run protection: overrides auto AND manual (only once tank is calibrated)
  bool stop = tankCalibrated && levelLow;
  if (stop != tankStop) {
    tankStop = stop;
    Serial.println(stop ? "# Tank LOW - pumps stopped" : "# Tank OK - pumps allowed");
  }
  if (stop) {
    setPump(PUMP_A_PIN, pumpAOn, false);
    setPump(PUMP_B_PIN, pumpBOn, false);
    setPump(SAMPLE_PIN, sampleOn, false);
    return;
  }

  // start delay: leave relays alone until the delay has passed
  static bool sampleWaited = false, pumpWaited = false;
  if (!sampleWaited && millis() >= SAMPLE_START_DELAY) {
    sampleWaited = true;
    Serial.println("# Sampling pump start delay over");
  }
  if (!pumpWaited && millis() >= PUMP_START_DELAY) {
    pumpWaited = true;
    Serial.println("# Pump A/B start delay over");
  }

  if (sampleWaited) setPump(SAMPLE_PIN, sampleOn, sampleEnabled);  // always on unless sampleoff

  if (!pumpAuto || !pumpWaited) return;
  // ec_low means EC is below the ADC floor -> definitely under target, keep running
  bool ecOk = !ecBelowRange && !isnan(ecValue) && ecValue >= EC_MIN && ecValue <= EC_MAX;
  bool phOk = ph >= PH_MIN && ph <= PH_MAX;
  bool run  = !isnan(ph) && !(ecOk && phOk);    // stop once both reach target
  setPump(PUMP_A_PIN, pumpAOn, run);
  setPump(PUMP_B_PIN, pumpBOn, run);
}

// ================= Status / commands =================
void printStatus()
{
  float kLow, kHigh;
  EEPROM.get(EC_KADDR, kLow);
  EEPROM.get(EC_KADDR + 4, kHigh);
  Serial.printf("# EC   Klow=%.3f  Khigh=%.3f%s\n", kLow, kHigh,
                (kLow == 1.0 && kHigh == 1.0) ? "  (NOT calibrated)" : "");
  float bootLow, bootHigh;
  memcpy(&bootLow, ecBootBytes, 4);
  memcpy(&bootHigh, ecBootBytes + 4, 4);
  bool never = ecBootBytes[0] == 0xFF && ecBootBytes[1] == 0xFF && ecBootBytes[2] == 0xFF && ecBootBytes[3] == 0xFF;
  if (never) Serial.println("# EC   flash at boot: empty (never saved)");
  else       Serial.printf("# EC   flash at boot: Klow=%.3f  Khigh=%.3f\n", bootLow, bootHigh);
  Serial.printf("# pH   V7=%.0fmV  V4=%.0fmV  slope=%.1fmV/pH\n",
                phV7, phV4, (phV4 - phV7) / 3.0);
  Serial.printf("# Tank empty=%.1fcm  full=%.1fcm%s\n",
                tankEmptyDist, tankFullDist, tankCalibrated ? "" : "  (NOT calibrated)");
  Serial.printf("# Pump %s  A=%s B=%s  stop at target EC %.2f-%.2f and pH %.2f-%.2f\n",
                pumpAuto ? "AUTO" : "MANUAL", pumpAOn ? "ON" : "OFF", pumpBOn ? "ON" : "OFF",
                EC_MIN, EC_MAX, PH_MIN, PH_MAX);
  Serial.printf("# Air temp target %.1f-%.1f C\n", TEMP_MIN, TEMP_MAX);
  Serial.printf("# Sampling pump %s%s\n", sampleOn ? "ON" : "OFF",
                sampleEnabled ? "" : "  (disabled by sampleoff)");
}

void handleCommand(char* cmd)
{
  for (char* p = cmd; *p; p++) *p = toupper((unsigned char)*p);

  if (!strcmp(cmd, "ENTEREC") || !strcmp(cmd, "CALEC") || !strcmp(cmd, "EXITEC")) {
    ecCommand(cmd, ecVoltage, waterTemp);

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

  } else if (!strcmp(cmd, "TANKEMPTY")) {
    float d = readDistanceCm(lastAirTemp);
    if (isnan(d)) { Serial.println("# tankempty rejected: no echo, check wiring/aim"); return; }
    tankEmptyDist = d;
    if (tankEmptyDist - tankFullDist < 3) tankFullDist = tankEmptyDist - 3;
    saveTankCal();
    Serial.printf("# tankempty saved: %.1fcm. Now fill to MAX level and send tankfull\n", d);

  } else if (!strcmp(cmd, "TANKFULL")) {
    float d = readDistanceCm(lastAirTemp);
    if (isnan(d)) { Serial.println("# tankfull rejected: no echo, check wiring/aim"); return; }
    if (tankEmptyDist - d < 3) {
      Serial.printf("# tankfull rejected: %.1fcm is too close to empty (%.1fcm). Do tankempty first\n", d, tankEmptyDist);
      return;
    }
    tankFullDist = d;
    tankCalibrated = true;
    saveTankCal();
    Serial.printf("# tankfull saved: %.1fcm. Usable depth=%.1fcm. Tank calibration done\n",
                  d, tankEmptyDist - tankFullDist);

  } else if (!strcmp(cmd, "TANKRESET")) {
    tankEmptyDist = 20.0; tankFullDist = 5.0; tankCalibrated = false;
    saveTankCal();
    Serial.println("# tank calibration reset to defaults");

  } else if (!strcmp(cmd, "PUMPAON") || !strcmp(cmd, "PUMPAOFF") ||
             !strcmp(cmd, "PUMPBON") || !strcmp(cmd, "PUMPBOFF")) {
    pumpAuto = false;
    bool on = !strcmp(cmd + 5, "ON");
    if (on && tankStop) {
      Serial.println("# Pump blocked: tank LOW. Refill first");
      on = false;
    }
    if (cmd[4] == 'A') setPump(PUMP_A_PIN, pumpAOn, on);
    else               setPump(PUMP_B_PIN, pumpBOn, on);
    Serial.println("# Pump MANUAL mode (send pumpauto to return to auto)");

  } else if (!strcmp(cmd, "SAMPLEON")) {
    sampleEnabled = true;
    if (tankStop) Serial.println("# Sampling pump blocked: tank LOW. Refill first");
    else          setPump(SAMPLE_PIN, sampleOn, true);

  } else if (!strcmp(cmd, "SAMPLEOFF")) {
    sampleEnabled = false;
    setPump(SAMPLE_PIN, sampleOn, false);

  } else if (!strcmp(cmd, "PUMPAUTO")) {
    pumpAuto = true;
    Serial.println("# Pump AUTO mode");

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
  // relays OFF before making them outputs, so pumps don't kick on at boot
  digitalWrite(PUMP_A_PIN, RELAY_ACTIVE_LOW ? HIGH : LOW);
  digitalWrite(PUMP_B_PIN, RELAY_ACTIVE_LOW ? HIGH : LOW);
  pinMode(PUMP_A_PIN, OUTPUT);
  pinMode(PUMP_B_PIN, OUTPUT);
  digitalWrite(SAMPLE_PIN, RELAY_ACTIVE_LOW ? HIGH : LOW);    // OFF until first reading
  pinMode(SAMPLE_PIN, OUTPUT);

  Serial.begin(115200);
  delay(500);
  EEPROM.begin(EEPROM_SIZE);
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);
  analogSetPinAttenuation(EC_PIN, ADC_11db);     // keep EC and pH on one range (see readEcVoltage)
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  dht.begin();
  for (int i = 0; i < 8; i++) ecBootBytes[i] = EEPROM.read(EC_KADDR + i);   // raw, for status
  loadEcCal();
  loadPhCal();
  loadTankCal();

  Serial.println();
  Serial.println("# Hydro ESP32 ready");
  printStatus();
  Serial.printf("# Start delay: sampling pump in %lu s, Pump A/B in %lu s\n",
                SAMPLE_START_DELAY / 1000, PUMP_START_DELAY / 1000);
  Serial.println("# Commands: enterec calec exitec | ph7 ph4 phreset | tankempty tankfull tankreset | pumpaon pumpaoff pumpbon pumpboff pumpauto | sampleon sampleoff | status | debug");
}

void loop()
{
  readSerialCommands();

  static unsigned long last = 0;
  if (millis() - last >= SEND_INTERVAL) {
    last = millis();

    float hum  = dht.readHumidity();
    float temp = dht.readTemperature();
    if (!isnan(temp)) lastAirTemp = temp;

    ecVoltage     = readEcVoltage();
    float ecValue = ecFromMv(ecVoltage, waterTemp);

    float po = readPhPo();
    float ph = phFromPo(po);

    float dist = readDistanceCm(lastAirTemp);
    float levelCm, levelPct;
    computeLevel(dist, levelCm, levelPct);
    bool levelLow = !isnan(levelPct) && levelPct < LOW_LEVEL_PCT;

    updatePumps(ecValue, ph, levelLow);

    // ---- JSON line for the Pi ----
    Serial.print('{');
    printField("temp", temp, 1, true);
    printField("hum",  hum,  1);
    printField("ec",   ecValue, 2);
    Serial.print(",\"ec_low\":"); Serial.print(ecBelowRange ? "true" : "false");
    printField("ph",   ph,   2);
    printField("level",     levelCm,  1);
    printField("level_pct", levelPct, 0);
    Serial.print(",\"level_low\":"); Serial.print(levelLow ? "true" : "false");
    printField("ec_mv",   ecVoltage, 0);
    printField("po_mv",   po,        0);
    printField("dist_cm", dist,      1);
    Serial.print(",\"pump_a\":");    Serial.print(pumpAOn  ? "true" : "false");
    Serial.print(",\"pump_b\":");    Serial.print(pumpBOn  ? "true" : "false");
    Serial.print(",\"pump_auto\":"); Serial.print(pumpAuto ? "true" : "false");
    Serial.print(",\"pump_sample\":"); Serial.print(sampleOn ? "true" : "false");
    Serial.print(",\"temp_ok\":");
    if (isnan(temp)) Serial.print("null");
    else Serial.print(temp >= TEMP_MIN && temp <= TEMP_MAX ? "true" : "false");
    Serial.println('}');

    if (debugMode) {
      Serial.printf("# T=%.1fC H=%.1f%%  EC=%.2f (%.0fmV%s)  pH=%.2f (Po %.0fmV)  Level=%.1fcm %.0f%% (dist %.1fcm)\n",
                    temp, hum, ecValue, ecVoltage, ecBelowRange ? " LOW" : "", ph, po,
                    levelCm, levelPct, dist);
    }
  }
}