class Rect:
    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class EdgeSizes:
    def __init__(self, left: float, right: float, top: float, bottom: float):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


class Dimensions:
    def __init__(self, content: Rect, margin: EdgeSizes, border: EdgeSizes, padding: EdgeSizes):
        self.content = content
        self.margin = margin
        self.border = border
        self.padding = padding