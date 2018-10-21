import functools
import typing
import tinycss
import cssselect
import enum
import html5_parser
import layout_builder
from lxml import etree
from tinycss import token_data

BASE_CSS = b"""
head, style, script {
  display: none;
}

article,
aside,
details,
div,
dt,
figcaption,
footer,
form,
header,
hgroup,
html,
main,
nav,
section,
summary {
  display: block;
}

body {
  display: block;
  margin: 8px 2px;
}

b {
  font-weight: bold;
}
"""

CSS_VALUE = tinycss.css21.TokenList
CSS_DEFINITIONS = typing.List[tinycss.css21.Declaration]
CSS_DEFINITION_MAPPING = typing.Mapping[str, tinycss.css21.Declaration]
CSS_RULE_MAPPING = typing.Mapping[str, tinycss.css21.TokenList]
CSS_RULES = typing.List[typing.Union[cssselect.Selector, CSS_DEFINITIONS]]


class CssProperty:
    def __init__(self, initial_value: token_data.Token, inherited=True):
        self.initial_value = token_data.TokenList([initial_value])
        self.inherited = inherited


def make_token(type, value, units=None, css=None):
    if css is None:
        css = value
    return token_data.Token(type, css, value, units, 0, 0)


CSS_PROPERTIES = {
    "colour": CssProperty(make_token("HASH", "#000")),

    "font-size": CssProperty(make_token("IDENT", "medium")),
    "font-style": CssProperty(make_token("IDENT", "medium")),
    "font-weight": CssProperty(make_token("IDENT", "normal")),

    "text-align": CssProperty(make_token("IDENT", "left")),
    "text-decoration": CssProperty(make_token("IDENT", "none"), False),
    "text-transform": CssProperty(make_token("IDENT", "none")),

    "display": CssProperty(make_token("IDENT", "inline"), False),
    "visibility": CssProperty(make_token("IDENT", "visible")),

    "height": CssProperty(make_token("IDENT", "auto"), False),
    "width": CssProperty(make_token("IDENT", "auto"), False),
    "max-height": CssProperty(make_token("IDENT", "none"), False),
    "max-width": CssProperty(make_token("IDENT", "none"), False),
    "min-height": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "min-width": CssProperty(make_token("INTEGER", 0, css="0"), False),

    "left": CssProperty(make_token("IDENT", "auto"), False),
    "right": CssProperty(make_token("IDENT", "auto"), False),
    "top": CssProperty(make_token("IDENT", "auto"), False),
    "bottom": CssProperty(make_token("IDENT", "auto"), False),

    "margin-left": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "margin-right": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "margin-top": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "margin-bottom": CssProperty(make_token("INTEGER", 0, css="0"), False),

    "padding-left": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "padding-right": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "padding-top": CssProperty(make_token("INTEGER", 0, css="0"), False),
    "padding-bottom": CssProperty(make_token("INTEGER", 0, css="0"), False),
}


@enum.unique
class Display(enum.Enum):
    NONE = enum.auto()
    INLINE = enum.auto()
    BLOCK = enum.auto()


class StyledNode:
    def __init__(self, node: etree.Element, style_rules: CSS_RULE_MAPPING, children: typing.List):
        self.node = node
        self.style_rules = style_rules
        self.children = children

    def __getitem__(self, item):
        return self.style_rules.get(item)

    def __repr__(self, level=0):
        ret = "\t" * level + f"<StyledNode {self.node} {self.style_rules} ["
        for child in self.children:
            ret += "\n" + child.__repr__(level + 1)
        ret += ("\n" + ("\t" * level) if len(self.children) >= 1 else "") + "]"
        return ret

    def display(self) -> Display:
        display = self["display"]
        if display is None:
            return Display.INLINE
        if len(display) != 1:
            return Display.INLINE
        display = display[0]
        if display.type != "IDENT":
            return Display.INLINE
        if display.value == "block":
            return Display.BLOCK
        elif display.value == "none":
            return Display.NONE
        return Display.INLINE


