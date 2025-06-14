from bs4 import BeautifulSoup

def _remove_html_tags(text):
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()
