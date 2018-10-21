import html_parser

if __name__ == "__main__":
    html = """
    <p>
      Hello!
      How are you?
    </p>
    """

    parser = html_parser.Parser(html)
    parser.parse_html()
