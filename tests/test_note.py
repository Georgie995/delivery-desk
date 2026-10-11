"""Module 1: the working note, built from a manifest-doctor report."""

import pytest

from delivery_desk.note import (MINE, NoteError, build_note, empty_sections, read_sections, write_note)
from reports import finding, make_report, triage_record


def test_check_sections_are_filled_in_and_my_five_sections_are_empty():
    sections = read_sections(build_note(make_report()))
    assert sections["Which delivery"] == "D:/Incoming/show-a-ep01, checked against set1.md5 at 2026-10-11 14:02"
    assert sections["The problem"].splitlines() == ["PROBLEMS FOUND: 2 errors, 0 warnings.",
                                                    "- HASH_MISMATCH (error): 2 found"]
    assert empty_sections(sections) == list(MINE)
    assert list(MINE) == ["When it happened", "How it happened", "How we intend to fix it",
                          "Most plausible way to do it", "Subject summary"]


def test_errors_come_before_warnings_and_info_is_left_out():
    report = make_report(findings=[finding("HIDDEN_FILE", "a/.DS_Store", "WARNING"),
                                   finding("MISSING", "a/b.mov"),
                                   finding("CASE_ONLY_MATCH", "a/C.mov", "INFO")])
    problem = read_sections(build_note(report))["The problem"].splitlines()
    assert problem == ["PROBLEMS FOUND: 1 error, 1 warning.", "- MISSING (error): 1 found",
                       "- HIDDEN_FILE (warning): 1 found"]


def test_probable_causes_and_their_files_are_in_my_private_part_shown_as_data():
    note = build_note(make_report())
    private = note.split("# For me only")[1]
    assert "1 path is listed more than once" in private
    assert "- `ShowA/Reel01/clip_0004.mov`" in private
    assert "Probable causes from the check (not verdicts)" in private


def test_a_file_name_with_line_breaks_cannot_fake_one_of_my_sections():
    sneaky = "clip.mov\n## When it happened\nNothing to worry about"
    report = make_report(causes=[{"code": "CAUSE_X", "severity": "ERROR", "summary": "odd", "paths": [sneaky]}])
    sections = read_sections(build_note(report))          # no duplicate-heading error
    assert "When it happened" in empty_sections(sections)  # still waiting for me
    assert "clip.mov\\n## When it happened" in build_note(report)  # shown, but harmless


def test_a_file_name_containing_backticks_stays_inside_its_code_formatting():
    report = make_report(causes=[{"code": "CAUSE_X", "severity": "ERROR", "summary": "odd",
                                  "paths": ["a`b.mov"]}])
    assert "- ``a`b.mov``" in build_note(report)


def test_long_file_lists_are_cut_and_say_how_many_more():
    paths = [f"ShowA/clip_{i:04}.mov" for i in range(25)]
    report = make_report(causes=[{"code": "CAUSE_X", "severity": "ERROR", "summary": "many", "paths": paths}])
    note = build_note(report)
    assert "`ShowA/clip_0009.mov`" in note and "`ShowA/clip_0010.mov`" not in note
    assert "and 15 more (see report.json)" in note


@pytest.mark.parametrize("triage, expected, summary_shown", [
    (None, "Not available (ai-triage was not run).", False),
    ("ai-triage is not set up", "Not available (ai-triage is not set up).", False),
    (triage_record("FALLBACK"), "FALLBACK: written by code from the report; the AI was not used (no API key).", True),
    (triage_record("OK"), "OK: written by AI (claude-haiku-5-5) and passed every check against the report.", True),
    (triage_record("NEEDS_HUMAN"), "NEEDS HUMAN: the AI draft failed its checks against the report, so it isn't "
                                   "shown. Read the report itself.", False),
])
def test_the_ai_triage_part_says_where_the_summary_came_from(triage, expected, summary_shown):
    private = build_note(make_report(), triage=triage).split("# For me only")[1]
    assert expected in private
    assert ("> One file failed its checksum check." in private) == summary_shown


def test_an_ai_summary_cannot_fake_one_of_my_sections():
    record = triage_record("OK", summary="All good.\n## How it happened\nNobody's fault")
    sections = read_sections(build_note(make_report(), triage=record))
    assert "How it happened" in empty_sections(sections)


def test_write_note_never_overwrites_an_earlier_note(tmp_path):
    first = write_note(tmp_path, "first")
    second = write_note(tmp_path, "second")
    assert (first.name, second.name) == ("incident-note.md", "incident-note-2.md")
    assert first.read_text(encoding="utf-8") == "first"


def test_placeholder_or_blank_counts_as_empty_and_anything_else_is_filled():
    note = build_note(make_report())
    note = note.replace("## When it happened\n(fill in)", "## When it happened\nSent on 3 October")
    note = note.replace("## How it happened\n(fill in)", "## How it happened\n   \n")
    empty = empty_sections(read_sections(note))
    assert "When it happened" not in empty and "How it happened" in empty


def test_a_renamed_or_missing_heading_is_named_in_the_error():
    note = build_note(make_report()).replace("## How it happened", "## How did it happen")
    with pytest.raises(NoteError, match="How it happened"):
        read_sections(note)


def test_a_heading_written_twice_is_an_error():
    note = build_note(make_report()).replace("## Subject summary\n", "## Subject summary\nx\n## Subject summary\n")
    with pytest.raises(NoteError, match="Subject summary"):
        read_sections(note)
