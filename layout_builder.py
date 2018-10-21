import enum
import typing
import html_parser


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

    @classmethod
    def default(cls):
        return cls(Rect(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0))


@enum.unique
class BoxType(enum.Enum):
    INLINE = enum.auto()
    BLOCK = enum.auto()
    ANONYMOUS = enum.auto()


class LayoutBox:
    def __init__(self, box_type: BoxType, node=None):
        self.dimensions = Dimensions.default()
        self.box_type = box_type
        self.children = []
        self.node = node

    def __repr__(self, level=0):
        ret = "\t" * level + f"<LayoutBox {self.dimensions} {type(self.node)} {self.box_type} ["
        for child in self.children:
            ret += "\n" + child.__repr__(level + 1)
        ret += ("\n" + ("\t" * level) if len(self.children) >= 1 else "") + "]"
        return ret

    def get_inline_container(self):
        if self.box_type in [BoxType.INLINE, BoxType.ANONYMOUS]:
            return self
        else:
            if len(self.children) < 1 or self.children[-1].box_type != BoxType.ANONYMOUS:
                    self.children.append(LayoutBox(BoxType.ANONYMOUS))
            return self.children[-1]


def build_layout_box(style_node) -> typing.Union[None, LayoutBox]:
    root_layout = style_node.display()
    if root_layout == html_parser.Display.INLINE:
        root_layout = BoxType.INLINE
    elif root_layout == html_parser.Display.BLOCK:
        root_layout = BoxType.BLOCK
    elif root_layout == html_parser.Display.NONE:
        return None
    root = LayoutBox(root_layout, style_node)

    has_block_children = any(c.display() == html_parser.Display.BLOCK for c in style_node.children)

    if style_node.node.text is not None:
        layout_box = LayoutBox(BoxType.INLINE, style_node.node.text)
        if root_layout == BoxType.BLOCK:
            root.children.append(layout_box)
        elif root_layout == BoxType.INLINE:
            container = root
            if has_block_children:
                container = root.get_inline_container()
            container.children.append(layout_box)

    for child in style_node.children:
        display = child.display()
        if display == html_parser.Display.BLOCK:
            root.children.append(build_layout_box(child))
            if child.node.tail is not None:
                root.children.append(LayoutBox(BoxType.INLINE, child.node.tail))
        elif display == html_parser.Display.INLINE:
            container = root
            if has_block_children:
                container = root.get_inline_container()
            container.children.append(build_layout_box(child))
            if child.node.tail is not None:
                container.children.append(LayoutBox(BoxType.INLINE, child.node.tail))

    return root
