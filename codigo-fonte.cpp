#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "DHTesp.h"
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

// Definição dos pinos do display TFT
#define TFT_CS 32  // Chip Select do display
#define TFT_DC 33  // Data/Command do display
#define TFT_RST 16 // Reset do display

// Pino do sensor DHT22
const int DHT_PIN = 15;

// Instância do display TFT
Adafruit_ILI9341 tft = Adafruit_ILI9341(TFT_CS, TFT_DC);

// Configurações editáveis
const char* default_SSID = "Wokwi-GUEST";             // Nome da rede Wi-Fi
const char* default_PASSWORD = "";                   // Senha da rede Wi-Fi
const char* default_BROKER_MQTT = "ip_do_broker";   // IP do Broker MQTT
const int default_BROKER_PORT = 1883;                // Porta do Broker MQTT
const char* default_TOPICO_SUBSCRIBE = "/TEF/lamp003/cmd"; // Tópico para escuta no Broker
const char* default_TOPICO_PUBLISH_1 = "/TEF/lamp003/attrs";  // Publicação de estado do LED
const char* default_TOPICO_PUBLISH_2 = "/TEF/lamp003/attrs/l"; // Publicação de luminosidade
const char* default_TOPICO_PUBLISH_3 = "/TEF/DHT001/attrs/t";  // Publicação de temperatura
const char* default_TOPICO_PUBLISH_4 = "/TEF/DHT001/attrs/h";  // Publicação de umidade
const char* default_TOPICO_PUBLISH_5 = "/TEF/POT001/attrs/v";  // Publicação de tensão
const char* default_ID_MQTT = "fiware_003";          // ID do dispositivo no Broker MQTT
const int default_D4 = 2;                            // Pino do LED onboard
const char* topicPrefix = "lamp003";                 // Prefixo de tópicos MQTT

// Instâncias de componentes
DHTesp dht;                  // Sensor de temperatura e umidade
WiFiClient espClient;        // Cliente Wi-Fi
PubSubClient MQTT(espClient);// Cliente MQTT

// Variáveis globais
char EstadoSaida = '0';      // Estado do LED ('0' desligado, '1' ligado)
int voltage;                 // Tensão lida
int luminosity;              // Luminosidade lida
TempAndHumidity data;        // Dados do sensor DHT22

// Inicializa a comunicação serial
void initSerial() {
    Serial.begin(115200);
}

// Reconeção ao Wi-Fi
void reconectWiFi() {
    if (WiFi.status() == WL_CONNECTED)
        return; // Já conectado

    WiFi.begin(default_SSID, default_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(100);
        Serial.print(".");
    }
    Serial.println("\nConectado ao Wi-Fi!");
    Serial.println(WiFi.localIP()); // Exibe o IP obtido
    digitalWrite(default_D4, LOW);  // Garante que o LED comece desligado
}

// Callback MQTT para tratar mensagens recebidas
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    String msg;
    for (int i = 0; i < length; i++) {
        msg += (char)payload[i];
    }
    Serial.println("Mensagem recebida: " + msg);

    String onTopic = String(topicPrefix) + "@on|";
    String offTopic = String(topicPrefix) + "@off|";

    if (msg.equals(onTopic)) {
        digitalWrite(default_D4, HIGH);
        EstadoSaida = '1';
    } else if (msg.equals(offTopic)) {
        digitalWrite(default_D4, LOW);
        EstadoSaida = '0';
    }
}

// Inicializa o Wi-Fi
void initWiFi() {
    Serial.println("Conectando ao Wi-Fi...");
    reconectWiFi();
}

// Inicializa o cliente MQTT
void initMQTT() {
    MQTT.setServer(default_BROKER_MQTT, default_BROKER_PORT);
    MQTT.setCallback(mqtt_callback);
}

