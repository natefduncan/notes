import re
import datetime as dt
import os
import subprocess
import argparse
from pathlib import Path
import difflib
import json
import pathlib

from notes import get_notes_files, parse_notes_files, Note
from graph import Graph

TODO_RE = re.compile(r"TODO:(.+)|- \[ \](.+)")
DUE_DATE_RE = re.compile(r"\((\d\d-\d\d-\d\d)\)")
NOTECARD_RE = re.compile(r"CARD\((.+)\):\n- (.+)\n- (.+)")

CONFIG_PATH = pathlib.Path(__file__).parent.resolve() / "config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        config = json.loads(f.read())
    return config


def write_config(config):
    with open(CONFIG_PATH, "w") as f:
        f.write(json.dumps(config))


def generate_node_index(graph: Graph, node: Note, level: int) -> str:
    output = ("  " * level) + f"- [{node.title.replace('# ', '')}]({node.path})\n"
    if not graph.children(node):
        return output
    else:
        children = sorted(graph.children(node), key=lambda x: x.title)
        for child in children:
            output += generate_node_index(graph, child, level + 1)
    return output


def generate_index(graph: Graph):
    index = ""
    nodes = sorted(graph.dfs(), key=lambda x: x.title)
    # List of tags
    tags = []
    for e in graph.nodes:
        tags += e.tags
    tags = sorted(list(set(tags)))
    tagless = list()
    for tag in tags:
        index += f"# {tag.replace('#', '')}\n"
        for node in nodes:
            if node.parent:
                continue
            if node.tags:
                if tag in node.tags:
                    index += generate_node_index(graph, node, 0)
            else:
                tagless.append(f"- [{node.title.replace('# ', '')}]({node.path})\n")
        index += "\n"
    index += "NO TAG\n" + "".join(list(set(tagless)))
    return index


