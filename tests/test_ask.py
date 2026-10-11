"""Module 2: `email --ask` asks only for empty sections and saves each answer straight away."""

import io

from delivery_desk import cli
from delivery_desk.note import build_note, empty_sections, read_sections, write_note
from reports import make_report
from test_email import MY_TEXT, filled


def run_with_typing(monkeypatch, note, typed):
    monkeypatch.setattr("sys.stdin", io.StringIO(typed))
    return cli.main(["email", str(note), "--ask"])


def sections_of(note):
    return read_sections(note.read_text(encoding="utf-8"))


def test_only_empty_sections_are_asked_and_my_written_text_is_untouched(tmp_path, monkeypatch, capsys):
    partly = {k: MY_TEXT[k] for k in ("When it happened", "How we intend to fix it")}
    note = write_note(tmp_path, filled(build_note(make_report()), partly))
    typed = "Two tapes held different files at one path.\n  The newer one replaced the older.\n\n" \
            "Restore from tape 1 and rename.\n\n" \
            "clip_0004 overwritten\n"
    assert run_with_typing(monkeypatch, note, typed) == 0
    out = capsys.readouterr().out
    assert "How it happened" in out and "When it happened (" not in out and "How we intend to fix it (" not in out
    s = sections_of(note)
    assert s["How it happened"] == "Two tapes held different files at one path.\n  The newer one replaced the older."
    assert s["Most plausible way to do it"] == "Restore from tape 1 and rename."
    assert s["Subject summary"] == "clip_0004 overwritten"
    assert s["When it happened"] == MY_TEXT["When it happened"]
    assert s["How we intend to fix it"] == MY_TEXT["How we intend to fix it"]
    assert (tmp_path / "manager-email.txt").read_text(encoding="utf-8").startswith(
        "Subject: Delivery issue: clip_0004 overwritten (PROBLEMS FOUND)")


def test_each_answer_is_saved_straight_away_so_stopping_halfway_keeps_it(tmp_path, monkeypatch, capsys):
    note = write_note(tmp_path, build_note(make_report()))
    assert run_with_typing(monkeypatch, note, "Delivered 3 October.\n\n") == 1   # then the typing stops
    assert sections_of(note)["When it happened"] == "Delivered 3 October."
    assert empty_sections(sections_of(note))[0] == "How it happened"
    assert "saved" in capsys.readouterr().out
    assert not list(tmp_path.glob("manager-email*"))


def test_ctrl_c_keeps_the_answers_given_so_far(tmp_path, monkeypatch):
    note = write_note(tmp_path, build_note(make_report()))
    typed = iter(["Delivered 3 October.", ""])

    def fake_input(prompt=""):
        try:
            return next(typed)
        except StopIteration:
            raise KeyboardInterrupt
    monkeypatch.setattr("builtins.input", fake_input)
    assert cli.main(["email", str(note), "--ask"]) == 1
    assert sections_of(note)["When it happened"] == "Delivered 3 October."


def test_pressing_enter_straight_away_skips_a_section(tmp_path, monkeypatch):
    note = write_note(tmp_path, build_note(make_report()))
    typed = "\n" + "Cause.\n\n" + "Fix.\n\n" + "Way.\n\n" + "Summary\n"
    assert run_with_typing(monkeypatch, note, typed) == 1
    assert empty_sections(sections_of(note)) == ["When it happened"]
    assert not list(tmp_path.glob("manager-email*"))


def test_an_answer_line_that_looks_like_a_heading_is_refused_and_asked_again(tmp_path, monkeypatch, capsys):
    note = write_note(tmp_path, filled(build_note(make_report()),
                                       {k: v for k, v in MY_TEXT.items() if k != "How it happened"}))
    typed = "## How we intend to fix it\n\n" + "Two tapes, one path.\n\n"
    assert run_with_typing(monkeypatch, note, typed) == 0
    assert "looks like a heading" in capsys.readouterr().out
    assert sections_of(note)["How it happened"] == "Two tapes, one path."


def test_text_written_in_the_note_while_answering_is_never_overwritten(tmp_path, monkeypatch, capsys):
    note = write_note(tmp_path, filled(build_note(make_report()),
                                       {k: v for k, v in MY_TEXT.items() if k != "How it happened"}))
    typed = iter(["My typed answer.", ""])

    def fake_input(prompt=""):
        # Meanwhile, Georgi fills the same section in his text editor and saves.
        text = note.read_text(encoding="utf-8")
        if "Written in the editor." not in text:
            note.write_text(text.replace("## How it happened\n(fill in)", "## How it happened\nWritten in the editor."),
                            encoding="utf-8")
        return next(typed)
    monkeypatch.setattr("builtins.input", fake_input)
    assert cli.main(["email", str(note), "--ask"]) == 0
    assert sections_of(note)["How it happened"] == "Written in the editor."
    assert "kept what's already written" in capsys.readouterr().out.lower()


def test_no_temporary_files_are_left_behind(tmp_path, monkeypatch):
    note = write_note(tmp_path, build_note(make_report()))
    run_with_typing(monkeypatch, note, "A.\n\nB.\n\nC.\n\nD.\n\nE\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["incident-note.md", "manager-email.txt"]


def test_the_note_and_the_no_email_message_both_mention_ask(tmp_path, capsys):
    text = build_note(make_report())
    assert "--ask" in text.split("## Which delivery")[0]
    note = write_note(tmp_path, text)
    assert cli.main(["email", str(note)]) == 1
    assert "--ask" in capsys.readouterr().out
