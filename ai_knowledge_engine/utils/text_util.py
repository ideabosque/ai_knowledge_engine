from bs4 import BeautifulSoup
import hashlib

def _remove_html_tags(text):
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()


def md5_string(text):
    text_bytes = text.encode('utf-8')
    md5_obj = hashlib.md5()
    md5_obj.update(text_bytes)
    md5_hex = md5_obj.hexdigest()
    return md5_hex
