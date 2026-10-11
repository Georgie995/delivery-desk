"""The command line.

    python -m delivery_desk check <delivery folder> --manifest FILE [other manifest-doctor options]
    python -m delivery_desk email <working note> [--ask]

Exit codes for `check`: delivery-ops-hub's own (0 clean or warnings · 1 problems found, note
written · 2 not checked · 3 alert not delivered, or settings wrong).
Exit codes for `email`: 0 email written · 1 sections still empty · 2 tool error.
"""

import argparse
import sys
from pathlib import Path

from .desk import run_check
from .files import replace_safely
from .manager_email import build_email, save_email
from .note import MINE, NoteError, empty_sections, fill_section, read_sections
from .settings import SettingsError, load_settings

# Shown when asking, so the meaning of each section is clear without opening the design.
PROMPTS = {
    "When it happened": "when the problem occurred, not when the check ran",
    "How it happened": "the confirmed cause, once you've investigated",
    "How we intend to fix it": "what will be done",
    "Most plausible way to do it": "how best to do it",
    "Subject summary": "one line for the email subject",
}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = _parser().parse_args(argv)
    if args.command == "check":
        try:
            settings = load_settings(args.config)
        except SettingsError as error:
            print(f"delivery-desk: error: {error}", file=sys.stderr)
            return 3
        return run_check(settings, args.tree, args.doctor_args)
    return _email(Path(args.note), args.ask)


def _parser():
    parser = argparse.ArgumentParser(prog="delivery-desk",
                                     description="Check a delivery, start a working note when there are problems, "
                                                 "and turn the filled-in note into an email for your manager.")
    parser.add_argument("--config", default="delivery-desk.toml", help="settings file (default: %(default)s)")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a delivery: one alert, ai-triage and, if problems are "
                                              "found, a working note")
    check.add_argument("tree", help="the delivery folder to check")
    check.add_argument("doctor_args", nargs=argparse.REMAINDER,
                       help="passed unchanged to manifest-doctor, e.g. --manifest FILE")
    email = commands.add_parser("email", help="write the manager email from a filled-in working note")
    email.add_argument("note", help="the working note (incident-note.md in the report folder)")
    email.add_argument("--ask", action="store_true", help="ask for the empty sections first, saving each answer")
    return parser


def _email(note, ask):
    try:
        if ask:
            _ask_for_empty_sections(note)
        sections = read_sections(_read(note))
    except NoteError as error:
        return _error(f"{note.name}: {error}")
    except FileNotFoundError:
        return _error(f"working note {note} not found")
    except UnicodeDecodeError:
        return _error(f"{note} isn't saved as UTF-8 text; save it as UTF-8 and try again")
    except OSError as error:
        return _error(f"can't read or save {note}: {error}")

    missing = empty_sections(sections)
    if missing:
        print(f"No email written. Still to fill in: {', '.join(missing)}.\n"
              f"Write under those headings in {note}, or run this again with --ask.")
        return 1
    path = save_email(note.parent, build_email(sections))
    print(f"Manager email written: {path}\nIt has not been sent: copy it into an email yourself.")
    return 0


def _ask_for_empty_sections(note):
    """Ask only for empty sections. The note is read again before every question and every save,
    so anything written in a text editor meanwhile is seen and never overwritten."""
    print("Answering into the note. Type your answer; an empty line finishes it.\n"
          "Press Enter straight away to skip a section. Each answer is saved as soon as you finish it.\n"
          "If the note is open in a text editor, reload it there afterwards.")
    try:
        for heading in MINE:
            if heading not in empty_sections(read_sections(_read(note))):
                continue
            while True:
                answer = _read_answer(heading)
                if answer is None:
                    print(f"Skipped: {heading}")
                    break
                text = _read(note)
                if heading not in empty_sections(read_sections(text)):
                    print(f"Kept what's already written under {heading} in the note; your typed answer wasn't used.")
                    break
                try:
                    replace_safely(note, fill_section(text, heading, answer))
                except NoteError as error:
                    if "looks like a heading" not in str(error):
                        raise
                    print(f"Not saved: {error}.")
                    continue  # ask the same question again
                print(f"Saved: {heading}")
                break
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. The answers you finished are saved in the note.")


def _read_answer(heading):
    """Lines until an empty one. The subject is one line. Enter straight away skips."""
    one_line = heading == "Subject summary"
    print(f"\n{heading} ({PROMPTS[heading]}" + ("; Enter finishes it" if one_line else "") + "):")
    lines = []
    while True:
        line = input("> ")
        if not line.strip():
            break
        lines.append(line)
        if one_line:
            break
    return "\n".join(lines) or None


def _read(note):
    return note.read_text(encoding="utf-8-sig")  # "-sig": Notepad may add an invisible marker at the start


def _error(message):
    print(f"delivery-desk: error: {message}", file=sys.stderr)
    return 2
