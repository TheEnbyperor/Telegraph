import html_parser

if __name__ == "__main__":
    html = """
    aaa
    <div data-bla="test" class="test a">
        <b style="color: blue;">
            Test
            <p>aaaaa</p>
        </b>
    </div>
    aa
    <style>
      div[data-bla="test"] {
        font-size: 20px;
      }
    </style>
    """

    parser = html_parser.Parser(html)
    parser.parse_html()
