import os
import json
import escpos.printer
import time
import paho.mqtt.client as mqtt


class Context:
    def __init__(self, printer: escpos.printer.Escpos):
        self.printer = printer


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc))
    client.subscribe("printer/print")


def on_message(client, userdata: Context, msg):
    try:
        payload = json.loads(msg.payload)
    except json.decoder.JSONDecodeError:
        return

    subject = payload.get("subject")
    if subject is None:
        return
    message = payload.get("message")
    if message is None:
        return

    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S")
    printer = userdata.printer

    # Print subject
    printer.set()
    printer.set(double_height=True)
    printer.textln(subject)

    # Print message time
    printer.set(bold=True)
    printer.text("Time: ")
    printer.set(bold=False)
    printer.textln(formatted_time)

    # Print message
    printer.textln("")
    printer.textln(message)
    printer.cut()
    print(printer.output)


printer = escpos.printer.Dummy()
printer.hw("INIT")

context = Context(printer)

client = mqtt.Client(userdata=context)
client.on_connect = on_connect
client.message_callback_add("printer/print", on_message)

client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)

while True:
    try:
        client.loop()
    except (KeyboardInterrupt, SystemExit):
        print("Bye!")
        break
