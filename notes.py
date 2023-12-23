from __future__ import annotations

import os
import re
from pathlib import Path
import typing
import datetime as dt
from dataclasses import dataclass, field

from tokens import tokenize

LINK_RE = re.compile(r"\[.+\]\([^\(\)]+\)")
TAG_RE = re.compile(r"(#[^ \n]+)")
ID_RE = re.compile(r"id: (.+)\n")
SECTION_RE = re.compile(r"## (.+)\n")
SECTION_BODY_RE = re.compile(r"(?:## .+)\n\n([\s\S]*?)\n\n(?=^##|---)")
KIND_RE = re.compile(r"kind: (.+)\n")
PARENT_RE = re.compile(r"parent: \[.+\]\((.+)\)\n")
DEFAULT_TEMPLATE = """---
id: %id
date: %date
tags: %tags
parent: %parent
kind: %kind
--- 

# %title

%body

----
%footer
"""


@dataclass
class Note:
    path: typing.Optional[str] = ""
    _id: str = ""
    kind: typing.Optional[str] = "note"
    date: dt.date = dt.date.today()
    tags: typing.List[str] = field(default_factory=list)
    parent: typing.Optional[Note] | typing.Optional[str] = None
    title: str = ""
    body: str = ""
    footer: str = ""
    template: typing.Optional[str] = None

    def __str__(self):
        return f"{self.title}"

    def __repr__(self):
        return str(self)

    def __hash__(self):
        return hash(self._id)

    def get_section_headers(self) -> list[str]:
        return re.findall(SECTION_RE, self.body)

    def replace_section(self, section: str, replace_with: str):
        section_body_re = rf"(?:## {section})\n\n([\s\S]*?)(?:\n\n)?(?=^##|---|\Z)"
        r = re.search(section_body_re, self.body, re.MULTILINE).span(1)
        self.body = self.body[:r[0]] + replace_with.strip() + self.body[r[1]:]

    def as_dot(self, orient_tag=False):
        output = ""
        _id = '"' + self._id.replace("-", "_") + '"'
        if orient_tag:
            output += f'{_id}[label="{self.title}"];\n'
            for tag in self.tags:
                output += f'"{tag}"[label="{tag}"];\n'
                output += f'"{tag}" -> {_id};\n'
            return output
        else:
            if self.parent:
                parent_id = '"' + self.parent._id.replace("-", "_") + '"'
                output += f'{_id}[label="{self.title}"];\n'
                output += f'{parent_id}[label="{self.parent.title}"];\n'
                output += f"{parent_id} -> {_id};\n"
                return output
            else:
                return None

    @staticmethod
    def get_new_id(path: str) -> str:
        files = get_notes_files([Path(path).expanduser()])
        now = dt.datetime.now()
        base_id = dt.datetime.strftime(now, "%y%m%d-%H%M")
        new_id = base_id
        sub_note = "abcdefghijklmnopqrstuvwxyz"
        sub_i = 0
        while True:
            if not any([new_id in i for i in files]):
                break
            new_id = base_id + sub_note[sub_i]
            sub_i += 1
        return new_id

    @classmethod
    def from_str(cls, string: str) -> Note:
        c = cls()
        tokens = tokenize(string)
        is_footer = False
        is_body = False
        for token in tokens:
            if token.kind == "ID_HEADER":
                c._id = re.search(ID_RE, token.value).group(1)
            elif token.kind == "TAG_HEADER":
                c.tags = re.findall(TAG_RE, token.value)
            elif token.kind == "DATE_HEADER":
                c.date = dt.datetime.strptime(token.value, "date: %y-%m-%d\n").date()
            elif token.kind == "PARENT_HEADER":
                parent = re.search(PARENT_RE, token.value)
                c.parent = None if not parent else parent.group(1)
            elif token.kind == "KIND_RE":
                c.kind = re.search(KIND_RE, token.value).group(1)
            elif token.kind == "TITLE":
                c.title = token.value.replace("# ", "").strip()
                is_body = True
            elif token.kind == "FOOTER_LINE":
                is_body = False
                is_footer = True
            else:
                if is_footer:
                    c.footer += token.value
                if is_body:
                    c.body += token.value
        c.footer = c.footer.strip()
        c.body = c.body.strip()
        return c

    @classmethod
    def from_file(cls, file: str) -> Note:
        with open(file, "r") as f:
            content = f.read()
        note = cls.from_str(content)
        note.path = file
        return note

    def get_links(self):
        return re.findall(LINK_RE, self.body)

    def to_str(self) -> str:
        date = self.date.strftime("%y-%m-%d")
        tags = " ".join(self.tags)
        parent = "" if not self.parent else f"[{self.parent.title}]({self.parent.path})"
        if self.template:
            with open(self.template, "r") as f:
                template = f.read()
        else:
            template = DEFAULT_TEMPLATE
        template_keys = {
            "%id": self._id,
            "%date": date,
            "%tags": tags,
            "%parent": parent,
            "%kind": self.kind, 
            "%title": self.title,
            "%body": self.body,
            "%footer": self.footer,
        }
        output = template
        for k, r in template_keys.items():
            output = output.replace(k, r)
        return output


def get_notes_files(folders: typing.List[str]) -> typing.List[str]:
    files = []
    for folder in folders:
        files += [
            os.path.join(dirpath, f)
            for (dirpath, dirnames, filenames) in os.walk(folder)
            for f in filenames
        ]
    files = [f for f in files if re.search(r"./\d{6}-\d{4}", f)]
    return files


def get_template_files(path: str) -> typing.List[str]:
    files = []
    files += [
        os.path.join(dirpath, f)
        for (dirpath, dirnames, filenames) in os.walk(path)
        for f in filenames
    ]
    files = [f for f in files if ".tpl" in f]
    return files


def parse_notes_files(files: typing.List[str]) -> typing.List[Note]:
    entries = [Note.from_file(i) for i in files]
    # Add parent entries
    for entry in entries:
        if entry.parent:
            parent = [i for i in entries if i._id == entry.parent][0]
            entry.parent = parent
    return entries


if __name__ == "__main__":
    files = get_notes_files(["literature", "permanent"])
    parsed = parse_notes_files(files)
    for f in parsed:
        print(f.get_links())
