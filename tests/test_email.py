"""Module 1: the manager email, built from a filled-in working note, and the `email` command."""

from delivery_desk import cli
from delivery_desk.manager_email import build_email
from delivery_desk.note import build_note, read_sections, write_note
from reports import make_report, triage_record

MY_TEXT = {
    "When it happened": "Delivered 3 October; the second copy overwrote it on 9 October.",
    "How it happened": "The same path existed on two tapes with different content.\n  Both were delivered to one place.",
    "How we intend to fix it": "Re-deliver the newer file under a different name.",
    "Most plausible way to do it": "Copy it from tape 2, rename it with _v2, upload with a note listing both "
                                   "versions & their checksums (MD5).",
    "Subject summary": "duplicate file overwritten on S3",
}


def filled(note, answers=MY_TEXT):
    for heading, text in answers.items():
        start = note.index(f"## {heading}\n") + len(f"## {heading}\n")
        end = note.index("\n", start)                      # the "(fill in…)" line
        note = note[:start] + text + note[end:]
    return note


def test_the_email_has_the_subject_and_six_parts_in_order_with_my_words_unchanged():
    email = build_email(read_sections(filled(build_note(make_report()))))
    lines = email.splitlines()
    assert lines[0] == "Subject: Delivery issue: duplicate file overwritten on S3 (PROBLEMS FOUND)"
    headings = [l for l in lines if l.endswith(":") and not l.startswith(" ")]
    assert headings == ["The problem:", "Which delivery:", "When it happened:", "How it happened:",
                        "How we intend to fix it:", "Most plausible way to do it:"]
    for heading in ("When it happened", "How it happened", "How we intend to fix it", "Most plausible way to do it"):
        assert f"{heading}:\n{MY_TEXT[heading]}\n" in email      # word for word, indentation and all


def test_line_breaks_in_the_subject_summary_become_spaces():
    answers = dict(MY_TEXT, **{"Subject summary": "duplicate file\noverwritten   on S3"})
    email = build_email(read_sections(filled(build_note(make_report()), answers)))
    assert email.splitlines()[0] == "Subject: Delivery issue: duplicate file overwritten on S3 (PROBLEMS FOUND)"


def test_my_private_part_never_reaches_the_email():
    note = filled(build_note(make_report(), triage=triage_record("OK", summary="Private triage words.")))
    email = build_email(read_sections(note))
    for private in ("Private triage words", "listed more than once", "clip_0004", "ai-triage", "Probable"):
        assert private not in email


def test_my_edits_to_the_check_sections_are_used_as_written():
    note = filled(build_note(make_report())).replace("- HASH_MISMATCH (error): 2 found",
                                                     "Two files don't match their checksums.")
    assert "The problem:\nPROBLEMS FOUND: 2 errors, 0 warnings.\nTwo files don't match their checksums.\n" in \
        build_email(read_sections(note))


# --- The `email` command ---------------------------------------------------------------------------------

def test_the_command_writes_the_email_next_to_the_note_and_never_overwrites(tmp_path, capsys):
    note = write_note(tmp_path, filled(build_note(make_report())))
    assert cli.main(["email", str(note)]) == 0
    first = tmp_path / "manager-email.txt"
    assert first.read_text(encoding="utf-8").startswith("Subject: Delivery issue: duplicate file")
    assert "not been sent" in capsys.readouterr().out
    first.write_text("my edited copy", encoding="utf-8")
    assert cli.main(["email", str(note)]) == 0
    assert first.read_text(encoding="utf-8") == "my edited copy"
    assert (tmp_path / "manager-email-2.txt").exists()


def test_empty_sections_mean_no_email_and_a_list_of_what_is_missing(tmp_path, capsys):
    partly = {k: MY_TEXT[k] for k in ("When it happened", "How we intend to fix it")}
    note = write_note(tmp_path, filled(build_note(make_report()), partly))
    assert cli.main(["email", str(note)]) == 1
    out = capsys.readouterr().out
    assert "How it happened, Most plausible way to do it, Subject summary" in out
    assert not list(tmp_path.glob("manager-email*"))


def test_a_note_saved_by_notepad_with_windows_line_endings_and_a_bom_still_works(tmp_path):
    note = tmp_path / "incident-note.md"
    note.write_bytes(b"\xef\xbb\xbf" + filled(build_note(make_report())).replace("\n", "\r\n").encode("utf-8"))
    assert cli.main(["email", str(note)]) == 0
    email = (tmp_path / "manager-email.txt").read_text(encoding="utf-8")
    assert email.startswith("Subject: Delivery issue: duplicate file overwritten on S3 (PROBLEMS FOUND)")
    assert f"When it happened:\n{MY_TEXT['When it happened']}\n" in email


def test_a_broken_note_is_a_tool_error_that_names_the_problem(tmp_path, capsys):
    note = write_note(tmp_path, filled(build_note(make_report())).replace("## How it happened", "## Cause"))
    assert cli.main(["email", str(note)]) == 2
    assert "How it happened" in capsys.readouterr().err


def test_a_missing_note_is_a_tool_error(tmp_path, capsys):
    assert cli.main(["email", str(tmp_path / "nowhere.md")]) == 2
    assert "not found" in capsys.readouterr().err
