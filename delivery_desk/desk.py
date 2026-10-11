"""Stage 1: check a delivery with the tools I already have, then start my working note.

delivery-ops-hub and ai-triage run as separate programs, exactly as I'd run them by hand, so
their own checks, messages, alerts and exit codes stay unchanged. Nothing here sends anything.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from .note import build_note, write_note


def run_check(settings, tree, doctor_args):
    """Returns delivery-ops-hub's own exit code: 0 clean, 1 problems found, 2 not checked, 3 not delivered."""
    reports = Path(settings["reports_dir"])
    before = _report_folders(reports)
    code = _run_ops_hub(settings, tree, doctor_args)

    # Compare folder lists before and after, as delivery-ops-hub does with manifest-doctor.
    new = sorted(_report_folders(reports) - before)
    if not new or not (new[-1] / "report.json").exists():
        _say("No report was written, so there's no working note.")
        return code
    folder = new[-1]
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    result = report["header"]["result"]
    if result != "PROBLEMS FOUND":
        _say(f"{result}: no working note needed.")
        return code

    triage, triage_file = _run_ai_triage(settings, folder)
    note = write_note(folder, build_note(report, triage=triage, triage_file=triage_file or "triage.md"))
    _say(f"Working note written: {note}\n"
         f"  Fill in its five \"(fill in)\" sections, then run:\n"
         f"    python -m delivery_desk email \"{note}\"\n"
         f"  (add --ask to be asked for them instead)")
    return code


def _run_ops_hub(settings, tree, doctor_args):
    command = [sys.executable, "-m", "delivery_ops_hub", "--config", str(settings["ops_hub_config"]),
               "check", str(tree), *doctor_args]
    try:
        return subprocess.run(command, env=_env_with_path(settings["ops_hub_path"])).returncode
    except OSError as error:
        _say(f"couldn't start delivery-ops-hub: {error}")
        return 3


def _run_ai_triage(settings, folder):
    """ai-triage's checked summary for the note: (its triage.json record, its .md name), or (reason, None)."""
    if not settings["ai_triage_python"]:
        return "ai-triage is not set up in delivery-desk.toml", None
    python = Path(settings["ai_triage_python"])
    if not python.exists():
        return f"ai-triage's Python not found at {settings['ai_triage_python']}", None
    before = set(folder.glob("triage*.json"))
    try:
        # Its own Python (it has the Anthropic library) and its own folder (its settings and playbook).
        completed = subprocess.run([str(python), "-m", "ai_triage", "draft", str(folder)],
                                   cwd=settings["ai_triage_path"], env=_env_with_path(settings["ai_triage_path"]))
    except OSError as error:
        return f"ai-triage couldn't start: {error}", None
    new = sorted(set(folder.glob("triage*.json")) - before)
    if not new:
        return f"ai-triage stopped without writing a note (exit code {completed.returncode})", None
    return json.loads(new[-1].read_text(encoding="utf-8")), new[-1].with_suffix(".md").name


def _env_with_path(folder):
    """Run a tool straight from its folder, without installing it."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(folder), env.get("PYTHONPATH")]))
    env["PYTHONIOENCODING"] = "utf-8"  # so accented file names survive
    return env


def _report_folders(reports):
    if not reports.exists():
        return set()
    return {p for p in reports.iterdir() if p.is_dir() and p.name.startswith("report-")}


def _say(text):
    print(f"[delivery-desk] {text}", flush=True)
