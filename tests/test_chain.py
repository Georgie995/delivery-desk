"""The copy → verify → alert chain, tools/copy-and-verify.sh (approved by Georgi 2026-10-20).

Runs the real script with bash, and the real job-watch, manifest-doctor, delivery-ops-hub and
ai-triage, when they sit next to delivery-desk. A small web server plays n8n. The "copy" is a short
Python command, so every outcome (good, bad, failed) can be staged. The AI key is always removed.
Synthetic data only.
"""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_check import DOCTOR, OPS_HUB, SECRET, TRIAGE_PYTHON, closed_url, n8n, settings  # noqa: F401 (fixture)

DESK = Path(__file__).resolve().parents[1]
SCRIPT = DESK / "tools" / "copy-and-verify.sh"
JOB_WATCH = DESK.parent / "job-watch"


def find_bash():
    """Git's own bash on Windows (another bash on PATH may be WSL's); the usual one elsewhere."""
    if os.name == "nt":
        try:
            exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True).stdout.strip()
        except OSError:
            return None
        git_root = Path(exec_path).parents[2]
        for candidate in (git_root / "bin" / "bash.exe", git_root / "usr" / "bin" / "bash.exe"):
            if candidate.exists():
                return str(candidate)
        return None
    return shutil.which("bash")


BASH = find_bash()

pytestmark = pytest.mark.skipif(
    not (BASH and all(p.exists() for p in (OPS_HUB / "delivery_ops_hub", DOCTOR / "manifest_doctor",
                                           JOB_WATCH / "job_watch", TRIAGE_PYTHON))),
    reason="bash, job-watch, delivery-ops-hub, manifest-doctor and ai-triage (with its .venv) must sit "
           "next to delivery-desk")

PY = sys.executable
GOOD = "import shutil, sys; shutil.copytree(sys.argv[1], sys.argv[2])"
BAD = ("import shutil, sys, pathlib; shutil.copytree(sys.argv[1], sys.argv[2]); "
       "pathlib.Path(sys.argv[2], 'Reel01', 'b.mov').write_bytes(b'picture B')")   # same size, wrong content
FAILS = "import sys; sys.exit(5)"
WITH_OWN_LIST = ("import hashlib, shutil, sys, pathlib; shutil.copytree(sys.argv[1], sys.argv[2]); "
                 "files = sorted(p for p in pathlib.Path(sys.argv[2]).rglob('*') if p.is_file()); "
                 "pathlib.Path(sys.argv[3]).write_text(''.join(hashlib.md5(p.read_bytes()).hexdigest() + '  ' + "
                 "p.relative_to(sys.argv[2]).as_posix() + chr(10) for p in files))")


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    (root / "Reel01").mkdir(parents=True)
    (root / "Reel01" / "a.mov").write_bytes(b"picture a")
    (root / "Reel01" / "b.mov").write_bytes(b"picture b")
    return root


@pytest.fixture
def env():
    environment = dict(os.environ, PYTHON=PY, JOB_WATCH_DIR=str(DESK.parent / "job-watch"),
                       MANIFEST_DOCTOR_DIR=str(DOCTOR), OPS_HUB_WEBHOOK_SECRET=SECRET)
    environment.pop("ANTHROPIC_API_KEY", None)   # never a real AI call from these tests
    return environment


def chain(tmp_path, env, url, options, copy_command, cwd=None):
    """Run the chain; returns (exit code, everything it printed)."""
    command = [BASH, str(SCRIPT), "--desk-config", str(settings(tmp_path, url)),
               "--watch-config", str(tmp_path / "no-job-watch.toml"),   # job-watch alerts off: n8n sees only the check
               "--lists-dir", str(tmp_path / "lists"), "--state-dir", str(tmp_path / "job-watch-state"),
               *options, "--", *copy_command]
    run = subprocess.run(command, cwd=cwd or tmp_path, env=env, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=300)
    return run.returncode, run.stdout + run.stderr


def standard(tmp_path, env, url, source, script=GOOD, name="Copy ShowA"):
    dest = tmp_path / "dest"
    code, out = chain(tmp_path, env, url, ["--name", name, "--source", str(source), "--dest", str(dest)],
                      [PY, "-c", script, str(source), str(dest)])
    return code, out, dest


def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*"))


def made_lists(tmp_path):
    return sorted((tmp_path / "lists").glob("*.md5")) if (tmp_path / "lists").exists() else []


def reports(tmp_path):
    return sorted((tmp_path / "reports").glob("report-*")) if (tmp_path / "reports").exists() else []


# --- The three outcomes ------------------------------------------------------------------------

def test_a_good_copy_is_checked_against_a_list_made_from_the_source(tmp_path, source, env, n8n):
    url, received = n8n
    code, out, dest = standard(tmp_path, env, url, source)
    assert code == 0, out
    assert [m["status"] for m in received] == ["CLEAN"]
    [listed] = made_lists(tmp_path)
    assert listed.read_text(encoding="utf-8").splitlines() == [
        f"{hashlib.md5(b'picture a').hexdigest()}  Reel01/a.mov",
        f"{hashlib.md5(b'picture b').hexdigest()}  Reel01/b.mov"]
    assert "Copy-ShowA" in listed.name


def test_a_bad_copy_is_caught_alerted_and_written_up(tmp_path, source, env, n8n):
    url, received = n8n
    code, out, dest = standard(tmp_path, env, url, source, script=BAD)
    assert code == 1, out
    assert [m["status"] for m in received] == ["PROBLEMS_FOUND"]
    [folder] = reports(tmp_path)
    assert "HASH_MISMATCH" in (folder / "incident-note.md").read_text(encoding="utf-8")


