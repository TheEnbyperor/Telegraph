import io
import math
import cairocffi as cairo
from weasyprint import HTML, CSS


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


if __name__ == "__main__":
    html = """
    ✨✨✨ SPARKLES ✨✨✨
    """

    style = """
    @page {
      width: 384px;
      margin: 0;
    }
    body {
      margin: 0;
      font-family: "Noto Color Emoji", serif;
    }
    """

    doc = HTML(string=html).render(stylesheets=[CSS(string=style)], enable_hinting=True)
    surface, _, _ = write_image_surface(doc)
    target = open("./test.png", "wb")
    surface.write_to_png(target)
