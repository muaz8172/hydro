/*
 * pH sensor (PH-4502C) test on ESP32
 * V+ -> 5V, G -> GND, Po -> 10k/20k divider -> GPIO33
 * Uncalibrated estimate: pH = 7 + (2.5V - Po) / 0.18
 */

#define PH_PIN        33
#define SAMPLES       30
#define DIVIDER_RATIO 1.5     // (10k + 20k) / 20k  -> undo the 2/3 divider

float readPin_mV()
{
  int buf[SAMPLES];
  for (int i = 0; i < SAMPLES; i++) {
    buf[i] = analogReadMilliVolts(PH_PIN);
    delay(5);
  }
  // sort, then average the middle values (removes spikes)
  for (int i = 0; i < SAMPLES - 1; i++)
    for (int j = i + 1; j < SAMPLES; j++)
      if (buf[i] > buf[j]) { int t = buf[i]; buf[i] = buf[j]; buf[j] = t; }

  long sum = 0;
  for (int i = 5; i < SAMPLES - 5; i++) sum += buf[i];
  return sum / (float)(SAMPLES - 10);
}

void setup()
{
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetPinAttenuation(PH_PIN, ADC_11db);   // 0 - ~3.1 V range
  delay(500);
  Serial.println("=== pH sensor test ===");
}

void loop()
{
  float pin_mV = readPin_mV();
  float po_mV  = pin_mV * DIVIDER_RATIO;             // real Po voltage
  float ph     = 7.0 + (2500.0 - po_mV) / 180.0;     // uncalibrated estimate

  Serial.print("pin:");
  Serial.print(pin_mV, 0);
  Serial.print("mV  Po:");
  Serial.print(po_mV, 0);
  Serial.print("mV  pH(uncal):");
  Serial.println(ph, 2);

  delay(1000);
}