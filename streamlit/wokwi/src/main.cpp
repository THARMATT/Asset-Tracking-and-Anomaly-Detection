#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// Wokwi's simulated Wi-Fi network
static const char* WIFI_SSID = "Wokwi-GUEST";
static const char* WIFI_PASSWORD = "";

// Public broker for a classroom demo. Use a private broker + TLS for production.
static const char* MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;

// MUST match MQTT_TOPIC_PREFIX in mqtt_bridge.py. Change to your own unique ID
// if you share this project publicly.
static const char* TOPIC_PREFIX = "iot-asset-tracker-demo/nsut-asset-7f31a9";
static const char* ASSET_ID = "ASSET_001";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

static const int BATTERY_POT_PIN = 34;   // Potentiometer 1: battery percentage
static const int GEOFENCE_POT_PIN = 35;  // Potentiometer 2: boundary test
static const int STATUS_LED_PIN = 2;

static const unsigned long PUBLISH_INTERVAL_MS = 2000;
unsigned long lastPublishMs = 0;
float latitude = 28.613909f;
float longitude = 77.209015f;
float speedKmh = 24.0f;
bool ledOn = false;

String telemetryTopic() {
  return String(TOPIC_PREFIX) + "/" + ASSET_ID + "/telemetry";
}
String statusTopic() {
  return String(TOPIC_PREFIX) + "/" + ASSET_ID + "/status";
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wokwi-GUEST");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi connected.");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!mqtt.connected()) {
    String clientId = String("wokwi-") + ASSET_ID + "-" + String((uint32_t)random(100000, 999999));
    Serial.print("Connecting to MQTT broker...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" connected.");
      mqtt.publish(statusTopic().c_str(), "online", true);
    } else {
      Serial.print(" failed, state=");
      Serial.print(mqtt.state());
      Serial.println("; retry in 2 seconds.");
      delay(2000);
    }
  }
}

int readBatteryPercent() {
  int raw = analogRead(BATTERY_POT_PIN);
  return constrain(map(raw, 0, 4095, 0, 100), 0, 100);
}

void updatePositionAndSpeed() {
  // Simulated GPS movement around the asset's configured Delhi home point.
  // Potentiometer 2 above 80% moves the asset outside the 150 m geofence.
  int boundaryControl = analogRead(GEOFENCE_POT_PIN);
  if (boundaryControl > 3276) {
    latitude = 28.616909f;   // ~333 m north of the configured home point
    longitude = 77.209015f;
  } else {
    float phase = (millis() % 30000UL) / 30000.0f;
    latitude = 28.613909f + 0.00035f * sinf(phase * 6.2831853f);
    longitude = 77.209015f + 0.00035f * cosf(phase * 6.2831853f);
  }
  speedKmh = 18.0f + (float)((millis() / 1000UL) % 28UL);
}

void publishTelemetry() {
  updatePositionAndSpeed();

  StaticJsonDocument<256> doc;
  doc["asset_id"] = ASSET_ID;
  doc["latitude"] = latitude;
  doc["longitude"] = longitude;
  doc["speed"] = speedKmh;
  doc["battery"] = readBatteryPercent();
  doc["device_uptime_ms"] = millis();

  char payload[256];
  size_t length = serializeJson(doc, payload, sizeof(payload));
  bool published = mqtt.publish(telemetryTopic().c_str(),
                                (const uint8_t*)payload, length, false);

  Serial.print(published ? "MQTT published: " : "MQTT publish failed: ");
  Serial.println(payload);

  ledOn = !ledOn;
  digitalWrite(STATUS_LED_PIN, ledOn ? HIGH : LOW);
}

void setup() {
  Serial.begin(115200);
  delay(250);
  pinMode(STATUS_LED_PIN, OUTPUT);
  pinMode(BATTERY_POT_PIN, INPUT);
  pinMode(GEOFENCE_POT_PIN, INPUT);
  analogReadResolution(12);

  Serial.println("\n=== IoT Asset Tracker / ESP32 MQTT ===");
  Serial.println("DHT22 is intentionally not used; backend simulates temperature.");
  Serial.print("Telemetry topic: ");
  Serial.println(telemetryTopic());

  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastPublishMs >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = now;
    publishTelemetry();
  }
}