// Reconeção ao Broker MQTT
void reconnectMQTT() {
    while (!MQTT.connected()) {
        Serial.println("Conectando ao Broker MQTT...");
        if (MQTT.connect(default_ID_MQTT)) {
            Serial.println("Conectado ao Broker!");
            MQTT.subscribe(default_TOPICO_SUBSCRIBE);
        } else {
            Serial.println("Falha ao conectar. Tentando novamente em 2s.");
            delay(2000);
        }
    }
}

// Verifica conexões Wi-Fi e MQTT
void VerificaConexoesWiFIEMQTT() {
    if (!MQTT.connected())
        reconnectMQTT();
    reconectWiFi();
}

// Envia o estado do LED via MQTT
void EnviaEstadoOutputMQTT() {
    if (EstadoSaida == '1') {
        MQTT.publish(default_TOPICO_PUBLISH_1, "s|on");
    } else {
        MQTT.publish(default_TOPICO_PUBLISH_1, "s|off");
    }
    delay(1000);
}

// Configura o LED onboard como saída
void InitOutput() {
    pinMode(default_D4, OUTPUT);
    digitalWrite(default_D4, LOW); // Começa desligado
}

// Lê a luminosidade e envia via MQTT
void handleLuminosity() {
    const int potPin = 34;
    int sensorValue = analogRead(potPin);
    luminosity = map(sensorValue, 0, 4095, 0, 100);
    MQTT.publish(default_TOPICO_PUBLISH_2, String(luminosity).c_str());
}

// Lê os dados do DHT22 e envia via MQTT
void handleDHT() {
    data = dht.getTempAndHumidity();
    MQTT.publish(default_TOPICO_PUBLISH_3, String(data.temperature, 2).c_str());
    MQTT.publish(default_TOPICO_PUBLISH_4, String(data.humidity, 1).c_str());
}

// Lê a tensão e envia via MQTT
void handleVoltage() {
    const int pin = 35;
    int value = analogRead(pin);
    voltage = map(value, 0, 4095, 0, 300);
    MQTT.publish(default_TOPICO_PUBLISH_5, String(voltage).c_str());
}

// Exibe os dados no display TFT
void VerficaEMostra(int luminosity, int voltage, TempAndHumidity data) {
    tft.fillScreen(ILI9341_BLACK);

    tft.setCursor(10, 25);
    tft.setTextColor(ILI9341_WHITE);
    tft.setTextSize(2);
    tft.print("Temperatura: ");
    tft.print(data.temperature);
    tft.println(" C");

    tft.setCursor(10, 75);
    tft.print("Umidade: ");
    tft.print(data.humidity);
    tft.println(" %");

    tft.setCursor(10, 125);
    tft.print("Luminosidade: ");
    tft.print(luminosity);
    tft.println(" lx");

    tft.setCursor(10, 175);
    tft.print("Tensao: ");
    tft.print(voltage);
    tft.println(" V");

    // Exibe alertas com base nos limites
    if (luminosity < 35) {
        tft.setCursor(10, 200);
        tft.setTextColor(ILI9341_RED);
        tft.println("ALERTA: Luminosidade Baixa!");
    }
    if (voltage < 100) {
        tft.setCursor(10, 225);
        tft.println("ALERTA: Queda de Tensao!");
    }
    if (data.temperature > 60) {
        tft.setCursor(10, 250);
        tft.println("ALERTA: Temperatura Alta!");
    }
    if (data.humidity > 70) {
        tft.setCursor(10, 275);
        tft.println("ALERTA: Umidade Alta!");
    }
}

// Configurações iniciais
void setup() {
    InitOutput();
    initSerial();
    initWiFi();
    initMQTT();
    dht.setup(DHT_PIN, DHTesp::DHT22);
    tft.begin();
    tft.setRotation(1);
    tft.fillScreen(ILI9341_BLACK);
    delay(5000);
}

// Loop principal
void loop() {
    VerificaConexoesWiFIEMQTT();
    EnviaEstadoOutputMQTT();
    handleLuminosity();
    handleDHT();
    handleVoltage();
    VerficaEMostra(luminosity, voltage, data);
    MQTT.loop();
}
