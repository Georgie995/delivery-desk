"""Stage 1: check a delivery with the tools I already have, then start my working note.

delivery-ops-hub (or, without alerts, manifest-doctor) and ai-triage run as separate programs,
exactly as I'd run them by hand, so their own checks, messages, alerts and exit codes stay
unchanged. Nothing here sends anything.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from .note import build_note, write_note
from .settings import SettingsError

# Each tool is given only the secret it needs: the webhook secret only to delivery-ops-hub,
# the AI key only to ai-triage, and manifest-doctor neither.
SECRET_NAMES = ("OPS_HUB_WEBHOOK_SECRET", "ANTHROPIC_API_KEY")


def run_check(settings, tree, doctor_args, secrets=None):
    """Check a delivery, then start the working note if problems were found.

    With alerts (delivery-ops-hub set up): returns its own exit code, 0 clean, 1 problems found,
    2 not checked, 3 not delivered. Without alerts (no ops_hub_path, the app's route when alerts
    are off): runs manifest-doctor directly and returns its code, 0, 1 or 2.
    `secrets` (from the app's Credential Manager) are handed to the one tool that needs each.
    """
    alerts = bool(settings.get("ops_hub_path"))
    if not alerts:
        _check_direct_settings(settings, doctor_args)
    reports = Path(settings["reports_dir"])
    before = _report_folders(reports)
    if alerts:
        code = _run_ops_hub(settings, tree, doctor_args, secrets)
    else:
        code = _run_manifest_doctor(settings, tree, doctor_args)

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

    triage, triage_file = _run_ai_triage(settings, folder, secrets)
    note = write_note(folder, build_note(report, triage=triage, triage_file=triage_file or "triage.md"))
    _say(f"Working note written: {note}\n"
         f"  Fill in its five \"(fill in)\" sections, then run:\n"
         f"    python -m delivery_desk email \"{note}\"\n"
         f"  (add --ask to be asked for them instead)")
    return code


def _check_direct_settings(settings, doctor_args):
    """Without alerts, delivery-desk runs manifest-doctor itself, so it needs to know where it is."""
    if not settings.get("manifest_doctor_path"):
        raise SettingsError("without alerts, delivery-desk needs manifest_doctor_path (where manifest-doctor is)")
    if not (Path(settings["manifest_doctor_path"]) / "manifest_doctor").is_dir():
        raise SettingsError(f"manifest-doctor not found at {settings['manifest_doctor_path']}")
    if not settings.get("reports_dir"):
        raise SettingsError("without alerts, delivery-desk needs reports_dir (where reports go)")
    if "--out" in doctor_args:
        raise ValueError("--out is set by delivery-desk (the reports folder); remove it")


def _run_manifest_doctor(settings, tree, doctor_args):
    command = [sys.executable, "-m", "manifest_doctor", "check", str(tree), *doctor_args,
               "--out", str(settings["reports_dir"])]
    try:
        return subprocess.run(command, env=_env_with_path(settings["manifest_doctor_path"])).returncode
    except OSError as error:
        _say(f"couldn't start manifest-doctor: {error}")
        return 2


def _run_ops_hub(settings, tree, doctor_args, secrets):
    command = [sys.executable, "-m", "delivery_ops_hub", "--config", str(settings["ops_hub_config"]),
               "check", str(tree), *doctor_args]
    try:
        env = _env_with_path(settings["ops_hub_path"], secrets, give=("OPS_HUB_WEBHOOK_SECRET",))
        return subprocess.run(command, env=env).returncode
    except OSError as error:
        _say(f"couldn't start delivery-ops-hub: {error}")
        return 3


def _run_ai_triage(settings, folder, secrets=None):
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
                                   cwd=settings["ai_triage_path"],
                                   env=_env_with_path(settings["ai_triage_path"], secrets, give=("ANTHROPIC_API_KEY",)))
    except OSError as error:
        return f"ai-triage couldn't start: {error}", None
    new = sorted(set(folder.glob("triage*.json")) - before)
    if not new:
        return f"ai-triage stopped without writing a note (exit code {completed.returncode})", None
    return json.loads(new[-1].read_text(encoding="utf-8")), new[-1].with_suffix(".md").name


def _env_with_path(folder, secrets=None, give=()):
    """Run a tool straight from its folder, without installing it, with only the secrets it needs.
    A secret handed over by the app wins over one in the environment, for this run only."""
    env = dict(os.environ)
    for name in SECRET_NAMES:
        if name not in give:
            env.pop(name, None)
        elif secrets and secrets.get(name):
            env[name] = secrets[name]
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(folder), env.get("PYTHONPATH")]))
    env["PYTHONIOENCODING"] = "utf-8"  # so accented file names survive
    return env


def _report_folders(reports):
    if not reports.exists():
        return set()
    return {p for p in reports.iterdir() if p.is_dir() and p.name.startswith("report-")}


def _say(text):
    print(f"[delivery-desk] {text}", flush=True)
