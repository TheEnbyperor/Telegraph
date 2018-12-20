import os
import io
import json
import base64
import escpos.constants
import escpos.printer
import time
import math
import paho.mqtt.client as mqtt
import struct
import cairocffi as cairo
import jinja2
from PIL import Image, ImageOps
from weasyprint import HTML, CSS, default_url_fetcher

PAGE_STYLE = """
@page {
  width: 384px;
  height: 3840px;
  margin: 0;
}
body {
  margin: 0;
  font-size: 20px;
}
"""
TEMPLATE = jinja2.Template("""
<html>
    <head>
        <title>Telegraph</title>

        <style>
            body {
                font-family: sans-serif;
            }
            p {
                font-size: 23px;
            }
        </style>
    </head>
    <body>
        <h1>{{ subject|e }}</h1>
        <p>
            <b>Time:</b> {{ time|e }}
            {% if sender %}
                <br/>
                <b>From:</b> {{ sender|e }}
            {% endif %}
        </p>
    </body>
</html>
""")


class Context:
    def __init__(self, printer: escpos.printer.Escpos):
        self.printer = printer


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc), flush=True)
    client.subscribe("printer/print")


def write_image_surface(doc, printer, resolution=96):
    dppx = resolution / 96

    # This duplicates the hinting logic in Page.paint. There is a
    # dependency cycle otherwise:
    #   this → hinting logic → context → surface → this
    # But since we do no transform here, cairo_context.user_to_device and
    # friends are identity functions.
    widths = [int(math.ceil(p.width * dppx)) for p in doc.pages]
    heights = [int(math.ceil(p._page_box.children[0].height * dppx)) for p in doc.pages]

    max_width = max(widths)
    printer._raw(escpos.constants.ESC + b"3\x16")
    for page, width, height in zip(doc.pages, widths, heights):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max_width, height)
        context = cairo.Context(surface)
        pos_x = (max_width - width) / 2
        page.paint(context, pos_x, 0, scale=dppx, clip=True)
        target = io.BytesIO()
        surface.write_to_png(target)
        target.seek(0)
        im = Image.open(target)
        im.load()
        im = convert_image(im)
        print_image(im, printer)

    printer._raw(escpos.constants.ESC + b"2")

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
    outp = []
    header = escpos.constants.ESC + b"*\x21" + struct.pack("<H", im.width)
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
    printer._raw(b''.join(outp))


def attachment_fetcher_factory(attachments):
    def attachment_fetcher(url)
        if url.startswith('cid:'):
            cid = url[4:]
            attachment = attachments[cid]
            return dict(string=base64.b64decode(attachment["data"], mime_type=attachment["type"])
        else:
          return weasyprint.default_url_fetcher(url)
    return attachment_fetcher


def parse_html(printer: escpos.escpos.Escpos, html: str, attachments: dict):
    doc = HTML(string=html, url_fetcher=attachment_fetcher_factory(attachments)).render(stylesheets=[CSS(string=PAGE_STYLE, url_fetcher=attachment_fetcher_factory(attachments))], enable_hinting=True)
    write_image_surface(doc, printer)


def on_message(client, userdata: Context, msg: mqtt.MQTTMessage):
    try:
        payload = json.loads(msg.payload)
    except json.decoder.JSONDecodeError as e:
        print(f"JSON decode error {e}", flush=True)
        return

    subject = payload.get("subject")
    if subject is None:
        subject =  "None"
    message = payload.get("message")
    if message is None:
        return
    attachments = payload.get("attachments")
    if attachments is None:
        attachments = {}
    sender = payload.get("from")

    formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S")
    printer = userdata.printer

    print(f"New email from {sender}, subject: {subject}", flush=True)

    # Print header
    parse_html(printer, TEMPLATE.render(subject=subject, time=formatted_time, sender=sender), {})

    # Print message
    parse_html(printer, message, attachments)
    printer._raw(b"\n"*6)


if __name__ == "__main__":
    printer = escpos.printer.Usb(0x0416, 0x5011)
    # printer = escpos.printer.Dummy()
    printer._raw(escpos.constants.ESC + b"@")

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
