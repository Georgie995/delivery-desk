"""Engine additions for the Delivery Desk app: secrets handed to one tool at a time, and the
no-alerts route's settings checks. Needs none of the other repos."""

import pytest

from delivery_desk import desk
from delivery_desk.settings import SettingsError

HOOK, KEY = "OPS_HUB_WEBHOOK_SECRET", "ANTHROPIC_API_KEY"


def test_each_tool_gets_only_its_own_secret_from_the_environment(monkeypatch):
    monkeypatch.setenv(HOOK, "hook-from-env")
    monkeypatch.setenv(KEY, "key-from-env")
    hub = desk._env_with_path("hub", give=(HOOK,))
    assert hub[HOOK] == "hook-from-env" and KEY not in hub
    triage = desk._env_with_path("triage", give=(KEY,))
    assert triage[KEY] == "key-from-env" and HOOK not in triage


def test_secrets_handed_over_by_the_app_go_only_to_the_tool_that_needs_them(monkeypatch):
    monkeypatch.delenv(HOOK, raising=False)
    monkeypatch.delenv(KEY, raising=False)
    secrets = {HOOK: "hook-from-app", KEY: "key-from-app"}
    hub = desk._env_with_path("hub", secrets=secrets, give=(HOOK,))
    triage = desk._env_with_path("triage", secrets=secrets, give=(KEY,))
    doctor = desk._env_with_path("doctor", secrets=secrets, give=())
    assert (hub.get(HOOK), hub.get(KEY)) == ("hook-from-app", None)
    assert (triage.get(KEY), triage.get(HOOK)) == ("key-from-app", None)
    assert HOOK not in doctor and KEY not in doctor


def direct(tmp_path, **overrides):
    settings = {"ops_hub_path": None, "ops_hub_config": None, "manifest_doctor_path": str(tmp_path),
                "reports_dir": str(tmp_path / "reports"), "ai_triage_path": None, "ai_triage_python": None}
    settings.update(overrides)
    return settings


def test_the_no_alerts_route_needs_to_know_where_manifest_doctor_is(tmp_path):
    with pytest.raises(SettingsError, match="manifest_doctor_path"):
        desk.run_check(direct(tmp_path, manifest_doctor_path=None), tmp_path, ["--manifest", "m.md5"])
    with pytest.raises(SettingsError, match="manifest-doctor not found"):
        desk.run_check(direct(tmp_path), tmp_path, ["--manifest", "m.md5"])   # no manifest_doctor/ inside


def test_the_no_alerts_route_sets_the_reports_folder_itself(tmp_path):
    (tmp_path / "manifest_doctor").mkdir()
    with pytest.raises(ValueError, match="--out"):
        desk.run_check(direct(tmp_path), tmp_path, ["--manifest", "m.md5", "--out", "elsewhere"])


class Started:
    """Stands in for starting a program: records what it was given instead of running it."""
    def __init__(self):
        self.runs = []

    def __call__(self, command, **kwargs):
        self.runs.append((command, kwargs.get("env", {})))

        class Done:
            returncode = 0
        return Done()


def test_delivery_ops_hub_is_started_with_the_webhook_secret_and_never_the_ai_key(tmp_path, monkeypatch):
    started = Started()
    monkeypatch.setattr(desk.subprocess, "run", started)
    settings = {"ops_hub_path": str(tmp_path), "ops_hub_config": str(tmp_path / "ops-hub.toml")}
    desk._run_ops_hub(settings, tmp_path, ["--manifest", "m.md5"], {HOOK: "hook-from-app", KEY: "key-from-app"})
    [(command, env)] = started.runs
    assert "delivery_ops_hub" in command and env.get(HOOK) == "hook-from-app" and KEY not in env


def test_ai_triage_is_started_with_the_ai_key_and_never_the_webhook_secret(tmp_path, monkeypatch):
    started = Started()
    monkeypatch.setattr(desk.subprocess, "run", started)
    python = tmp_path / "python.exe"
    python.write_text("stand-in", encoding="utf-8")
    settings = {"ai_triage_path": str(tmp_path), "ai_triage_python": str(python)}
    desk._run_ai_triage(settings, tmp_path, {HOOK: "hook-from-app", KEY: "key-from-app"})
    [(command, env)] = started.runs
    assert "ai_triage" in command and env.get(KEY) == "key-from-app" and HOOK not in env


def test_manifest_doctor_is_started_with_no_secrets_at_all(tmp_path, monkeypatch):
    monkeypatch.setenv(HOOK, "hook-from-env")
    monkeypatch.setenv(KEY, "key-from-env")
    started = Started()
    monkeypatch.setattr(desk.subprocess, "run", started)
    desk._run_manifest_doctor({"manifest_doctor_path": str(tmp_path), "reports_dir": str(tmp_path / "r")},
                              tmp_path, ["--manifest", "m.md5"])
    [(command, env)] = started.runs
    assert "manifest_doctor" in command and HOOK not in env and KEY not in env


# --- For the app: messages collected, no console windows, and Stop ends a tool and its children -----

import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def test_on_the_command_line_tools_run_exactly_as_before(monkeypatch):
    started = Started()
    monkeypatch.setattr(desk.subprocess, "run", started)
    desk._run(["tool"], env={})
    assert started.runs == [(["tool"], {})]


def test_for_the_app_each_line_a_tool_prints_is_collected():
    lines = []
    code = desk._run([sys.executable, "-c", "import sys; print('first', flush=True); print('second', file=sys.stderr)"],
                     env=dict(os.environ), output=lines.append)
    assert code == 0
    assert [line.strip() for line in lines] == ["first", "second"]


def test_for_the_app_no_console_window_is_opened(monkeypatch):
    seen = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            seen.update(kwargs)
            self.stdout = iter(())
            self.returncode = 0
            self.pid = 1

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(desk.subprocess, "Popen", FakePopen)
    desk._run(["tool"], env={}, output=lambda line: None)
    if os.name == "nt":
        assert seen["creationflags"] & subprocess.CREATE_NO_WINDOW
    else:
        # Linux and macOS: the tool gets its own process group, so Stop can end it and its children.
        assert seen["start_new_session"] is True


def _alive(pid):
    if os.name == "nt":
        found = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in found
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        # A stopped program can linger as a "zombie" (state Z) until it's tidied away: that's not running.
        return stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_stop_ends_the_tool_and_any_program_it_started(tmp_path):
    pid_file = tmp_path / "child.pid"
    child = "import time; time.sleep(60)"
    parent = ("import subprocess, sys, time; "
              f"p = subprocess.Popen([sys.executable, '-c', {child!r}]); "
              f"open({str(pid_file)!r}, 'w').write(str(p.pid)); time.sleep(60)")
    stop = threading.Event()
    threading.Timer(1.5, stop.set).start()
    started = time.monotonic()
    desk._run([sys.executable, "-c", parent], env=dict(os.environ), output=lambda line: None, stop=stop)
    assert time.monotonic() - started < 20                     # it didn't wait the full minute
    child_pid = int(pid_file.read_text())
    time.sleep(1)
    assert not _alive(child_pid)                               # the child was stopped too