class Parser:
    def __init__(self, html):
        self.html = html
        self.css_parser = tinycss.make_parser('page3')
        self.css_translator = cssselect.HTMLTranslator()

        css_rules = self.css_parser.parse_stylesheet_bytes(BASE_CSS).rules
        self.css_rules = []
        self.parse_css_rules(css_rules)

    def parse_css_rules(self, rules: tinycss.css21.RuleSet):
        for rule in rules:
            if isinstance(rule, tinycss.css21.RuleSet):
                try:
                    selectors = cssselect.parse(rule.selector.as_css())
                except cssselect.parser.SelectorSyntaxError:
                    return
                for selector in selectors:
                    self.css_rules.append((selector, rule.declarations))

    def get_css_rules(self, node: etree.Element):
        if node.tag == "style":
            style = self.css_parser.parse_stylesheet_bytes(node.text.encode())
            self.parse_css_rules(style.rules)

        for child in node:
            self.get_css_rules(child)

    @staticmethod
    def sort_css_rules(rules: CSS_RULES) -> CSS_RULES:
        return sorted(rules, key=lambda x: x[0].specificity())

    def matches_selector(self, tree: etree.Element, node: etree.Element,
                         rule: typing.Tuple[cssselect.Selector, typing.List[tinycss.css21.Declaration]]) -> bool:
        if node in tree.xpath(self.css_translator.selector_to_xpath(rule[0])):
            return True
        return False

    @staticmethod
    def parse_spaced_rule(rule: token_data.TokenList) -> typing.List[token_data.Token]:
        out = [rule[0]]
        i = 1
        try:
            while rule[i].type == "S":
                out.append(rule[i + 1])
                i += 2
        except IndexError:
            return out

    def expand_rules(self, rules: CSS_DEFINITION_MAPPING) -> CSS_DEFINITION_MAPPING:
        out = {}
        for definition, value in rules.items():
            if definition == f"margin" or definition == "padding":
                data = self.parse_spaced_rule(value.value)
                if len(data) == 1:
                    out[f"{definition}-top"] = tinycss.css21. \
                        Declaration(f"{definition}-top", token_data.TokenList(data), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-bottom"] = tinycss.css21. \
                        Declaration(f"{definition}-bottom", token_data.TokenList(data), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-left"] = tinycss.css21. \
                        Declaration(f"{definition}-left", token_data.TokenList(data), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-right"] = tinycss.css21. \
                        Declaration(f"{definition}-right", token_data.TokenList(data), value.priority, value.line,
                                    value.column)
                elif len(data) == 2:
                    out[f"{definition}-top"] = tinycss.css21. \
                        Declaration(f"{definition}-top", token_data.TokenList([data[0]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-bottom"] = tinycss.css21. \
                        Declaration(f"{definition}-bottom", token_data.TokenList([data[0]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-left"] = tinycss.css21. \
                        Declaration(f"{definition}-left", token_data.TokenList([data[1]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-right"] = tinycss.css21. \
                        Declaration(f"{definition}-right", token_data.TokenList([data[1]]), value.priority, value.line,
                                    value.column)
                elif len(data) == 3:
                    out[f"{definition}-top"] = tinycss.css21. \
                        Declaration(f"{definition}-top", token_data.TokenList([data[0]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-bottom"] = tinycss.css21. \
                        Declaration(f"{definition}-bottom", token_data.TokenList([data[2]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-left"] = tinycss.css21. \
                        Declaration(f"{definition}-left", token_data.TokenList([data[1]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-right"] = tinycss.css21. \
                        Declaration(f"{definition}-right", token_data.TokenList([data[1]]), value.priority, value.line,
                                    value.column)
                elif len(data) == 3:
                    out[f"{definition}-top"] = tinycss.css21. \
                        Declaration(f"{definition}-top", token_data.TokenList([data[0]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-bottom"] = tinycss.css21. \
                        Declaration(f"{definition}-bottom", token_data.TokenList([data[2]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-left"] = tinycss.css21. \
                        Declaration(f"{definition}-left", token_data.TokenList([data[3]]), value.priority, value.line,
                                    value.column)
                    out[f"{definition}-right"] = tinycss.css21. \
                        Declaration(f"{definition}-right", token_data.TokenList([data[1]]), value.priority, value.line,
                                    value.column)
            else:
                out[definition] = value
        return out

    def cascade_rules(self, elm_definitions: CSS_DEFINITIONS,
                      prev_definitons: CSS_DEFINITIONS) -> CSS_DEFINITIONS:
        out = {}
        for definition, value in CSS_PROPERTIES.items():
            out[definition] = tinycss.css21.Declaration(definition, value.initial_value, None, 0, 0)
        for definition in prev_definitons:
            if out.get(definition.name) is not None:
                if out[definition.name].priority == "important" and definition.priority != "important":
                    continue
            if CSS_PROPERTIES.get(definition.name) is not None and CSS_PROPERTIES[definition.name].inherited:
                out[definition.name] = definition
        for definition in elm_definitions:
            if out.get(definition.name) is not None:
                if out[definition.name].priority == "important" and definition.priority != "important":
                    continue
            out[definition.name] = definition

        for definition, value in out.items():
            if value.value.as_css() == "inherit":
                prev_value = next((x for x in prev_definitons if x.name == definition), None)
                if prev_value is None:
                    out[definition] = tinycss.css21.Declaration(definition, CSS_PROPERTIES[definition].initial_value,
                                                                None, 0, 0)
                else:
                    out[definition] = prev_value
        for definition, value in out.items():
            if value.value.as_css() == "initial":
                out[definition] = tinycss.css21.Declaration(definition,
                                                            CSS_PROPERTIES[definition].initial_value, None, 0, 0)

        out = self.expand_rules(out)
        return [v for _, v in out.items()]

    def make_styled_tree(self, node: etree.Element, tree: etree.Element, prev_rules: CSS_DEFINITIONS):
        element_rules = []
        if node.attrib.get("style") is not None:
            style = self.css_parser.parse_style_attr(node.attrib["style"])
            element_rules.extend(style[0])

        own_rules = []
        for rule in self.css_rules:
            if self.matches_selector(tree, node, rule):
                own_rules.append(rule)
        own_rules = functools.reduce(lambda a, b: a + b, map(lambda r: r[1], self.sort_css_rules(own_rules)), [])
        own_rules.extend(element_rules)

        own_rules = self.cascade_rules(own_rules, prev_rules)
        rule_definitions = {v.name: v.value for v in own_rules}

        children = []
        for child in node:
            children.append(self.make_styled_tree(child, tree, own_rules))

        return StyledNode(node, rule_definitions, children)

    def parse_html(self):
        tree = html5_parser.parse(self.html)
        self.get_css_rules(tree)

        styled_tree = self.make_styled_tree(tree, tree, [])
        print(styled_tree)

        layout_tree = layout_builder.build_layout_box(styled_tree)
        print(layout_tree)