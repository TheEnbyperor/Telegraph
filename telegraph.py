import os
import json
import escpos.constants
import escpos.printer
import time
import paho.mqtt.client as mqtt
import bs4
from bs4 import BeautifulSoup


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


def walk_html_tree(node, printer):
    if node.name is not None:
        for child in node.children:
            if isinstance(child, bs4.element.NavigableString):
                printer.text(str(child))
            elif child.name == "i":
                printer._raw(escpos.constants.ESC + b'\x34\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x34\x00')
            elif child.name == "b":
                printer._raw(escpos.constants.ESC + b'\x45\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x45\x00')
            elif child.name == "b":
                printer._raw(escpos.constants.ESC + b'\x2d\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x2d\x00')
            else:
                walk_html_tree(child, printer)


def parse_html(printer, html):
    soup = BeautifulSoup(html, features="html.parser")
    walk_html_tree(soup, printer)


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
    sender = payload.get("from")

    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S")
    printer = userdata.printer

    # Print subject
    printer._raw(escpos.constants.GS + b'\x21\x01')
    printer.textln(subject)
    printer._raw(escpos.constants.GS + b'\x21\x00')

    # Print message time
    printer._raw(escpos.constants.ESC + b'\x45\x01')
    printer.text("Time: ")
    printer._raw(escpos.constants.ESC + b'\x45\x00')
    printer.textln(formatted_time)

    # Print sender if available
    if sender is not None:
        printer._raw(escpos.constants.ESC + b'\x45\x01')
        printer.text("From: ")
        printer._raw(escpos.constants.ESC + b'\x45\x00')
        printer.textln(sender)

    # Print message
    printer.textln("")
    parse_html(printer, message)
    printer.cut()


if __name__ == "__main__":
    printer = escpos.printer.Usb(0x0416, 0x5011)
    printer._raw(escpos.constants.ESC + b'\x40')

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