def update_index(config):
    os.chdir(Path(config["path"]).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    graph = Graph(parsed)
    index = generate_index(graph)
    path = (Path(config["path"]) / "index.md").expanduser()
    with open(path, "w") as f:
        f.write(index)

def update_notecard(config, anki_format):
    os.chdir(Path(config["path"]).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    decks = {}
    for p in parsed:
        notecards = re.findall(NOTECARD_RE, p.body)
        if notecards:
            for notecard in notecards:
                deck, front, back = notecard
                if deck in decks:
                    decks[deck].append((front, back))
                else:
                    decks[deck] = [(front, back)]
    output = ""
    if anki_format:
        output += "#separator:Comma\n"
        output += "#html:false\n"
        output += "#columns:front,back,deck,notetype\n"
        output += "#deck column:3\n"
        output += "#notetype column:4\n"
    for deck, cards in decks.items():
        if anki_format:
            for front, back in cards:
                deck_esc = deck.strip().replace("\"", "\"\"")
                front_esc = front.strip().replace("\"", "\"\"")
                back_esc = back.strip().replace("\"", "\"\"")
                output += f"\"{front_esc}\",\"{back_esc}\",\"{deck_esc}\",Basic\n"
        else:
            output += f"# {deck}\n\n"
            for front, back in cards:
                output += f"- {front}\n- {back}\n\n"
    outfile = "notecard.md" if not anki_format else "notecard.txt"
    path = (Path(config["path"]) / outfile).expanduser()
    with open(path, "w") as f:
        f.write(output)

def update_todo(sort_date: bool, config):
    os.chdir(Path(config["path"]).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    items = {}
    for p in parsed:
        todos = re.findall(TODO_RE, p.body)
        if todos:
            items[p] = []
            for t in todos:
                task = t[0] if t[0] else t[1]  # Two different types of todo formats
                items[p].append(task)
    output = ""
    if sort_date:
        today = dt.datetime.today()
        all_tasks = [i for j in items.values() for i in j]
        dated_tasks = [i for i in all_tasks if re.search(DUE_DATE_RE, i)]
        dates = [
            dt.datetime.strptime(re.search(DUE_DATE_RE, i).group(1), "%y-%m-%d")
            for i in dated_tasks
        ]
        no_dated_tasks = [i for i in all_tasks if not re.search(DUE_DATE_RE, i)]
        dated_tasks_dict = {k: [] for k in list(set(dates))}
        for date, task in zip(dates, dated_tasks):
            dated_tasks_dict[date].append(task)

        sorted_dates = sorted(dated_tasks_dict.keys())
        for date in sorted_dates:
            days = (date - today).days
            formatted_date = dt.datetime.strftime(date, "%A, %b %d %Y")
            output += f"## {formatted_date}, {days} day(s)\n"
            for t in dated_tasks_dict[date]:
                formatted_t = re.sub(DUE_DATE_RE, "", t).strip()
                note = list(items.keys())[
                    [t in i for i in list(items.values())].index(True)
                ]  # This is ugly
                output += f"- [ ] {formatted_t} ([{note.title}]({note.path}))\n"
            output += "\n"

        output += "## No Date\n"
        for t in no_dated_tasks:
            output += f"- [ ] {t}\n"
    else:
        for p, tasks in items.items():
            output += f"[{p.title}]({p.path})\n\n"
            for t in tasks:
                output += f"- [ ] {t}\n"
            output += "\n"
    path = (Path(config["path"]) / "todo.md").expanduser()
    with open(path, "w") as f:
        f.write(output)


def find_note_by_title(title: str, config) -> Note:
    os.chdir(Path(config["path"]).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    scores = [
        difflib.SequenceMatcher(None, args.title, i.title, False).ratio()
        for i in parsed
    ]
    max_idx = scores.index(max(scores))
    return parsed[max_idx]


def main(args):
    if args.command == "set":
        config = load_config()
        config[args.key] = args.value
        write_config(config)

    else:
        config = load_config()
        if "path" not in config:
            raise ValueError("Path must be set in config file!")

        elif args.command == "new":
            if args.path:
                os.chdir(Path(args.path).expanduser())
            else:
                os.chdir(Path(config["path"]).expanduser())
            _id = Note.get_new_id(config["path"])
            path = f"{_id}.md"
            body = args.body.read() if args.body else ""
            title = args.title if args.title else "New Note"
            template = args.template if args.template else None
            kind = args.kind if args.kind else "note"
            tags = ["#" + i.strip() for i in args.tags.split(",")] if args.tags else []
            new_note = Note(
                path=path, _id=_id, title=title, tags=tags, template=template, body=body, kind=kind, 
            )
            if args.noeditor:
                with open(path, "w") as f:
                    f.write(new_note.to_str())
            else:
                subprocess.run(
                    args=["nvim", "-", "-c", f":file {path}"],
                    cwd=Path(config["path"]).expanduser(),
                    input=bytes(new_note.to_str(), "utf-8"),
                )

        elif args.command == "index":
            update_index(config)
            subprocess.run(
                args=["nvim", "index.md"], cwd=Path(config["path"]).expanduser()
            )

        elif args.command == "todo":
            update_todo(args.sort_date, config)
            subprocess.run(
                args=["nvim", "todo.md"], cwd=Path(config["path"]).expanduser()
            )

        elif args.command == "notecard":
            update_notecard(config, args.anki_format)
            outfile = "notecard.md" if not args.anki_format else "notecard.txt"
            subprocess.run(
                args=["nvim", outfile], cwd=Path(config["path"]).expanduser()
            )

        elif args.command == "search":
            subprocess.run(
                args=["nvim", "-", "-c", r':call feedkeys("\<c-f>")'],
                cwd=Path(config["path"]).expanduser(),
            )

        elif args.command == "graph":
            os.chdir(Path(config["path"]).expanduser())
            files = get_notes_files(["."])
            parsed = parse_notes_files(files)
            graph = Graph(parsed)
            print(graph.as_dot(orient_tag=args.orient_tag))

        elif args.command == "find":
            note = find_note_by_title(args.title, config)
            subprocess.run(
                args=["nvim", note.path], cwd=Path(config["path"]).expanduser()
            )

        elif args.command == "append":
            note = find_note_by_title(args.title, config)
            body = args.file.read() if args.file else args.content
            note.body += "\n" + body
            with open(note.path, "w") as f:
                f.write(note.to_str())

        elif args.command == "last":
            p = subprocess.run(
                args=["nvim", "--headless", "-c", ":ol", "-c", ":q"],
                cwd=Path(config["path"]).expanduser(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            all_files = p.stdout.decode("utf-8").split("\n")
            last_file = all_files[0].split(":")[1].strip()
            subprocess.run(
                args=["nvim", last_file], cwd=Path(config["path"]).expanduser()
            )

        elif args.command == "cat":
            note = find_note_by_title(args.title, config)
            print(note.body)

        elif args.command == "templates":
            note_path = Path(config["path"]).expanduser()
            files = [each for each in os.listdir(note_path) if each.endswith('.tpl')]
            for f in files:
                print(f)

        elif args.command == "replace-section":
            note = find_note_by_title(args.title, config)
            if not args.replace_with:
                raise ValueError("Set replace with -r")
            replace_with = args.replace_with.read() 
            note.replace_section(args.section, replace_with)
            with open(note.path, "w") as f:
                f.write(note.to_str())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="notes", description="notes system")
    subparsers = parser.add_subparsers(dest="command", help="sub-command help")

    # Set
    s = subparsers.add_parser("set", help="Set config key/value")
    s.add_argument("key", help="Set config key")
    s.add_argument("value", help="Set config value")

    # New (import) note
    new_note = subparsers.add_parser("new", help="Create new note")
    new_note.add_argument("-t", "--title", type=str, help="note title")
    new_note.add_argument(
        "-b",
        "--body",
        type=argparse.FileType("r"),
        help="note body; can pipe from stdin or input from a file",
        nargs="?",
    )
    new_note.add_argument("-g", "--tags", type=str, help="comma separated list of tags")
    new_note.add_argument(
        "-f", "--template", type=str, help="new note from existing template"
    )
    new_note.add_argument(
        "-n",
        "--noeditor",
        action="store_true",
        help="Save note instead of opening editor",
    )
    new_note.add_argument(
        "-k",
        "--kind",
        type=str, 
        help="note type; default to 'note'",
    )
    new_note.add_argument("-p", "--path", type=str, help="overwite saved notes path")
    
    # Index
    subparsers.add_parser("index", help="Open index file")

    # todo
    todo = subparsers.add_parser("todo", help="open todo file")
    todo.add_argument("-d", "--sort-date", action="store_true", help="sort by due date")

    # notecard
    notecard = subparsers.add_parser("notecard", help="open notecard file")
    notecard.add_argument("-a", "--anki-format", action="store_true", help="save notecards in format that can be uploaded to Anki")

    # Search
    subparsers.add_parser("search", help="Search note files")

    # Graph
    graph = subparsers.add_parser("graph", help="visualize note files")
    graph.add_argument(
        "-t", "--orient-tag", action="store_true", help="Orient graph around tags"
    )

    # Find
    find = subparsers.add_parser(
        "find", help="Find note with most similar title and open"
    )
    find.add_argument("title", type=str, help="note title")

    # Append
    append = subparsers.add_parser("append", help="Add content to end of note body")
    append.add_argument("title", type=str, help="note title")
    append.add_argument(
        "-f",
        "--file",
        type=argparse.FileType("r"),
        help="note body; can pipe from stdin or input from a file",
        nargs="?",
    )
    append.add_argument(
        "-c", "--content", type=str, help="content to add to end of body", nargs="?"
    )

    # Last
    last = subparsers.add_parser("last", help="Open up last file")

    # Cat
    cat = subparsers.add_parser("cat", help="Cat note body to stdout")
    cat.add_argument("title", type=str, help="note title")

    # Templates
    templates = subparsers.add_parser("templates", help="List available note templates")
    # Replace Section 
    replace_section = subparsers.add_parser("replace-section", help="Replace content of a note section")
    replace_section.add_argument("title", type=str, help="note title")
    replace_section.add_argument("section", type=str, help="note section")
    replace_section.add_argument(
        "-r",
        "--replace-with",
        type=argparse.FileType("r"),
        help="text to replace section; can pipe from stdin or input from a file",
        nargs="?",
    )




    args = parser.parse_args()
    main(args)
