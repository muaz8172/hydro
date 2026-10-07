#include <DHT.h>

#define DHTPIN 12       // DHT22 data pin connected to GPIO 12 (D12)
                       // GPIO12 is a boot strapping pin: if the ESP32 won't boot with DATA
                       // connected, run espefuse.py set_flash_voltage 3.3V once
#define DHTTYPE DHT22   // DHT 22 (AM2302)

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  Serial.println("DHT22 Test");
  dht.begin();
}

void loop() {
  // Wait a few seconds between measurements
  delay(2000);

  float humidity = dht.readHumidity();
  float tempC = dht.readTemperature();       // Celsius
  float tempF = dht.readTemperature(true);   // Fahrenheit

  // Check if any reads failed
  if (isnan(humidity) || isnan(tempC) || isnan(tempF)) {
    Serial.println("Failed to read from DHT sensor!");
    return;
  }

  float heatIndexC = dht.computeHeatIndex(tempC, humidity, false);

  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.print("%  Temperature: ");
  Serial.print(tempC);
  Serial.print("°C  Heat index: ");
  Serial.print(heatIndexC);
  Serial.println("°C");
}