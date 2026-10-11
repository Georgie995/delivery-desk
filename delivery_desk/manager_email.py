"""The manager email: a subject line and six parts, built from my filled-in working note.

The tool only writes it to a file. Sending it is always my job.
"""

from pathlib import Path

from .files import write_new

# The order Georgi gave at the kickoff. "Subject summary" goes in the subject, not the body.
ORDER = ("The problem", "Which delivery", "When it happened", "How it happened", "How we intend to fix it",
         "Most plausible way to do it")


def build_email(sections):
    subject = " ".join(sections["Subject summary"].split())  # a subject line can't contain line breaks
    lines = [f"Subject: Delivery issue: {subject} (PROBLEMS FOUND)", ""]
    for heading in ORDER:
        lines += [f"{heading}:", sections[heading], ""]   # my words, exactly as written
    return "\n".join(lines)


def save_email(folder, text):
    return write_new(Path(folder), "manager-email", ".txt", text)
