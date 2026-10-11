"""The working note: my record of one incident, as plain text (Markdown) I can edit anywhere.

Built from a manifest-doctor report when a check finds problems. Two sections are filled in
from the check; five are left for me. Nothing under "For me only" is ever put in the email.
"""

import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from .files import write_new

FROM_CHECK = ("Which delivery", "The problem")
MINE = ("When it happened", "How it happened", "How we intend to fix it", "Most plausible way to do it",
        "Subject summary")
PRIVATE = ("Probable causes from the check (not verdicts)", "ai-triage summary")
PRIVATE_DIVIDER = "# For me only: nothing below this line is put in the email"
PLACEHOLDER = "(fill in"
HINTS = {"Subject summary": "(fill in: one line for the email subject, written once you know what went wrong)"}
MAX_PATHS = 10  # enough to start investigating; the full list stays in report.json


class NoteError(Exception):
    """The note can't be read safely, e.g. a heading was renamed or written twice."""


def build_note(report, triage=None, triage_file="triage.md"):
    """`triage` is ai-triage's triage.json record, a reason it's unavailable (text), or None if not run."""
    header = report["header"]
    lines = [f"# Incident note: {_data(_last_part(header['tree']))}", "",
             'How to use: write under each "(fill in)" heading, in any text editor, whenever you like.',
             "Don't rename the headings. When all five are filled in, run:",
             '    python -m delivery_desk email "<path to this file>"',
             "Or add --ask to that command to be asked for the empty sections instead.", "",
             "## Which delivery", _which_delivery(header), "",
             "## The problem", *_problem(report), ""]
    for heading in MINE:
        lines += [f"## {heading}", HINTS.get(heading, "(fill in)"), ""]
    lines += [PRIVATE_DIVIDER, "",
              f"## {PRIVATE[0]}", *_causes(report["causes"]), "",
              f"## {PRIVATE[1]}", *_triage(triage, triage_file)]
    return "\n".join(lines) + "\n"


def write_note(folder, text):
    return write_new(Path(folder), "incident-note", ".md", text)


KNOWN = {f"## {h}": h for h in FROM_CHECK + MINE + PRIVATE}


def read_sections(text):
    """Split a note into {heading: text}. Only exact, known headings count, so text that merely
    looks like a heading (a quoted AI line, an escaped file name) can't start a section."""
    sections, current = {}, None
    for line in text.splitlines():
        if _is_boundary(line):
            current = KNOWN.get(line.rstrip())
            if current in sections:
                raise NoteError(f'the heading "## {current}" appears more than once; keep only one')
            if current is not None:
                sections[current] = []
        elif current is not None:
            sections[current].append(line)
    missing = [h for h in FROM_CHECK + MINE if h not in sections]
    if missing:
        raise NoteError("heading missing or renamed: " + ", ".join(f'"## {h}"' for h in missing)
                        + ". Put it back exactly as it was.")
    return {heading: _trim(lines) for heading, lines in sections.items()}


def empty_sections(sections):
    """My sections still blank or still showing the "(fill in" placeholder, in note order."""
    return [h for h in MINE if not sections[h].strip() or sections[h].strip().startswith(PLACEHOLDER)]


def fill_section(text, heading, answer):
    """Put an answer under one of my sections, only if it's still empty. Everything else in the
    note, including anything I've written, comes back exactly as it was."""
    for line in answer.splitlines():
        if _is_boundary(line):
            raise NoteError(f'the line "{line.strip()}" looks like a heading in the note; please reword it')
    if heading not in empty_sections(read_sections(text)):
        raise NoteError(f'"{heading}" already has text in the note')
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.rstrip() == f"## {heading}")
    end = start + 1
    while end < len(lines) and not _is_boundary(lines[end]):
        end += 1
    return "\n".join(lines[:start + 1] + answer.splitlines() + [""] + lines[end:]) + "\n"


def _is_boundary(line):
    """A line that starts a section, or the start of the private part."""
    return line.rstrip() in KNOWN or line.startswith("# For me only")


# --- Building the parts from the report -----------------------------------------------------------------

def _which_delivery(header):
    manifests = " and ".join(_data(m["path"]) for m in header.get("manifests") or []) or "no manifest"
    return f"{_data(header['tree'])}, checked against {manifests} at {_when(header.get('run_at'))}"


def _problem(report):
    counts = report["header"]["counts"]
    lines = [f"{_data(report['header']['result'])}: {_plural(counts.get('ERROR', 0), 'error')}, "
             f"{_plural(counts.get('WARNING', 0), 'warning')}."]
    tally = Counter((f["severity"], f["code"]) for f in report["findings"] if f["severity"] in ("ERROR", "WARNING"))
    # Errors first, then the most frequent; INFO isn't a problem, so it stays in the report.
    for (severity, code), n in sorted(tally.items(), key=lambda t: (t[0][0] != "ERROR", -t[1], t[0][1])):
        lines.append(f"- {_data(code)} ({severity.lower()}): {n} found")
    return lines


def _causes(causes):
    if not causes:
        return ["None suggested by the check."]
    lines = []
    for cause in causes:
        lines.append(f"- {_data(cause['severity'])}, {_data(cause['code'])}: {_data(cause['summary'])}")
        paths = cause.get("paths") or []
        lines += [f"  - {_code(p)}" for p in paths[:MAX_PATHS]]
        if len(paths) > MAX_PATHS:
            lines.append(f"  - and {len(paths) - MAX_PATHS} more (see report.json)")
    return lines


def _triage(triage, triage_file):
    if triage is None:
        return ["Not available (ai-triage was not run)."]
    if isinstance(triage, str):
        return [f"Not available ({_data(triage)})."]
    status = triage.get("status")
    if status == "OK":
        first = f"OK: written by AI ({_data(triage.get('model'))}) and passed every check against the report."
    elif status == "FALLBACK":
        first = (f"FALLBACK: written by code from the report; the AI was not used "
                 f"({_data(triage.get('fallback_reason'))}).")
    else:
        # A draft that failed its checks isn't worth a glance under pressure, so it isn't shown.
        return ["NEEDS HUMAN: the AI draft failed its checks against the report, so it isn't shown. "
                "Read the report itself.", "", f"Full triage note: {_data(triage_file)}"]
    # Quoted line by line: no line of the summary can ever look like one of my headings.
    summary = [f"> {line}" for line in str(triage["draft"]["summary"]).splitlines()]
    return [first, "", *summary, "", f"Full triage note: {_data(triage_file)}"]


# --- Small helpers ----------------------------------------------------------------------------------------

def _data(text):
    """Text from the report is data. Line breaks and other control characters are shown, not
    obeyed, so a file name can never start a new line that looks like one of my headings."""
    return "".join(repr(c)[1:-1] if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c for c in str(text))


def _code(text):
    """Markdown code formatting, with a fence longer than any run of backticks inside the name."""
    text = _data(text)
    fence = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _last_part(path):
    return re.split(r"[\\/]", str(path).rstrip("\\/"))[-1] or str(path)


def _when(run_at):
    try:
        return datetime.fromisoformat(run_at).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return _data(run_at or "an unknown time")


def _plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _trim(lines):
    """Drop blank lines around a section; everything inside it is kept exactly as written."""
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return "\n".join(lines)
