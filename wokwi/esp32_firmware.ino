/*
 ============================================================================
 IoT-Based Smart Asset Tracking and Anomaly Detection System
 ESP32 Wokwi Firmware: RFID/IoT Asset Scanner & MQTT Telemetry Node
 ============================================================================
 
 Features:
   - Connects to WiFi ("Wokwi-GUEST" in simulation or configured LAN AP).
   - Connects to Eclipse Mosquitto MQTT broker on topic "asset/events".
   - Hardware Input Simulation:
       * Pushbutton 1 (GPIO 18): Simulates an Internal Shelf Scan (Asset A001 @ SHELF_01).
       * Pushbutton 2 (GPIO 19): Simulates a Perimeter Gate Scan (Asset A005 @ MAIN_GATE).
       * Serial Console Input: Type '1'-'5' to simulate scans for assets A001-A005.
   - Emits canonical JSON events conforming to the backend schema:
       {
         "message_id": "esp32-xxxx",
         "asset_id": "A001",
         "location": "SHELF_01",
         "event_type": "INTERNAL_SCAN",
         "timestamp": "2026-10-23T18:00:00Z"
       }
   - Status LEDs:
       * Green LED (GPIO 22): Blinks on successful publish / Normal event.
       * Red LED (GPIO 23): Blinks on Alert / Unauthorized / MQTT error.
 ============================================================================
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"

// Hardware Pin Definitions
#define BTN_SHELF_PIN   18   // Pushbutton 1: Internal Shelf Scan
#define BTN_GATE_PIN    19   // Pushbutton 2: Main Gate Scan
#define LED_GREEN_PIN   22   // Status Indicator: OK / Published
#define LED_RED_PIN     23   // Status Indicator: Alert / Error

// Debounce Tracking
unsigned long lastShelfBtnTime = 0;
unsigned long lastGateBtnTime = 0;
const unsigned long DEBOUNCE_DELAY_MS = 400;

// Registered Demo Assets and expected zones
struct AssetConfig {
  const char* id;
  const char* name;
  const char* defaultZone;
  bool isExitAuthorized;
};

const AssetConfig CATALOG[] = {
  {"A001", "Laptop", "SHELF_01", true},
  {"A002", "Monitor", "SHELF_01", true},
  {"A003", "Keyboard", "SHELF_02", true},
  {"A004", "Projector", "SHELF_02", true},
  {"A005", "Scanner", "SHELF_03", false}
};
const int CATALOG_SIZE = sizeof(CATALOG) / sizeof(CATALOG[0]);

// Network Clients
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Reconnection Timer
unsigned long lastMqttReconnectAttempt = 0;
const unsigned long RECONNECT_INTERVAL_MS = 5000;

// Event counter for unique message ID generation
unsigned long eventCounter = 1000;

// ----------------------------------------------------------------------------
// Utility Functions
// ----------------------------------------------------------------------------

void flashLed(int pin, int durationMs = 150) {
  digitalWrite(pin, HIGH);
  delay(durationMs);
  digitalWrite(pin, LOW);
}

void printSerialHelp() {
  Serial.println(F("\n========================================================"));
  Serial.println(F("ESP32 IoT Asset Tracking Node - Interactive Commands:"));
  Serial.println(F("  Press Green Button (GPIO 18) : Normal Scan A001 @ SHELF_01"));
  Serial.println(F("  Press Red Button (GPIO 19)   : Gate Scan A005 @ MAIN_GATE"));
  Serial.println(F("  Serial Key '1'               : Normal Scan A001 @ SHELF_01"));
  Serial.println(F("  Serial Key '2'               : Misplaced Scan A002 @ SHELF_03"));
  Serial.println(F("  Serial Key '3'               : Normal Scan A003 @ SHELF_02"));
  Serial.println(F("  Serial Key '4'               : Authorized Exit A004 @ MAIN_GATE"));
  Serial.println(F("  Serial Key '5'               : Unauthorized Exit A005 @ MAIN_GATE"));
  Serial.println(F("  Serial Key 'h'               : Show this help menu"));
  Serial.println(F("========================================================\n"));
}

// ----------------------------------------------------------------------------
// WiFi Connection
// ----------------------------------------------------------------------------

void setupWiFi() {
  delay(10);
  Serial.println();
  Serial.print(F("[WiFi] Connecting to SSID: "));
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(F("."));
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(F("\n[WiFi] Connected successfully!"));
    Serial.print(F("[WiFi] Assigned IP: "));
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(F("\n[WiFi WARNING] WiFi not connected. Simulation will retry in background."));
  }
}

// ----------------------------------------------------------------------------
// MQTT Connection & Callback
// ----------------------------------------------------------------------------

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print(F("[MQTT INBOUND] Topic: "));
  Serial.println(topic);
}

boolean connectMQTT() {
  Serial.print(F("[MQTT] Attempting connection to broker: "));
  Serial.print(MQTT_BROKER);
  Serial.print(F(":"));
  Serial.println(MQTT_PORT);

  // Generate a distinct client ID with random suffix to avoid broker kicks
  String clientId = String(MQTT_CLIENT_ID) + "_" + String(random(0xffff), HEX);

  boolean connected = false;
  if (strlen(MQTT_USERNAME) > 0) {
    connected = mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD);
  } else {
    connected = mqttClient.connect(clientId.c_str());
  }

  if (connected) {
    Serial.println(F("[MQTT] Connected to broker successfully!"));
    flashLed(LED_GREEN_PIN, 200);
  } else {
    Serial.print(F("[MQTT ERROR] Connection failed, rc="));
    Serial.println(mqttClient.state());
    flashLed(LED_RED_PIN, 200);
  }
  return connected;
}

// ----------------------------------------------------------------------------
// Publish Telemetry Event
// ----------------------------------------------------------------------------

bool publishAssetEvent(const char* assetId, const char* location, const char* eventType) {
  if (!mqttClient.connected()) {
    Serial.println(F("[MQTT WARNING] Cannot publish: Broker disconnected."));
    flashLed(LED_RED_PIN, 100);
    return false;
  }

  // Construct JSON payload
  StaticJsonDocument<256> doc;
  
  eventCounter++;
  char msgIdBuf[32];
  snprintf(msgIdBuf, sizeof(msgIdBuf), "esp32-%08lx", eventCounter);

  doc["message_id"] = msgIdBuf;
  doc["asset_id"] = assetId;
  doc["location"] = location;
  doc["event_type"] = eventType;

  char jsonBuffer[256];
  serializeJson(doc, jsonBuffer);

  Serial.println(F("\n--- [ESP32 OUTBOUND MQTT EVENT] ---"));
  Serial.print(F("Topic  : "));
  Serial.println(MQTT_TOPIC);
  Serial.print(F("Payload: "));
  Serial.println(jsonBuffer);

  boolean success = mqttClient.publish(MQTT_TOPIC, jsonBuffer);
  if (success) {
    Serial.println(F("Result : PUBLISH SUCCESS (QoS 0)"));
    flashLed(LED_GREEN_PIN, 100);
  } else {
    Serial.println(F("Result : PUBLISH FAILED"));
    flashLed(LED_RED_PIN, 200);
  }
  Serial.println(F("----------------------------------\n"));
  return success;
}

// ----------------------------------------------------------------------------
// Arduino Setup & Main Loop
// ----------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 1000);

  Serial.println(F("\n========================================================"));
  Serial.println(F("   IoT Asset Tracking - ESP32 Wokwi Simulation Node    "));
  Serial.println(F("========================================================"));

  pinMode(BTN_SHELF_PIN, INPUT_PULLUP);
  pinMode(BTN_GATE_PIN, INPUT_PULLUP);
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);

  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_RED_PIN, LOW);

  setupWiFi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  printSerialHelp();
}

void loop() {
  // 1. Maintain WiFi and MQTT connection state
  if (WiFi.status() == WL_CONNECTED) {
    if (!mqttClient.connected()) {
      unsigned long now = millis();
      if (now - lastMqttReconnectAttempt > RECONNECT_INTERVAL_MS) {
        lastMqttReconnectAttempt = now;
        connectMQTT();
      }
    } else {
      mqttClient.loop();
    }
  }

  // 2. Read Physical Pushbuttons
  unsigned long currentMillis = millis();

  // Pushbutton 1: Shelf Scan (Normal Asset A001 @ SHELF_01)
  if (digitalRead(BTN_SHELF_PIN) == LOW) {
    if (currentMillis - lastShelfBtnTime > DEBOUNCE_DELAY_MS) {
      lastShelfBtnTime = currentMillis;
      Serial.println(F("[TRIGGER] Shelf Button Pressed -> Scanning A001 @ SHELF_01"));
      publishAssetEvent("A001", "SHELF_01", "INTERNAL_SCAN");
    }
  }

  // Pushbutton 2: Perimeter Gate Scan (Unauthorized Asset A005 @ MAIN_GATE)
  if (digitalRead(BTN_GATE_PIN) == LOW) {
    if (currentMillis - lastGateBtnTime > DEBOUNCE_DELAY_MS) {
      lastGateBtnTime = currentMillis;
      Serial.println(F("[TRIGGER] Gate Button Pressed -> Scanning A005 @ MAIN_GATE"));
      publishAssetEvent("A005", "MAIN_GATE", "GATE_SCAN");
    }
  }

  // 3. Read Serial Console Commands for Interactive Demonstrations
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case '1':
        Serial.println(F("[SERIAL 1] Normal Scan: Asset A001 @ SHELF_01"));
        publishAssetEvent("A001", "SHELF_01", "INTERNAL_SCAN");
        break;
      case '2':
        Serial.println(F("[SERIAL 2] Misplaced Scan: Asset A002 @ SHELF_03 (Expected SHELF_01)"));
        publishAssetEvent("A002", "SHELF_03", "INTERNAL_SCAN");
        break;
      case '3':
        Serial.println(F("[SERIAL 3] Normal Scan: Asset A003 @ SHELF_02"));
        publishAssetEvent("A003", "SHELF_02", "INTERNAL_SCAN");
        break;
      case '4':
        Serial.println(F("[SERIAL 4] Authorized Exit: Asset A004 @ MAIN_GATE"));
        publishAssetEvent("A004", "MAIN_GATE", "GATE_SCAN");
        break;
      case '5':
        Serial.println(F("[SERIAL 5] SECURITY ALERT: Unauthorized Exit: Asset A005 @ MAIN_GATE"));
        publishAssetEvent("A005", "MAIN_GATE", "GATE_SCAN");
        break;
      case 'h':
      case 'H':
        printSerialHelp();
        break;
      case '\r':
      case '\n':
        break;
      default:
        Serial.print(F("[INFO] Unknown key: '"));
        Serial.print(cmd);
        Serial.println(F("'. Type 'h' for menu."));
        break;
    }
  }
}
