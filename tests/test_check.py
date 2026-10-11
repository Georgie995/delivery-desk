"""Module 3: `check` joins the real delivery-ops-hub (and through it manifest-doctor) and ai-triage.

Runs only when those repos sit next to delivery-desk. A small web server inside the test plays
n8n. The AI key is always removed, so ai-triage uses its code-written fallback: no AI call, no cost.
"""

import hashlib
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from delivery_desk import cli

PROJECTS = Path(__file__).resolve().parents[2]
OPS_HUB = PROJECTS / "delivery-ops-hub"
DOCTOR = PROJECTS / "delivery-verify"           # manifest-doctor's local folder
TRIAGE = PROJECTS / "ai-triage"
TRIAGE_PYTHON = TRIAGE / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
SECRET = "test-secret-1234567890"

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in (OPS_HUB / "delivery_ops_hub", DOCTOR / "manifest_doctor", TRIAGE_PYTHON)),
    reason="delivery-ops-hub, manifest-doctor and ai-triage (with its .venv) must sit next to delivery-desk")


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)   # never a real AI call from these tests


@pytest.fixture
def n8n():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            data = json.dumps({"logged": True, "alerted": body["status"] != "CLEAN", "alert_mode": "dry_run"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/webhook/delivery-check", received
    httpd.shutdown()
    httpd.server_close()


def closed_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}/webhook/delivery-check"


def make_delivery(tmp_path, broken=True):
    """A tiny synthetic delivery and its MD5 manifest. If broken, one file no longer matches."""
    tree = tmp_path / "show-a-ep01"
    files = {"ShowA/Reel01/clip_0001.mov": b"frames one", "ShowA/Reel01/clip_0002.mov": b"frames two"}
    lines = []
    for rel, data in files.items():
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        (tree / rel).write_bytes(data)
        lines.append(f"{hashlib.md5(data).hexdigest()}  {rel}")
    if broken:
        (tree / "ShowA/Reel01/clip_0002.mov").write_bytes(b"frames two, changed")
    manifest = tmp_path / "set1.md5"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tree, manifest


def settings(tmp_path, url, triage=True):
    hub_config = tmp_path / "ops-hub.toml"
    hub_config.write_text(f'manifest_doctor_path = "{DOCTOR.as_posix()}"\n'
                          f'reports_dir = "{(tmp_path / "reports").as_posix()}"\n'
                          f'webhook_url = "{url}"\noutbox_dir = "{(tmp_path / "outbox").as_posix()}"\n',
                          encoding="utf-8")
    desk = tmp_path / "delivery-desk.toml"
    text = f'ops_hub_path = "{OPS_HUB.as_posix()}"\nops_hub_config = "{hub_config.as_posix()}"\n'
    if triage:
        text += f'ai_triage_path = "{TRIAGE.as_posix()}"\nai_triage_python = "{TRIAGE_PYTHON.as_posix()}"\n'
    desk.write_text(text, encoding="utf-8")
    return desk


def check(desk, tree, manifest):
    return cli.main(["--config", str(desk), "check", str(tree), "--manifest", str(manifest)])


def report_folders(tmp_path):
    return sorted((tmp_path / "reports").glob("report-*"))


def test_problems_found_runs_all_three_and_writes_the_working_note(tmp_path, n8n, capfd):
    url, received = n8n
    tree, manifest = make_delivery(tmp_path)
    assert check(settings(tmp_path, url), tree, manifest) == 1           # delivery-ops-hub's "problems found"
    assert [m["status"] for m in received] == ["PROBLEMS_FOUND"]         # exactly one alert
    [folder] = report_folders(tmp_path)
    assert {"report.json", "triage.json", "triage.md", "incident-note.md"} <= {p.name for p in folder.iterdir()}
    note = (folder / "incident-note.md").read_text(encoding="utf-8")
    assert f"## Which delivery\n{tree.as_posix()}" in note or f"## Which delivery\n{tree}" in note
    assert "- HASH_MISMATCH (error): 1 found" in note
    assert "## ai-triage summary\nFALLBACK: written by code" in note
    assert "Full triage note: triage.md" in note
    out = capfd.readouterr().out
    assert "Working note written" in out and "--ask" in out


def test_a_clean_delivery_is_alerted_as_usual_but_needs_no_note(tmp_path, n8n, capfd):
    url, received = n8n
    tree, manifest = make_delivery(tmp_path, broken=False)
    assert check(settings(tmp_path, url), tree, manifest) == 0
    assert [m["status"] for m in received] == ["CLEAN"]
    [folder] = report_folders(tmp_path)
    assert not list(folder.glob("incident-note*")) and not list(folder.glob("triage*"))
    assert "no working note" in capfd.readouterr().out.lower()


def test_an_undelivered_alert_still_gets_a_working_note_and_exit_3(tmp_path, capfd):
    tree, manifest = make_delivery(tmp_path)
    assert check(settings(tmp_path, closed_url()), tree, manifest) == 3
    assert len(list((tmp_path / "outbox").glob("*.json"))) == 1          # delivery-ops-hub kept it
    [folder] = report_folders(tmp_path)
    assert (folder / "incident-note.md").exists()


def test_without_ai_triage_the_note_says_why_and_everything_else_works(tmp_path, n8n):
    url, received = n8n
    tree, manifest = make_delivery(tmp_path)
    assert check(settings(tmp_path, url, triage=False), tree, manifest) == 1
    [folder] = report_folders(tmp_path)
    note = (folder / "incident-note.md").read_text(encoding="utf-8")
    assert "Not available (ai-triage is not set up in delivery-desk.toml)." in note
    assert len(received) == 1


def test_a_missing_ai_triage_python_is_explained_in_the_note(tmp_path, n8n):
    url, _ = n8n
    tree, manifest = make_delivery(tmp_path)
    desk = settings(tmp_path, url)
    desk.write_text(desk.read_text(encoding="utf-8").replace(TRIAGE_PYTHON.as_posix(), "C:/nowhere/python.exe"),
                    encoding="utf-8")
    assert check(desk, tree, manifest) == 1
    [folder] = report_folders(tmp_path)
    assert "Not available (ai-triage's Python not found at C:/nowhere/python.exe)." in \
        (folder / "incident-note.md").read_text(encoding="utf-8")


def test_a_check_that_could_not_run_writes_no_note(tmp_path, n8n, capfd):
    url, received = n8n
    tree, _ = make_delivery(tmp_path)
    assert check(settings(tmp_path, url), tree, tmp_path / "no-such-manifest.md5") == 2   # NOT CHECKED
    assert [m["status"] for m in received] == ["NOT_CHECKED"]
    assert not list(tmp_path.rglob("incident-note*"))
    assert "no working note" in capfd.readouterr().out.lower()


def test_a_missing_webhook_secret_stops_delivery_ops_hub_and_no_note_is_written(tmp_path, n8n, monkeypatch):
    url, received = n8n
    monkeypatch.delenv("OPS_HUB_WEBHOOK_SECRET")
    tree, manifest = make_delivery(tmp_path)
    assert check(settings(tmp_path, url), tree, manifest) == 3
    assert received == [] and not list(tmp_path.rglob("incident-note*"))


def test_the_delivery_itself_is_never_changed(tmp_path, n8n):
    url, _ = n8n
    tree, manifest = make_delivery(tmp_path)
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes()) for p in tree.rglob("*") if p.is_file()}
    check(settings(tmp_path, url), tree, manifest)
    after = {p: (p.stat().st_size, p.stat().st_mtime_ns, p.read_bytes()) for p in tree.rglob("*") if p.is_file()}
    assert before == after


