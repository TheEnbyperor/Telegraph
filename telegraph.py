import os
import io
import json
import regex
import typing
import escpos.constants
import escpos.printer
import time
import paho.mqtt.client as mqtt
import bs4
import struct
import w3lib.url
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from emoji import UNICODE_EMOJI


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


def is_emoji(s: str) -> bool:
    count = 0
    for emoji in UNICODE_EMOJI:
        count += s.count(emoji)
        if count > 1:
            return False
    return bool(count)


def convert_image(img: Image) -> Image:
    img_original = img.convert('RGBA')
    im = Image.new("RGB", img_original.size, (255, 255, 255))
    im.paste(img_original, mask=img_original.split()[3])
    wpercent = (384 / float(im.size[0]))
    hsize = int((float(im.size[1]) * float(wpercent)))
    im = im.resize((384, hsize), Image.ANTIALIAS)
    im = im.convert("L")
    im = ImageOps.invert(im)
    im = im.convert("1")
    return im


def get_image(url: str) -> typing.Union[None, Image.Image]:
    try:
        data_uri = w3lib.url.parse_data_uri(url)
        try:
            im = Image.open(io.BytesIO(data_uri.data))
            im.load()
            return im
        except IOError:
            return None
    except ValueError:
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None
        try:
            im = Image.open(io.BytesIO(response.content))
            im.load()
            return im
        except IOError:
            return None


def print_image(im: Image.Image, printer: escpos.escpos.Escpos):
    header = escpos.constants.ESC + b"*\x21" + struct.pack("<H", im.width)
    outp = [escpos.constants.ESC + b"3\x16"]  # Adjust line-feed size
    im = im.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)
    line_height = 24
    width_pixels, height_pixels = im.size
    top = 0
    left = 0
    while left < width_pixels:
        box = (left, top, left + line_height, top + height_pixels)
        im_slice = im.transform((line_height, height_pixels), Image.EXTENT, box)
        im_bytes = im_slice.tobytes()
        outp.append(header + im_bytes + b"\n")
        left += line_height
    outp.append(escpos.constants.ESC + b"2")  # Reset line-feed size
    printer._raw(b''.join(outp))


def print_emoji(text: str, printer: escpos.escpos.Escpos):
    im = Image.new('RGB', (24, 24), 'white')
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype('NotoEmoji-Regular.ttf', 18)
    draw.text((0, 0), text, (0, 0, 0), font=font)
    im = im.convert("L")
    im = ImageOps.invert(im)
    im = im.convert("1")
    header = escpos.constants.ESC + b"*\x21" + struct.pack("<H", im.width)
    im = im.transpose(Image.ROTATE_270).transpose(Image.FLIP_LEFT_RIGHT)
    outp = [escpos.constants.ESC + b"3\x16"]  # Adjust line-feed size
    im_bytes = im.tobytes()
    outp.append(header + im_bytes)
    outp.append(escpos.constants.ESC + b"2")  # Reset line-feed size
    printer._raw(b''.join(outp))


def print_text(text: str, printer: escpos.escpos.Escpos):
    text = regex.findall(r'.\p{Sk}+|\X', text)
    for char in text:
        if len(char) > 1 or ord(char) > 127:
            print_emoji(char, printer)
        else:
            printer.text(char)


def walk_html_tree(node: bs4.element.Tag, printer: escpos.escpos.Escpos):
    if node.name is not None:
        for child in node.children:
            if isinstance(child, bs4.element.NavigableString):
                print_text(str(child), printer)
            elif child.name == "br":
                print_text('\n', printer)
            elif child.name == "i" or child.name == "em" or child.name == "cite":
                printer._raw(escpos.constants.ESC + b'\x34\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x34\x00')
            elif child.name == "b":
                printer._raw(escpos.constants.ESC + b'\x45\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x45\x00')
            elif child.name == "u":
                printer._raw(escpos.constants.ESC + b'\x2d\x01')
                walk_html_tree(child, printer)
                printer._raw(escpos.constants.ESC + b'\x2d\x00')
            elif child.name == "h1":
                printer._raw(escpos.constants.ESC + b'\x21\x12')
                printer._raw(escpos.constants.ESC + b'\x45\x01')
                walk_html_tree(child, printer)
                print_text('\n', printer)
                printer._raw(escpos.constants.ESC + b'\x21\x00')
                printer._raw(escpos.constants.ESC + b'\x45\x00')
            elif child.name == "h2":
                printer._raw(escpos.constants.ESC + b'\x21\x11')
                printer._raw(escpos.constants.ESC + b'\x45\x01')
                walk_html_tree(child, printer)
                print_text('\n', printer)
                printer._raw(escpos.constants.ESC + b'\x21\x00')
                printer._raw(escpos.constants.ESC + b'\x45\x00')
            elif child.name == "h3":
                printer._raw(escpos.constants.ESC + b'\x21\x01')
                printer._raw(escpos.constants.ESC + b'\x45\x01')
                walk_html_tree(child, printer)
                print_text('\n', printer)
                printer._raw(escpos.constants.ESC + b'\x21\x00')
                printer._raw(escpos.constants.ESC + b'\x45\x00')
            elif child.name == "img":
                img = get_image(child['src'])
                if img is None:
                    print_text(str(child['alt']), printer)
                else:
                    img = convert_image(img)
                    print_image(img, printer)
            else:
                walk_html_tree(child, printer)


def parse_html(printer: escpos.escpos.Escpos, html: str):
    soup = BeautifulSoup(html, features="html.parser")
    walk_html_tree(soup, printer)


def on_message(client, userdata: Context, msg: mqtt.MQTTMessage):
    try:
        payload = json.loads(msg.payload)
    except json.decoder.JSONDecodeError:
        return

    subject = payload.get("subject")
    if subject is None:
        subject =  "None"
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
    # printer = escpos.printer.Dummy()
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
