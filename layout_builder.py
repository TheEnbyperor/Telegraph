import enum
import typing
import tinycss.token_data
import html_parser
from PIL import ImageFont


class EdgeSizes:
    def __init__(self, left: float, right: float, top: float, bottom: float):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom

    def __repr__(self):
        return f"EdgeSizes({self.left}, {self.right}, {self.top}, {self.bottom})"


class Rect:
    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.height}, {self.width})"

    def expanded_by(self, edge: EdgeSizes):
        return Rect(self.x - edge.left,
                    self.y - edge.left,
                    self.width + edge.left + edge.right,
                    self.height + edge.top + edge.bottom)


class Dimensions:
    def __init__(self, content: Rect, margin: EdgeSizes, border: EdgeSizes, padding: EdgeSizes):
        self.content = content
        self.margin = margin
        self.border = border
        self.padding = padding

    def __repr__(self):
        return f"Dimensions({self.content}, {self.margin}, {self.border}, {self.padding})"

    @classmethod
    def default(cls):
        return cls(Rect(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0), EdgeSizes(0, 0, 0, 0))

    @property
    def padding_box(self) -> Rect:
        return self.content.expanded_by(self.padding)

    @property
    def border_box(self) -> Rect:
        return self.padding_box.expanded_by(self.border)

    @property
    def margin_box(self) -> Rect:
        return self.border_box.expanded_by(self.margin)

@enum.unique
class BoxType(enum.Enum):
    INLINE = enum.auto()
    BLOCK = enum.auto()
    ANONYMOUS = enum.auto()
    LINE = enum.auto()


class LayoutBox:
    def __init__(self, box_type: BoxType, parent, node, parser):
        self.dimensions = Dimensions.default()
        self.box_type = box_type
        self.children = []
        self.parent = parent
        self.node = node
        self.parser = parser
        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12, encoding="unic")

    def __repr__(self, level=0):
        ret = "\t" * level + f"<LayoutBox {self.dimensions} {self.node.node} {self.box_type} ["
        for child in self.children:
            ret += "\n" + child.__repr__(level + 1)
        ret += ("\n" + ("\t" * level) if len(self.children) >= 1 else "") + "]"
        return ret

    def get_inline_container(self):
        if self.box_type in [BoxType.INLINE, BoxType.ANONYMOUS]:
            return self
        else:
            if len(self.children) < 1 or self.children[-1].box_type != BoxType.ANONYMOUS:
                    self.children.append(
                        LayoutBox(BoxType.ANONYMOUS,
                                  self,
                                  html_parser.StyledNode(None,
                                                         self.parser.cascade_rules([], self.node.style_rules),
                                                         []),
                                  self.parser)
                    )
            return self.children[-1]

    def layout(self, containing_block: Dimensions, prev_dimensions: Dimensions):
        if self.box_type in [BoxType.BLOCK, BoxType.ANONYMOUS]:
            self.layout_block(containing_block, prev_dimensions)
        elif self.box_type == BoxType.INLINE:
            self.layout_inline(containing_block)

    def layout_block(self, containing_block: Dimensions, prev_dimensions: Dimensions):
        self.calculate_block_width(containing_block)
        self.calculate_block_position(containing_block, prev_dimensions)
        self.layout_block_children()
        self.calculate_block_height()

    def layout_inline(self, containing_block: Dimensions):
        self.layout_inline_children()
        self.calculate_inline_size(containing_block)
        self.calculate_inline_position(containing_block)
        # self.layout_block_children()
        # self.calculate_block_height()

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

    def calculate_inline_size(self, containing_block: Dimensions):
        if isinstance(self.node.node, list):
            self.dimensions.content.width, self.dimensions.content.height = self.font.getsize(" ".join(self.node.node))

    def calculate_block_position(self, containing_block: Dimensions, prev_dimensions: Dimensions):
        if prev_dimensions is not None:
            self.dimensions.margin.top = max(self.get_single_int_value("margin-top"), prev_dimensions.margin.bottom)
        else:
            self.dimensions.margin.top = self.get_single_int_value("margin-top")
        self.dimensions.margin.bottom = self.get_single_int_value("margin-bottom")
        self.dimensions.padding.top = self.get_single_int_value("padding-top")
        self.dimensions.padding.bottom = self.get_single_int_value("padding-bottom")

        self.dimensions.content.x = containing_block.content.x + self.dimensions.margin.left \
                                    + self.dimensions.border.left + self.dimensions.padding.left
        self.dimensions.content.y = containing_block.content.height + containing_block.content.y \
                                    + self.dimensions.margin.top + self.dimensions.border.top \
                                    + self.dimensions.padding.top

    def find_or_create_line_box(self):
        parent = self.parent
        child = self
        while parent is not None:
            for c in parent.children:
                if c.box_type == BoxType.LINE:
                    c.children.append(child)
                    index = parent.children.index(child)
                    del parent.children[index]
                    child.parent = c
                    return c
            if parent.box_type in [BoxType.BLOCK, BoxType.ANONYMOUS]:
                box = LayoutBox(BoxType.LINE,
                                parent,
                                html_parser.StyledNode(None, child.parser.cascade_rules([], child.node.style_rules), []),
                                child.parser)
                box.children = [child]
                child.parent = box
                index = parent.children.index(child)
                parent.children[index] = box
                return box
            elif parent.box_type == BoxType.LINE:
                parent.children.append(child)
                index = child.parent.children.index(child)
                del child.parent.children[index]
                child.parent = parent
                return parent
            child = parent
            parent = parent.parent

    def calculate_inline_position(self, containing_block: Dimensions):
        box = self.find_or_create_line_box()
        print(box)

    def layout_block_children(self):
        prev_dimensions = None
        for child in self.children:
            child.layout(self.dimensions, prev_dimensions)
            prev_dimensions = child.dimensions
            self.dimensions.content.height += child.dimensions.margin_box.height

    def layout_inline_children(self):
        for child in self.children:
            child.layout(self.dimensions, None)
            if child.dimensions.margin_box.height > self.dimensions.content.height:
                self.dimensions.content.height = child.dimensions.margin_box.height
            self.dimensions.content.width += child.dimensions.margin_box.width

    def calculate_block_height(self):
        height = self.get_single_int_value("height")
        if height != "auto":
            self.dimensions.content.height = height


def build_layout_box(style_node, parser, parent=None) -> typing.Union[None, LayoutBox]:
    root_layout = style_node.display()
    if root_layout == html_parser.Display.INLINE:
        root_layout = BoxType.INLINE
    elif root_layout == html_parser.Display.BLOCK:
        root_layout = BoxType.BLOCK
    elif root_layout == html_parser.Display.NONE:
        return None
    root = LayoutBox(root_layout, parent, style_node, parser)

    has_block_children = any(c.display() == html_parser.Display.BLOCK for c in style_node.children)
    for child in style_node.children:
        display = child.display()
        if display == html_parser.Display.BLOCK:
            root.children.append(build_layout_box(child, parser, root))
        elif display == html_parser.Display.INLINE:
            container = root
            if has_block_children:
                container = root.get_inline_container()
            container.children.append(build_layout_box(child, parser, root))

    return root
