#!/usr/bin/env bash
# copy-and-verify: one command from "start the copy" to "checked, alerted, written up".
# (Approved by Georgi 2026-10-20: his automation answers Q2-Q4.)
#
#   bash tools/copy-and-verify.sh --name "Restore TAPE001" --source SRC --dest DEST -- <copy command>
#   bash tools/copy-and-verify.sh --name "Ingest ShowA" --dest DEST --list LIST -- <copy command that writes LIST>
#
# 1. The list. If the copy method writes its own checksum list, give it with --list. If not, a list
#    is made FROM THE SOURCE, before the copy starts (manifest-doctor make). A list made from the
#    copy afterwards would always agree with it, so it could never catch a bad copy.
# 2. The copy runs exactly as typed, under job-watch: alerts on finish, failure, stall and resume.
# 3. Only if the copy succeeded: delivery-desk check on the destination against the list, which
#    verifies, sends one alert and writes the incident note when there are problems.
#
# It never changes the source or the destination itself; only your copy command writes.
#
# Exit codes:
#   0  copied and checked: clean (or warnings only)
#   1  copied and checked: problems found; an incident note was written
#   2  not checked: a mistake in the options, no complete list, or the check couldn't run
#   3  checked, but the alert wasn't delivered, or delivery-desk's settings are wrong
#   4  the copy failed or was interrupted, so nothing was checked (job-watch has already alerted)

set -u

die() { echo "copy-and-verify: not checked: $1" >&2; exit 2; }

# Paths in a form both bash and Windows Python understand (Git Bash: D:/...; elsewhere as usual).
here() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }

SCRIPT_PATH="${BASH_SOURCE[0]//\\//}"                      # Windows-style \ as /
TOOLS_DIR="${SCRIPT_PATH%/*}"
[ "$TOOLS_DIR" = "$SCRIPT_PATH" ] && TOOLS_DIR="."         # run from inside tools/
DESK_DIR="$(here "$TOOLS_DIR/..")"
PROJECTS="$(here "$DESK_DIR/..")"

NAME="" SOURCE="" DEST="" LIST="" DESK_CONFIG="" WATCH_CONFIG="" LISTS_DIR="" STATE_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --) shift; break ;;
        --name|--source|--dest|--list|--desk-config|--watch-config|--lists-dir|--state-dir)
            [ $# -ge 2 ] || die "$1 needs a value"
            case "$1" in
                --name) NAME="$2" ;; --source) SOURCE="$2" ;; --dest) DEST="$2" ;; --list) LIST="$2" ;;
                --desk-config) DESK_CONFIG="$2" ;; --watch-config) WATCH_CONFIG="$2" ;;
                --lists-dir) LISTS_DIR="$2" ;; --state-dir) STATE_DIR="$2" ;;
            esac
            shift 2 ;;
        *) die "unknown option $1 (the copy command goes after --)" ;;
    esac
done
COPY=("$@")

[ -n "$NAME" ] || die "--name is needed (a name people will recognise, e.g. \"Restore TAPE001\")"
[ -n "$DEST" ] || die "--dest is needed (where the copy goes)"
[ -n "$SOURCE" ] || [ -n "$LIST" ] || die "--source is needed, to make the list from (or --list, if the copy method writes one)"
[ ${#COPY[@]} -gt 0 ] || die "the copy command is missing: put it after --"

# A Python 3.11 or newer. (On Windows "python3" can be a shop shortcut that isn't Python at all.)
PY=""
for candidate in "${PYTHON:-}" python3 python; do
    [ -n "$candidate" ] || continue
    if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
        PY="$candidate"; break
    fi
done
[ -n "$PY" ] || die "Python 3.11 or newer wasn't found (set PYTHON to its path)"

JOB_WATCH_DIR="${JOB_WATCH_DIR:-$PROJECTS/job-watch}"
if [ -z "${MANIFEST_DOCTOR_DIR:-}" ]; then
    for folder in "$PROJECTS/manifest-doctor" "$PROJECTS/delivery-verify"; do   # its GitHub and local names
        [ -d "$folder/manifest_doctor" ] && MANIFEST_DOCTOR_DIR="$folder" && break
    done
fi
[ -d "$JOB_WATCH_DIR/job_watch" ] || die "job-watch wasn't found at $JOB_WATCH_DIR (set JOB_WATCH_DIR)"
[ -d "${MANIFEST_DOCTOR_DIR:-}/manifest_doctor" ] || die "manifest-doctor wasn't found next to delivery-desk (set MANIFEST_DOCTOR_DIR)"

DESK_CONFIG="${DESK_CONFIG:-$DESK_DIR/delivery-desk.toml}"
WATCH_CONFIG="${WATCH_CONFIG:-$JOB_WATCH_DIR/job-watch.toml}"
LISTS_DIR="${LISTS_DIR:-$DESK_DIR/chain-lists}"
STATE_DIR="${STATE_DIR:-$JOB_WATCH_DIR}"

# Refuse folder layouts that would make the check meaningless or pollute it.
"$PY" - "$SOURCE" "$DEST" "$LISTS_DIR" "$STATE_DIR" <<'PYCHECK' || exit 2
import sys
from pathlib import Path
source, dest, lists, state = (Path(p).resolve() if p else None for p in sys.argv[1:])
def inside(a, b):
    return a is not None and b is not None and (a == b or a.is_relative_to(b))
problems = []
if inside(dest, source) or inside(source, dest):
    problems.append("the source and the destination overlap; the copy would land in what is being listed")
if inside(lists, source) or inside(lists, dest):
    problems.append("the lists folder is inside the source or the destination; it would change what is checked")
if inside(state, dest):
    problems.append("the job-watch state folder is inside the destination; it would appear as extra files")
for problem in problems:
    print(f"copy-and-verify: not checked: {problem}", file=sys.stderr)
sys.exit(1 if problems else 0)
PYCHECK

# --- 1. The list --------------------------------------------------------------------------------
if [ -z "$LIST" ]; then
    LIST="$LISTS_DIR/${NAME//[^A-Za-z0-9._-]/-}-$(date +%Y%m%d-%H%M%S).md5"
    echo "copy-and-verify: 1/3 making the list from the source, before the copy..."
    PYTHONPATH="$MANIFEST_DOCTOR_DIR" "$PY" -m manifest_doctor make "$SOURCE" --out "$LIST" \
        || die "no complete list could be made from the source, so the copy was not started"
else
    echo "copy-and-verify: 1/3 using the copy method's own list: $LIST"
fi

# --- 2. The copy, watched -------------------------------------------------------------------------
echo "copy-and-verify: 2/3 copying, watched by job-watch..."
PYTHONPATH="$JOB_WATCH_DIR" "$PY" -m job_watch run --name "$NAME" --watch "$DEST" --config "$WATCH_CONFIG" \
    --status-dir "$STATE_DIR/job-watch-status" --log-dir "$STATE_DIR/job-watch-logs" -- "${COPY[@]}"
copied=$?
if [ $copied -ne 0 ]; then
    echo "copy-and-verify: the copy failed (exit code $copied), so nothing was checked." >&2
    exit 4
fi

# --- 3. The check, alert and write-up ---------------------------------------------------------------
[ -f "$LIST" ] || die "the copy finished, but the list $LIST wasn't found"
echo "copy-and-verify: 3/3 checking the copy against the list..."
PYTHONPATH="$DESK_DIR" "$PY" -m delivery_desk --config "$DESK_CONFIG" check "$DEST" --manifest "$LIST"
checked=$?
case $checked in
    0|1|3) exit $checked ;;
    *) die "delivery-desk couldn't check the copy (exit code $checked)" ;;
esac