def test_a_failed_copy_is_not_checked_and_says_the_copys_exit_code(tmp_path, source, env, n8n):
    url, received = n8n
    code, out, dest = standard(tmp_path, env, url, source, script=FAILS)
    assert code == 4, out
    assert received == [] and reports(tmp_path) == []
    assert "exit code 5" in out


# --- The list comes first, and must be complete ------------------------------------------------

def test_the_list_is_made_before_the_copy_starts(tmp_path, source, env, n8n):
    # The copy deletes a source file as it goes: a list made afterwards would miss it, so the
    # check would pass. A list made first still has it, so the missing file is caught.
    url, received = n8n
    steal = ("import shutil, sys, pathlib; pathlib.Path(sys.argv[1], 'Reel01', 'b.mov').unlink(); "
             "shutil.copytree(sys.argv[1], sys.argv[2])")
    code, out, dest = standard(tmp_path, env, url, source, script=steal)
    assert code == 1, out
    assert [m["status"] for m in received] == ["PROBLEMS_FOUND"]


def test_if_no_complete_list_can_be_made_the_copy_never_starts(tmp_path, env, n8n):
    url, received = n8n
    empty = tmp_path / "empty-source"
    empty.mkdir()
    code, out, dest = standard(tmp_path, env, url, empty)
    assert code == 2, out
    assert not dest.exists() and received == [] and made_lists(tmp_path) == []


def test_the_source_is_never_changed(tmp_path, source, env, n8n):
    before = snapshot(source)
    standard(tmp_path, env, n8n[0], source)
    assert snapshot(source) == before


# --- When the copy method writes its own list ---------------------------------------------------

def test_the_copy_methods_own_list_is_used_and_none_is_made(tmp_path, source, env, n8n):
    url, received = n8n
    dest, own = tmp_path / "dest", tmp_path / "copy-tool.md5"
    code, out = chain(tmp_path, env, url, ["--name", "Copy ShowA", "--dest", str(dest), "--list", str(own)],
                      [PY, "-c", WITH_OWN_LIST, str(source), str(dest), str(own)])
    assert code == 0, out
    assert [m["status"] for m in received] == ["CLEAN"]
    assert made_lists(tmp_path) == []


def test_a_missing_own_list_after_the_copy_means_not_checked(tmp_path, source, env, n8n):
    url, received = n8n
    dest = tmp_path / "dest"
    code, out = chain(tmp_path, env, url,
                      ["--name", "Copy ShowA", "--dest", str(dest), "--list", str(tmp_path / "never-written.md5")],
                      [PY, "-c", GOOD, str(source), str(dest)])
    assert code == 2, out
    assert received == [] and "never-written.md5" in out


# --- Mistakes that are refused before anything runs ---------------------------------------------

@pytest.mark.parametrize("options, says", [
    (["--source", "{src}", "--dest", "{dest}"], "--name is needed"),
    (["--name", "x", "--dest", "{dest}"], "--source is needed"),
    (["--name", "x", "--source", "{src}"], "--dest is needed"),
    (["--name", "x", "--source", "{src}", "--dest", "{src}/inside"], "overlap"),
    (["--name", "x", "--source", "{tmp}/outer/source", "--dest", "{tmp}/outer"], "overlap"),
    (["--name", "x", "--source", "{src}", "--dest", "{dest}", "--lists-dir", "{dest}/lists"], "lists folder"),
    (["--name", "x", "--source", "{src}", "--dest", "{dest}", "--state-dir", "{dest}/state"], "state folder"),
])
def test_unsafe_or_incomplete_options_are_refused_before_anything_runs(tmp_path, source, env, n8n, options, says):
    url, received = n8n
    marker = tmp_path / "copy-ran"
    filled = [o.format(src=source, dest=tmp_path / "dest", tmp=tmp_path) for o in options]
    code, out = chain(tmp_path, env, url, filled, [PY, "-c", f"open({str(marker)!r}, 'w')"])
    assert code == 2, out
    assert says in out
    assert not marker.exists() and received == [] and made_lists(tmp_path) == []


def test_no_copy_command_is_refused(tmp_path, source, env, n8n):
    code, out = chain(tmp_path, env, n8n[0], ["--name", "x", "--source", str(source), "--dest", str(tmp_path / "d")], [])
    assert code == 2, out


def test_without_a_usable_python_it_stops_clearly(tmp_path, source, env, n8n):
    env = dict(env, PYTHON="no-such-python", PATH="")   # nothing else to fall back on
    code, out, dest = standard(tmp_path, env, n8n[0], source)
    assert code == 2, out
    assert "Python 3.11 or newer wasn't found" in out


# --- Passing on delivery-desk's own outcome ------------------------------------------------------

def test_an_alert_that_cant_be_delivered_is_reported(tmp_path, source, env):
    code, out, dest = standard(tmp_path, env, closed_url(), source)
    assert code == 3, out


# --- Fits into normal use -------------------------------------------------------------------------

def test_relative_paths_in_the_copy_command_still_work(tmp_path, source, env, n8n):
    url, received = n8n
    code, out = chain(tmp_path, env, url, ["--name", "Copy ShowA", "--source", "source", "--dest", "dest"],
                      [PY, "-c", GOOD, "source", "dest"], cwd=tmp_path)
    assert code == 0, out
    assert (tmp_path / "dest" / "Reel01" / "a.mov").exists()


def test_job_watch_files_never_land_in_the_working_folder(tmp_path, source, env, n8n):
    work = tmp_path / "work"
    work.mkdir()
    chain(tmp_path, env, n8n[0], ["--name", "Copy ShowA", "--source", str(source), "--dest", str(tmp_path / "dest")],
          [PY, "-c", GOOD, str(source), str(tmp_path / "dest")], cwd=work)
    assert list(work.iterdir()) == []
