import escpos.printer
import struct
from PIL import Image, ImageOps

if __name__ == "__main__":
    with open("Cat03.jpg", "rb") as f:
        img_original = Image.open(f)
        img_original.load()

    img_original = img_original.convert('RGBA')
    im = Image.new("RGB", img_original.size, (255, 255, 255))
    im.paste(img_original, mask=img_original.split()[3])
    wpercent = (380/float(im.size[0]))
    hsize = int((float(im.size[1])*float(wpercent)))
    im = im.resize((380, hsize), Image.ANTIALIAS)
    im = im.convert("L")
    im = ImageOps.invert(im)
    im = im.convert("1")

    printer = escpos.printer.Usb(0x0416, 0x5011)
    printer._raw(escpos.constants.ESC + b'\x40')

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

    printer._raw(escpos.constants.ESC + b'\x69')
