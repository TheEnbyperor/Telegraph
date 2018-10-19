import os
import json
import escpos
import time
import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc))
    client.subscribe("printer/print")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except json.decoder.JSONDecodeError:
        return
    print(payload)
    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S")


printer = escpos.printer.Dummy()

client = mqtt.Client(userdata={"printer": printer})
client.on_connect = on_connect
client.message_callback_add("printer/print", on_message)

client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)

while True:
    try:
        client.loop()
    except (KeyboardInterrupt, SystemExit):
        print("Bye!")
        break