# --- End to end against the real n8n (skipped if it isn't running or no secret is saved) ----------------

def _real_secret():
    """Read once, before the tests swap in their stand-in secret. On Windows, also the value saved
    for this user, which a terminal opened before it was saved can't see."""
    secret = os.environ.get("OPS_HUB_WEBHOOK_SECRET", "").strip()
    if os.name == "nt" and not secret:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                secret = str(winreg.QueryValueEx(key, "OPS_HUB_WEBHOOK_SECRET")[0]).strip()
        except OSError:
            pass
    return secret


REAL_SECRET = _real_secret()


def _n8n_ready():
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5678/webhook/delivery-check", data=b"{}",
                                                      method="POST"), timeout=2)
    except urllib.error.HTTPError as error:
        return error.code == 403          # the webhook is there and wants its secret
    except OSError:
        return False
    return False


@pytest.mark.skipif(not _n8n_ready() or not REAL_SECRET, reason="n8n not running or no saved secret")
def test_end_to_end_a_broken_delivery_reaches_the_real_n8n_log_and_gets_a_note(tmp_path, monkeypatch):
    monkeypatch.setenv("OPS_HUB_WEBHOOK_SECRET", REAL_SECRET)
    log = OPS_HUB / "runtime" / "logs" / "delivery-checks.csv"
    before = log.read_text(encoding="utf-8-sig").splitlines() if log.exists() else []
    tree, manifest = make_delivery(tmp_path)
    assert check(settings(tmp_path, "http://localhost:5678/webhook/delivery-check"), tree, manifest) == 1
    new_rows = [row for row in log.read_text(encoding="utf-8-sig").splitlines()[len(before):] if tree.name in row]
    assert len(new_rows) == 1 and ",PROBLEMS_FOUND," in new_rows[0]
    assert not list((tmp_path / "outbox").glob("*.json"))              # delivered, nothing waiting
    [folder] = report_folders(tmp_path)
    assert (folder / "incident-note.md").exists()
