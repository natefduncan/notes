from typing import NamedTuple
import re

ID_HEADER_RE = r"id: (.+)\n"
TAG_HEADER_RE =r'tags: (.+)\n'
DATE_HEADER_RE = r'date: \d{2}-\d{2}-\d{2}\n'
PARENT_HEADER_RE = r"parent: \[.+\]\((.+)\)\n"
TITLE_RE = r"# (.+)\n"
LINK_RE = r"\[.+\]\([^\(\)]+\)"

TOKENS = [
    ("FOOTER_LINE", r"----\n"), 
    ("HEADER_LINE", r"---\n"), 
    ("ID_HEADER", ID_HEADER_RE), 
    ("TAG_HEADER", TAG_HEADER_RE), 
    ("DATE_HEADER", DATE_HEADER_RE), 
    ("PARENT_HEADER", PARENT_HEADER_RE), 
    ("TITLE", TITLE_RE),
    ("LINK", LINK_RE), 
    ("CR", r"\n"), 
    ("LINE", r".+\n")
]

class Token(NamedTuple):
    kind: str
    value: str

def tokenize(content):
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in TOKENS)
    for mo in re.finditer(tok_regex, content):
        kind = mo.lastgroup
        value = mo.group()
        yield Token(kind, value)

if __name__=="__main__":
    with open("./literature/230609-2249.md", "r") as f:
        content = f.read()
    tokens = tokenize(content)
    for token in tokens:
        print(token)
