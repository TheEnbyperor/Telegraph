import html_parser

if __name__ == "__main__":
    html = """
    <p>
      <em>Hello!</em>
      How are you?
    </p>
    """

    parser = html_parser.Parser(html)
    parser.parse_html()
