/*
 * 2-channel relay test on ESP32
 * IN1 -> GPIO18 (D18, Pump In), IN2 -> GPIO19 (D19, Pump Out)
 * VCC -> 5V, GND -> GND (shared with ESP32)
 *
 * Serial Monitor: 115200 baud, line ending = Newline
 * Commands: 1on  1off  2on  2off  alloff  auto
 */

#define RELAY1_PIN  18      // D18 Pump In
#define RELAY2_PIN  19      // D19 Pump Out

#define ACTIVE_LOW  true    // most relay modules: LOW = ON. Set false if yours is reversed

const int ON  = ACTIVE_LOW ? LOW  : HIGH;
const int OFF = ACTIVE_LOW ? HIGH : LOW;

bool autoMode = true;
String cmd = "";

void setRelay(int pin, bool on, const char* name)
{
  digitalWrite(pin, on ? ON : OFF);
  Serial.printf("%s -> %s\n", name, on ? "ON" : "OFF");
}

void setup()
{
  // set OFF before making them outputs, so relays don't click at boot
  digitalWrite(RELAY1_PIN, OFF);
  digitalWrite(RELAY2_PIN, OFF);
  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);

  Serial.begin(115200);
  delay(500);
  Serial.println("=== Relay test ===");
  Serial.println("Auto mode: each relay ON 2 s, OFF 2 s");
  Serial.println("Type any command to switch to manual: 1on 1off 2on 2off alloff auto");
}

void handleCommand(String c)
{
  c.trim();
  c.toLowerCase();
  if (c.length() == 0) return;

  if (c != "auto") autoMode = false;

  if      (c == "1on")    setRelay(RELAY1_PIN, true,  "Relay 1");
  else if (c == "1off")   setRelay(RELAY1_PIN, false, "Relay 1");
  else if (c == "2on")    setRelay(RELAY2_PIN, true,  "Relay 2");
  else if (c == "2off")   setRelay(RELAY2_PIN, false, "Relay 2");
  else if (c == "alloff") {
    setRelay(RELAY1_PIN, false, "Relay 1");
    setRelay(RELAY2_PIN, false, "Relay 2");
  }
  else if (c == "auto") {
    autoMode = true;
    Serial.println("Auto mode ON");
  }
  else Serial.println("Unknown command");
}

void loop()
{
  // read serial commands
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n') { handleCommand(cmd); cmd = ""; }
    else if (ch != '\r') cmd += ch;
  }

  // automatic test sequence
  if (autoMode) {
    static unsigned long last = 0;
    static int step = 0;
    if (millis() - last >= 2000) {
      last = millis();
      switch (step) {
        case 0: setRelay(RELAY1_PIN, true,  "Relay 1"); break;
        case 1: setRelay(RELAY1_PIN, false, "Relay 1"); break;
        case 2: setRelay(RELAY2_PIN, true,  "Relay 2"); break;
        case 3: setRelay(RELAY2_PIN, false, "Relay 2"); break;
      }
      step = (step + 1) % 4;
    }
  }
}