import html_parser

if __name__ == "__main__":
    html = """
    aaa
    <div class="test a"><b style="color: blue;">Test</b><i>aaaaa</i></div>
    aa
    <style>
      div.test {
        font-size: 20px;
      }
    </style>
    """

    parser = html_parser.Parser(html)
    parser.parse_html()
