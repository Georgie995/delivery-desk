"""Stage 1: check a delivery with the tools I already have, then start my working note.

delivery-ops-hub (or, without alerts, manifest-doctor) and ai-triage run as separate programs,
exactly as I'd run them by hand, so their own checks, messages, alerts and exit codes stay
unchanged. Nothing here sends anything.

On the command line, the tools' messages go straight to the terminal. For the Delivery Desk app,
they are collected instead (`output`), no console windows open, and `stop` can end a check.
"""

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .note import build_note, write_note
from .settings import SettingsError

# Each tool is given only the secret it needs: the webhook secret only to delivery-ops-hub,
# the AI key only to ai-triage, and manifest-doctor neither.
SECRET_NAMES = ("OPS_HUB_WEBHOOK_SECRET", "ANTHROPIC_API_KEY")
STOPPED = 130  # the usual exit code for "interrupted"


@dataclass
class Outcome:
    code: int                 # the checking tool's own exit code (STOPPED if stopped)
    report_folder: Path | None
    result: str | None        # "CLEAN", "PASSED WITH WARNINGS" or "PROBLEMS FOUND"; None if no report
    note: Path | None         # the working note, written only for PROBLEMS FOUND
    stopped: bool = False


def run_check(settings, tree, doctor_args, secrets=None):
    """The command line's view: just the exit code. See check() for what each code means."""
    return check(settings, tree, doctor_args, secrets).code


def check(settings, tree, doctor_args, secrets=None, output=None, stop=None):
    """Check a delivery, then start the working note if problems were found.

    With alerts (delivery-ops-hub set up): its own exit code, 0 clean, 1 problems found,
    2 not checked, 3 not delivered. Without alerts (no ops_hub_path, the app's route when alerts
    are off): manifest-doctor runs directly, 0, 1 or 2.
    `secrets` (from the app's Credential Manager) are handed to the one tool that needs each.
    `output` (the app) receives every message instead of the terminal; `stop` ends the check.
    """
    alerts = bool(settings.get("ops_hub_path"))
    if not alerts:
        _check_direct_settings(settings, doctor_args)
    reports = Path(settings["reports_dir"])
    before = _report_folders(reports)
    if alerts:
        code = _run_ops_hub(settings, tree, doctor_args, secrets, output, stop)
    else:
        code = _run_manifest_doctor(settings, tree, doctor_args, output, stop)
    if stop is not None and stop.is_set():
        _say("Stopped. Nothing was changed, and no working note was written.", output)
        return Outcome(STOPPED, None, None, None, stopped=True)

    # Compare folder lists before and after, as delivery-ops-hub does with manifest-doctor.
    new = sorted(_report_folders(reports) - before)
    if not new or not (new[-1] / "report.json").exists():
        _say("No report was written, so there's no working note.", output)
        return Outcome(code, None, None, None)
    folder = new[-1]
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    result = report["header"]["result"]
    if result != "PROBLEMS FOUND":
        _say(f"{result}: no working note needed.", output)
        return Outcome(code, folder, result, None)

    triage, triage_file = _run_ai_triage(settings, folder, secrets, output, stop)
    note = write_note(folder, build_note(report, triage=triage, triage_file=triage_file or "triage.md"))
    _say(f"Working note written: {note}\n"
         f"  Fill in its five \"(fill in)\" sections, then run:\n"
         f"    python -m delivery_desk email \"{note}\"\n"
         f"  (add --ask to be asked for them instead)", output)
    return Outcome(code, folder, result, note)


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


def _run_manifest_doctor(settings, tree, doctor_args, output=None, stop=None):
    command = [sys.executable, "-m", "manifest_doctor", "check", str(tree), *doctor_args,
               "--out", str(settings["reports_dir"])]
    try:
        return _run(command, _env_with_path(settings["manifest_doctor_path"]), output=output, stop=stop)
    except OSError as error:
        _say(f"couldn't start manifest-doctor: {error}", output)
        return 2


def _run_ops_hub(settings, tree, doctor_args, secrets, output=None, stop=None):
    command = [sys.executable, "-m", "delivery_ops_hub", "--config", str(settings["ops_hub_config"]),
               "check", str(tree), *doctor_args]
    try:
        env = _env_with_path(settings["ops_hub_path"], secrets, give=("OPS_HUB_WEBHOOK_SECRET",))
        return _run(command, env, output=output, stop=stop)
    except OSError as error:
        _say(f"couldn't start delivery-ops-hub: {error}", output)
        return 3


def _run_ai_triage(settings, folder, secrets=None, output=None, stop=None):
    """ai-triage's checked summary for the note: (its triage.json record, its .md name), or (reason, None)."""
    if not settings["ai_triage_python"]:
        return "ai-triage is not set up", None
    python = Path(settings["ai_triage_python"])
    if not python.exists():
        return f"ai-triage's Python not found at {settings['ai_triage_python']}", None
    before = set(folder.glob("triage*.json"))
    try:
        # Its own Python (it has the Anthropic library) and its own folder (its settings and playbook).
        code = _run([str(python), "-m", "ai_triage", "draft", str(folder)],
                    _env_with_path(settings["ai_triage_path"], secrets, give=("ANTHROPIC_API_KEY",)),
                    cwd=settings["ai_triage_path"], output=output, stop=stop)
    except OSError as error:
        return f"ai-triage couldn't start: {error}", None
    new = sorted(set(folder.glob("triage*.json")) - before)
    if not new:
        return f"ai-triage stopped without writing a note (exit code {code})", None
    return json.loads(new[-1].read_text(encoding="utf-8")), new[-1].with_suffix(".md").name


def _run(command, env, cwd=None, output=None, stop=None):
    """Run one tool and return its exit code.

    Command line (no `output`, no `stop`): exactly as before, its messages go to the terminal.
    App: messages are collected line by line, no console window opens, and setting `stop`
    ends the tool together with any program it started (delivery-ops-hub starts manifest-doctor).
    """
    if output is None and stop is None:
        return subprocess.run(command, env=env, cwd=cwd).returncode
    if os.name == "nt":
        extra = {"creationflags": subprocess.CREATE_NO_WINDOW}
    else:
        extra = {"start_new_session": True}  # its own process group, so Stop can end its children too
    process = subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", **extra)
    # Read in the background, so a chatty tool can never fill its pipe and stall.
    reader = threading.Thread(target=_collect, args=(process.stdout, output), daemon=True)
    reader.start()
    while process.poll() is None:
        if stop is not None and stop.is_set():
            _stop_with_children(process)
            break
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass
    process.wait()
    reader.join(timeout=5)
    return process.returncode


def _collect(stream, output):
    for line in stream:
        if output is not None:
            output(line)


def _stop_with_children(process):
    """Stopping is safe: every tool only reads the delivery. Ending a program doesn't end the
    programs it started (delivery-ops-hub starts manifest-doctor), so the whole family is ended:
    on Windows with its own taskkill; elsewhere by signalling the tool's process group."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return
    import signal
    try:
        os.killpg(process.pid, signal.SIGTERM)   # its own group: the group's number is the tool's
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)   # still running after a polite request
    except ProcessLookupError:
        pass                                      # it had already finished


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


def _say(text, output=None):
    message = f"[delivery-desk] {text}"
    if output is not None:
        output(message + "\n")
    else:
        print(message, flush=True)
