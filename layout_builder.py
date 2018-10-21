import enum
import typing
import tinycss.token_data
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

    def layout(self, containing_block: Dimensions):
        if self.box_type == BoxType.BLOCK:
            self.layout_block(containing_block)

    def layout_block(self, containing_block: Dimensions):
        self.calculate_block_width(containing_block)
        self.calculate_block_position(containing_block)
        self.layout_block_children()
        self.calculate_block_height()

    @staticmethod
    def value_token_to_int(value: tinycss.token_data.Token):
        if value.type == "INTEGER" or value.type == "NUMBER":
            return 0
        elif value.type == "DIMENSION":
            if value.unit == "px":
                return value.value
        elif value.type == "IDENT":
            if value.value == "auto":
                return "auto"
        return 0

    def get_single_int_value(self, name: str):
        value = self.node[name]
        if value is None:
           value = html_parser.CSS_PROPERTIES[name].initial_value
        if len(value) > 1:
            value = html_parser.CSS_PROPERTIES[name].initial_value
        value = value[0]
        if value.type not in ["INTEGER", "NUMBER", "DIMENSION", "NUMBER", "PERCENTAGE"]:
            value = html_parser.CSS_PROPERTIES[name].initial_value[0]
        if value.type == "INTEGER" or value.type == "NUMBER":
            if value.value != 0:
                value = html_parser.CSS_PROPERTIES[name].initial_value[0]
        return self.value_token_to_int(value)

    def calculate_block_width(self, containing_block: Dimensions):
        width = self.get_single_int_value("width")
        margin_left = self.get_single_int_value("margin-left")
        margin_right = self.get_single_int_value("margin-right")
        padding_left = self.get_single_int_value("padding-left")
        padding_right = self.get_single_int_value("padding-right")

        total = sum(map(lambda v: 0 if v == "auto" else v, [width, margin_left, margin_right,
                                                            padding_left, padding_right]))

        if width != "auto" and total > containing_block.content.width:
            if margin_left == "auto":
                margin_left = 0
            if margin_right == "auto":
                margin_right = 0

        underflow = containing_block.content.width - total

        if width != "auto" and margin_left != "auto" and margin_right != "auto":
            margin_right = margin_right + underflow
        elif width != "auto" and margin_left != "auto" and margin_right == "auto":
            margin_right = underflow
        elif width != "auto" and margin_left == "auto" and margin_right != "auto":
            margin_left = underflow
        elif width == "auto":
            if margin_left == "auto":
                margin_left = 0
            if margin_right == "auto":
                margin_right = 0

            if underflow >= 0:
                width = underflow
            else:
                width = 0
                margin_right = margin_right + underflow
        elif margin_left == "auto" and margin_right == "auto":
            margin_left = underflow / 2
            margin_right = underflow / 2

        self.dimensions.content.width = width
        self.dimensions.padding.left = padding_left
        self.dimensions.padding.right = padding_right
        self.dimensions.margin.left = margin_left
        self.dimensions.margin.right = margin_right


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
    print(root, has_block_children)
    for child in style_node.children:
        display = child.display()
        print(display)
        if display == html_parser.Display.BLOCK:
            root.children.append(build_layout_box(child))
        elif display == html_parser.Display.INLINE:
            container = root
            if has_block_children:
                if container.box_type == BoxType.INLINE:
                    container.box_type = BoxType.BLOCK
                container = root.get_inline_container()
            container.children.append(build_layout_box(child))

    return root
