import copy
import typing
import tinycss
import cssselect
import functools
from lxml import etree

BASE_CSS = b"""
b {
  font-weight: bold;
}
"""


class StyledNode:
    def __init__(self, node: etree.Element, style_rules: typing.List[tinycss.css21.Declaration], children: typing.List):
        self.node = node
        self.style_rules = style_rules
        self.children = children

    def __str__(self):
        children = ' '.join(map(str, self.children))
        return f"<StyledNode {self.node} {self.style_rules} [{children}]>"


class Parser:
    def __init__(self, html):
        self.html = html
        self.css_parser = tinycss.make_parser('page3')
        self.css_translator = cssselect.HTMLTranslator()

        self.current_rules = []

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

    def sort_css_rules(self):
        self.css_rules = sorted(self.css_rules, key=lambda x: x[0].specificity())

    def matches_selector(self, tree: etree.Element, node: etree.Element,
                         rule: typing.Tuple[cssselect.Selector, typing.List[tinycss.css21.Declaration]]) -> bool:
        if node in tree.xpath(self.css_translator.selector_to_xpath(rule[0])):
                return True
        return False

    def make_styled_tree(self, node: etree.Element, tree: etree.Element):
        old_rules = copy.copy(self.current_rules)

        element_rules = []
        if node.attrib.get("style") is not None:
            style = self.css_parser.parse_style_attr(node.attrib["style"])
            element_rules.extend(style[0])

        for rule in self.css_rules:
            if self.matches_selector(tree, node, rule):
                self.current_rules.extend(rule[1])

        element_rules = self.current_rules + element_rules

        children = []
        for child in node:
            children.append(self.make_styled_tree(child, tree))

        self.current_rules = old_rules

        return StyledNode(node, element_rules, children)

    def parse_html(self):
        tree = etree.HTML(self.html)
        self.get_css_rules(tree)
        self.sort_css_rules()

        print(self.css_rules)

        styled_tree = self.make_styled_tree(tree, tree)
        print(styled_tree)
