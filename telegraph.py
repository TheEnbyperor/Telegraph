import os
import io
import json
import escpos.constants
import escpos.printer
import time
import math
import paho.mqtt.client as mqtt
import struct
import cairocffi as cairo
from PIL import Image, ImageOps
from weasyprint import HTML, CSS

PAGE_STYLE = """
@page {
  width: 384px;
  margin: 0;
}
body {
  margin: 0;
  font-size: 20px;
}
"""


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


def write_image_surface(doc, resolution=96):
    dppx = resolution / 96

    # This duplicates the hinting logic in Page.paint. There is a
    # dependency cycle otherwise:
    #   this → hinting logic → context → surface → this
    # But since we do no transform here, cairo_context.user_to_device and
    # friends are identity functions.
    widths = [int(math.ceil(p.width * dppx)) for p in doc.pages]
    heights = [int(math.ceil(p._page_box.children[0].height * dppx)) for p in doc.pages]

    max_width = max(widths)
    sum_heights = sum(heights)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max_width, sum_heights)
    context = cairo.Context(surface)
    pos_y = 0
    for page, width, height in zip(doc.pages, widths, heights):
        pos_x = (max_width - width) / 2
        page.paint(context, pos_x, pos_y, scale=dppx, clip=True)
        pos_y += height
    return surface, max_width, sum_heights


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


def parse_html(printer: escpos.escpos.Escpos, html: str):
    doc = HTML(string=html).render(stylesheets=[CSS(string=PAGE_STYLE)], enable_hinting=True)
    surface, _, _ = write_image_surface(doc)
    target = io.BytesIO()
    surface.write_to_png(target)
    target.seek(0)
    im = Image.open(target)
    im.load()
    im = convert_image(im)
    print_image(im, printer)


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

    printer._raw(escpos.constants.ESC + b'\x40')

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
