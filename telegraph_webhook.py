import os
import paho.mqtt.client as mqtt
from flask import Flask

app = Flask(__name__)


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc))


@app.route('/print-shopping-list', methods=['GET'])
def shopping_list_hook():
    client.publish("printer/shopping-list")
    return "OK"


if __name__ == '__main__':
    client = mqtt.Client()
    client.on_connect = on_connect

    client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)
    client.loop_start()

    app.run(host="0.0.0.0", port=80)
