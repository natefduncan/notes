import click
import re
import datetime as dt
import os
import subprocess
import argparse
from pathlib import Path
import difflib
import json
from typing import Optional
import pathlib

from notes.notes import get_notes_files, parse_notes_files, Note
from notes.graph import Graph

TODO_RE = re.compile(r"TODO:(.+)|- \[ \](.+)")
DUE_DATE_RE = re.compile(r"\((\d\d-\d\d-\d\d)\)")
NOTECARD_RE = re.compile(r"CARD\((.+)\):\n- (.+)\n- (.+)")
CONFIG_PATH = Path(os.path.expanduser("~")) / ".config" / "notes" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def create_refs_folder(notes_path, note_id):
    os.makedirs(f"{notes_path}/refs", exist_ok=True)
    os.makedirs(f"{notes_path}/refs/{note_id}", exist_ok=True)

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


def update_index(notes_path: str):
    os.chdir(Path(notes_path).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    graph = Graph(parsed)
    index = generate_index(graph)
    path = (Path(notes_path) / "index.md").expanduser()
    with open(path, "w") as f:
        f.write(index)


def update_notecard(notes_path: str, anki_format: bool):
    os.chdir(Path(notes_path).expanduser())
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
                deck_esc = deck.strip().replace('"', '""')
                front_esc = front.strip().replace('"', '""')
                back_esc = back.strip().replace('"', '""')
                output += f'"{front_esc}","{back_esc}","{deck_esc}",Basic\n'
        else:
            output += f"# {deck}\n\n"
            for front, back in cards:
                output += f"- {front}\n- {back}\n\n"
    outfile = "notecard.md" if not anki_format else "notecard.txt"
    path = (Path(notes_path) / outfile).expanduser()
    with open(path, "w") as f:
        f.write(output)


def update_todo(sort_date: bool, notes_path: str):
    os.chdir(Path(notes_path).expanduser())
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
        dated_tasks_dict = {k: [] for k in list(dates)}
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
    path = (Path(notes_path) / "todo.md").expanduser()
    with open(path, "w") as f:
        f.write(output)


def find_note_by_title(title: str, notes_path: str) -> Note:
    os.chdir(Path(notes_path).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    scores = [
        difflib.SequenceMatcher(None, title, i.title, False).ratio() for i in parsed
    ]
    max_idx = scores.index(max(scores))
    return parsed[max_idx]


def get_notes_path(ctx: click.core.Context) -> str:
    if "path" not in ctx.obj["config"]:
        raise ValueError("Path must be set in config file!")
    else:
        return ctx.obj["config"]["path"]


@click.group()
@click.pass_context
def cli(ctx):
    config = load_config()
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command(short_help="Set note directory")
@click.argument("value", type=str)
def set_note_path(value: str):
    config = load_config()
    config["path"] = value
    write_config(config)


@cli.command(short_help="create new note")
@click.option("-t", "--title", type=str, help="note title")
@click.option(
    "-b",
    "--body",
    type=click.File("r"),
    help="note body; can pipe from stdin or input from a file",
)
@click.option("-g", "--tags", type=str, help="comma separated list of tags")
@click.option("-f", "--template", type=str, help="new note from existing template")
@click.option(
    "-n",
    "--noeditor",
    is_flag=True,
    help="Save note instead of opening editor",
)
@click.option(
    "-k",
    "--kind",
    type=str,
    help="note type; default to 'note'",
)
@click.option("-p", "--path", type=str, help="overwite saved notes path")
@click.option("-r", "--refs", is_flag=True, type=bool, help="create reference folder in ./refs for image files")
@click.pass_context
def new(
    ctx,
    title: Optional[str],
    body: Optional[click.File],
    tags: Optional[str],
    template: Optional[str],
    noeditor: Optional[bool],
    kind: Optional[str],
    path: Optional[str],
    refs: Optional[bool],
):
    notes_path = get_notes_path(ctx)
    if path:
        os.chdir(Path(path).expanduser())
    else:
        os.chdir(Path(notes_path).expanduser())
    _id = Note.get_new_id(notes_path)
    path = f"{_id}.md"
    body = body.read() if body else ""
    title = title if title else "New Note"
    template = template if template else None
    kind = kind if kind else "note"
    tags = ["#" + i.strip() for i in tags.split(",")] if tags else []
    new_note = Note(
        path=path,
        _id=_id,
        title=title,
        tags=tags,
        template=template,
        body=body,
        kind=kind,
    )
    if refs:
        create_refs_folder("refs", _id)
    if noeditor:
        with open(path, "w") as f:
            f.write(new_note.to_str())
    else:
        subprocess.run(
            ["nvim", "-", "-c", f":file {path}"],
            cwd=Path(notes_path).expanduser(),
            input=bytes(new_note.to_str(), "utf-8"),
        )


@cli.command(short_help="Open index file")
@click.pass_context
def index(ctx):
    notes_path = get_notes_path(ctx)
    update_index(notes_path)
    subprocess.run(["nvim", "index.md"], cwd=Path(notes_path).expanduser())


@cli.command(short_help="open todo file")
@click.option("-d", "--sort-date", is_flag=True, help="sort by due date")
@click.pass_context
def todo(ctx, sort_date: bool):
    notes_path = get_notes_path(ctx)
    update_todo(sort_date, notes_path)
    subprocess.run(args=["nvim", "todo.md"], cwd=Path(notes_path).expanduser())


@cli.command(short_help="create notecard file")
@click.option("-a", "--anki-format", is_flag=True, type=bool, help="anki format")
@click.pass_context
def notecard(ctx, anki_format: bool):
    notes_path = get_notes_path(ctx)
    update_notecard(notes_path, anki_format)
    outfile = "notecard.md" if not anki_format else "notecard.txt"
    subprocess.run(["nvim", outfile], cwd=Path(notes_path).expanduser())


@cli.command(short_help="Search note files")
@click.pass_context
def search(ctx):
    notes_path = get_notes_path(ctx)
    subprocess.run(
        args=[
            "nvim",
            "-",
            "-c",
            r':lua require("telescope.builtin").live_grep({glob_pattern={"!*refs/*", "!*scripts/*"}})',
        ],
        cwd=Path(notes_path).expanduser(),
    )


@cli.command(short_help="visualize note files")
@click.option(
    "-t", "--orient-tag", is_flag=True, type=bool, help="Orient graph around tags"
)
@click.pass_context
def graph(ctx, orient_tag: bool):
    notes_path = get_notes_path(ctx)
    os.chdir(Path(notes_path).expanduser())
    files = get_notes_files(["."])
    parsed = parse_notes_files(files)
    graph = Graph(parsed)
    click.echo(graph.as_dot(orient_tag=orient_tag))


@cli.command(short_help="Find note with most similar title and open")
@click.option("-r", "--refs", is_flag=True, type=bool, help="create reference folder in refs for image files")
@click.argument("title", type=str)
@click.pass_context
def find(ctx, title: str, refs: bool):
    notes_path = get_notes_path(ctx)
    note = find_note_by_title(title, notes_path)
    cwd = Path(notes_path).expanduser()
    if refs:
        create_refs_folder(cwd, note._id)
    subprocess.run(args=["nvim", note.path], cwd=cwd)


@cli.command(short_help="Add content to end of note body")
@click.argument("title", type=str)
@click.option(
    "-f",
    "--file",
    type=click.File("r"),
    help="note body; can pipe from stdin or input from a file",
)
@click.option("-c", "--content", type=str, help="content to add to end of body")
@click.pass_context
def append(ctx, title: str, file: Optional[click.File], content: Optional[str]):
    notes_path = get_notes_path(ctx)
    note = find_note_by_title(title, notes_path)
    body = file.read() if file else content
    note.body += "\n" + body
    with open(note.path, "w") as f:
        f.write(note.to_str())


@cli.command(short_help="Open up last file")
@click.pass_context
def last(ctx):
    notes_path = get_notes_path(ctx)
    p = subprocess.run(
        args=["nvim", "--headless", "-c", ":ol", "-c", ":q"],
        cwd=Path(notes_path).expanduser(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    all_files = p.stdout.decode("utf-8").split("\n")
    last_file = all_files[0].split(":")[1].strip()
    subprocess.run(args=["nvim", last_file], cwd=Path(notes_path).expanduser())


@cli.command(short_help="Cat note body to stdout")
@click.argument("title", type=str)
@click.pass_context
def cat(ctx, title: str):
    notes_path = get_notes_path(ctx)
    note = find_note_by_title(title, notes_path)
    click.echo(note.body)


@cli.command(short_help="List available note templates")
@click.pass_context
def templates(ctx):
    notes_path = get_notes_path(ctx)
    note_path = Path(notes_path).expanduser()
    files = [each for each in os.listdir(note_path) if each.endswith(".tpl")]
    for f in files:
        click.echo(f)


@cli.command(short_help="Replace content of a note section")
@click.argument("title", type=str)
@click.argument("section", type=str)
@click.option(
    "-r",
    "--replace-with",
    type=click.File("r"),
    help="text to replace section; can pipe from stdin or input from a file",
)
@click.pass_context
def replace_section(ctx, title: str, section: str, replace_with: click.File):
    notes_path = get_notes_path(ctx)
    note = find_note_by_title(title, notes_path)
    if not replace_with:
        raise ValueError("Set replace with -r")
    replace_with = replace_with.read()
    note.replace_section(section, replace_with)
    with open(note.path, "w") as f:
        f.write(note.to_str())


if __name__ == "__main__":
    cli()
