"""The command line.

    python -m delivery_desk email <working note>

Exit codes for `email`: 0 email written · 1 sections still empty · 2 tool error.
"""

import argparse
import sys
from pathlib import Path

from .manager_email import build_email, save_email
from .note import NoteError, empty_sections, read_sections


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = _parser().parse_args(argv)
    return _email(Path(args.note))


def _parser():
    parser = argparse.ArgumentParser(prog="delivery-desk",
                                     description="Turn a filled-in working note into an email for your manager.")
    commands = parser.add_subparsers(dest="command", required=True)
    email = commands.add_parser("email", help="write the manager email from a filled-in working note")
    email.add_argument("note", help="the working note (incident-note.md in the report folder)")
    return parser


def _email(note):
    try:
        text = note.read_text(encoding="utf-8-sig")  # "-sig": Notepad may add an invisible marker at the start
    except FileNotFoundError:
        return _error(f"working note {note} not found")
    except UnicodeDecodeError:
        return _error(f"{note} isn't saved as UTF-8 text; save it as UTF-8 and try again")
    except OSError as error:
        return _error(f"can't read {note}: {error}")
    try:
        sections = read_sections(text)
    except NoteError as error:
        return _error(f"{note.name}: {error}")

    missing = empty_sections(sections)
    if missing:
        print(f"No email written. Still to fill in: {', '.join(missing)}.\n"
              f"Write under those headings in {note}, then run this again.")
        return 1
    path = save_email(note.parent, build_email(sections))
    print(f"Manager email written: {path}\nIt has not been sent: copy it into an email yourself.")
    return 0


def _error(message):
    print(f"delivery-desk: error: {message}", file=sys.stderr)
    return 2
