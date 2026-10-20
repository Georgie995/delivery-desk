# Decisions

Each entry records the decision, the alternatives considered and why this one was chosen.

## 2026-10-11: Ideas C+E from the brainstorm, slim scope

- **Source:** chosen by Georgi from `research/ideas-backlog.md`. C is "my three tools working as one"; E is "explaining problems".
- **Slim scope (Georgi's choice):** check → working note → one alert → log.
  - **Parked:** filling manifest gaps (A) and the rename preview (B). Both change files, so each needs its own safety design.

## 2026-10-11: The reader is the operator, then the manager, never the client

- **What Georgi does:** "I work out the problem, relay it to my manager, and we write the client explanation."
- **Decision:** the tool makes two things: the operator's **working note** and a **manager email**.
  - **No client draft.** Outside-facing text stays with people (Georgi's choice).
- **The fix always comes from Georgi.** The tool never suggests one.

## 2026-10-11: Reuse ai-triage only; no new AI

- **Decision:** ai-triage's existing checked summary goes in the private part of the working note. The email is filled in by plain code from the report and Georgi's own words.
- **Rejected:**
  - A new AI step to polish Georgi's wording. It would need new checks that his cause and fix weren't changed, and another "live run pending".
  - No AI at all. That would lose the point of joining the three tools together.

## 2026-10-11: The working note is plain text with exact headings

- **Decision:** Markdown, which is plain text with `#` headings, editable in any text editor.
  - **Only exact, known headings count.** A renamed, missing or doubled heading is a tool error (exit 2) that names the heading. The tool doesn't guess where a section went.
- **Rejected:**
  - A JSON or TOML file: awkward to write paragraphs in by hand.
  - Guessing renamed headings: a wrong guess would put the wrong words in the email.

## 2026-10-11: "Empty" means blank or still starting with "(fill in"

- **Why:** the placeholder shows where to write, and the subject summary's placeholder carries a hint. Anything else counts as written, even one word, because it's Georgi's call.

## 2026-10-11: The private part starts with a heading, not a "---" line

- **Decision:** a `# For me only…` heading ends my sections.
- **Why not `---`:** Georgi might type `---` inside his own text. If that line were the divider, the rest of his section would be cut off without warning.

## 2026-10-11: Text from the report is data, never structure

- **Problem:** Linux file names can contain line breaks. A file named `clip.mov` + line break + `## When it happened` could fake one of Georgi's sections.
- **Decision:**
  - Control characters (line breaks, tabs and the Unicode line separators) from the report are **shown escaped**, as `\n`, so they can't start a new line.
  - File names sit in Markdown code formatting, with a fence longer than any backticks in the name.
  - The ai-triage summary is **quoted line by line** (`> `), so none of its lines can match a heading.
- **Tests:** a file name and an AI summary both try to fake a heading, and both fail.

## 2026-10-11: A NEEDS_HUMAN triage draft isn't shown

- **Why:** it failed its own checks against the report. Under pressure, a wrong summary is worse than none, so the note says to read the report itself.

## 2026-10-11: The problem section lists errors, then warnings; INFO is left out

- **Why:** INFO findings aren't problems, and they stay in the report. Errors come first because they're why the note exists.

## 2026-10-11: Up to 10 file names per probable cause

- **Why:** enough to start investigating, and the note stays readable. A line says how many more there are, and where to find them (report.json).

## 2026-10-11: Never overwrite a note or an email

- **Decision:** a second note becomes `incident-note-2.md`, and a second email `manager-email-2.txt`.
  - Files are opened in "create only" mode. The operating system refuses if the file already exists, so even two runs at the same moment can't overwrite each other.
- **Why:** Georgi may have edited the first one by hand.

## 2026-10-11: The email has no greeting or sign-off

- **Why:** Georgi adds his own when pasting. His sections are copied word for word.
  - **Subject format:** `Delivery issue: <summary> (PROBLEMS FOUND)`, Georgi's format. Line breaks in the summary become spaces, because a subject line can't contain them.
- **Edits to the check sections are used as written.** Georgi may reword "The problem" for his manager. The note is his document.

## 2026-10-11: The code file is `manager_email.py`, not `email.py`

- **Why:** Python has a built-in library called `email`. A file of the same name can be confused with it, so the clearer name avoids that.

## 2026-10-11: Notes saved by Notepad still work

- **Decision:** the note is read as UTF-8 and tolerates the invisible marker some editors put at the start (a "BOM").
  - **Windows line endings** are handled too.
  - **A note saved in another encoding** gets a clear error asking for UTF-8.

## 2026-10-11: Tests are checked by breaking the code on purpose

- **Why:** module 1's tests could only "fail first" because the code didn't exist yet. To prove they really protect something, 9 protections were broken one at a time:
  - escaping;
  - quoting;
  - hiding NEEDS_HUMAN drafts;
  - never overwriting;
  - email order;
  - the placeholder rule;
  - keeping private text out of the email;
  - refusing duplicate headings;
  - cutting long lists.

  A test failed every time.

## 2026-10-11: "The problem" keeps manifest-doctor's codes

- **Decision (Georgi's):** lines such as `DUPLICATE_ENTRY (error): 1 found` stay as they are. Georgi can reword them in the note before emailing.
- **Rejected:** a table of plain-English wordings for every code. It would be more to maintain, and it wasn't asked for.

## 2026-10-11: `--ask` writes into the same working note

- **Georgi asked for both ways of filling in:** by hand, and by being asked. Both write to the one note, so there's only ever one record of the incident.
- **Only empty sections are asked.** Text Georgi has written is never changed.
- **Rejected:** keeping typed answers in a separate file. That would create two records that could disagree.

## 2026-10-11: Each answer is saved the moment it's finished

- **Decision:**
  - The note is updated after every answer, by writing a temporary file next to it and swapping it in one step.
  - Stopping halfway (Ctrl-C, or closing the input) keeps every finished answer.
  - A crash mid-save leaves the old note whole.
- **Exit code after stopping:** 1, "sections still empty", not the usual Ctrl-C code (130). The `email` exit codes describe the state of the note, and that's what matters next.

## 2026-10-11: The note is read again before every question and every save

- **Why:** Georgi might fill in a section in his text editor while the tool is asking. If the section is no longer empty when it's time to save, his editor text is kept, the typed answer is dropped, and the tool says so.
- **Rejected:** merging the two texts. Guessing how to combine someone's words is worse than asking them to check.

## 2026-10-11: How an answer ends

- **Decision:**
  - An empty line finishes an answer, and pressing Enter straight away skips the section.
  - The subject summary is always one line.
- **Trade-off:** typed answers can't contain blank lines between paragraphs. For paragraphs, edit the note in a text editor.

## 2026-10-11: An answer line that looks like a heading is refused

- **Why:** a typed line such as `## How it happened` would create a second heading and break the note. The tool explains this and asks the same question again.

## 2026-10-11: Module 2 tests were checked by breaking the code on purpose

- **What was broken**, one at a time:
  - asking for filled sections;
  - overwriting text written in the editor meanwhile;
  - accepting heading-like lines;
  - not handling Ctrl-C;
  - never swapping in the temporary file;
  - never saving answers.
- **Result:** a test failed every time.

## 2026-10-11: `check` runs the other tools as separate programs

- **Decision:** delivery-desk runs `python -m delivery_ops_hub check …`, and through it manifest-doctor, then `python -m ai_triage draft …`, exactly as Georgi would by hand.
  - Their messages appear unchanged on screen.
  - delivery-ops-hub's exit code is passed on.
- **Why:** each tool keeps its own checks, alerts, outbox and "never silent" behaviour. ai-triage needs its own Python, because only its `.venv` has the Anthropic library. delivery-desk stays standard-library-only.
- **Rejected:** importing their code, as job-watch does with delivery-ops-hub's sender. Here the *whole* commands are wanted, not one part of them.

## 2026-10-11: The new report is found by comparing folders before and after

- **Decision:** the same approach delivery-ops-hub uses for manifest-doctor. The reports folder is read from delivery-ops-hub's own settings file, so it's never set twice.
- **Rejected:** reading the printed "Reports:" line. Printed text can change between versions.

## 2026-10-11: A working note only for PROBLEMS FOUND, even if the alert wasn't delivered

- **Decision:**
  - CLEAN, PASSED WITH WARNINGS and NOT CHECKED: no note (Georgi's answer at the design stage).
  - An undelivered alert is still a problem delivery: the note is written, delivery-ops-hub keeps the alert in its outbox, and the exit code stays 3.

## 2026-10-11: ai-triage is optional, and its absence is explained in the note

- **Decision:** if ai-triage isn't set up, its Python is missing, or it stops without writing a note, the note says why. Everything else carries on.
- **Settings:** `ai_triage_path` and `ai_triage_python` must be set together. Setting only one is a mistake, and the tool says so.

## 2026-10-11: delivery-desk's own settings errors exit with 3

- **Why:** this matches delivery-ops-hub, where 3 means "couldn't do the job: not delivered, or settings wrong". It keeps 2 meaning "NOT CHECKED" for `check`. This extends the approved design's exit code list, which is updated to match.
- **Settings:** unknown setting names are refused, so a typo is caught rather than silently ignored.

## 2026-10-11: The tests make real tool runs, but never a real AI call

- **Decision:** the joined-up tests run the real delivery-ops-hub, manifest-doctor and ai-triage on a tiny synthetic delivery. A stand-in web server plays n8n.
  - `ANTHROPIC_API_KEY` is always removed, so ai-triage uses its code-written fallback: no AI call and no cost.
  - The tests skip when the sibling repos aren't next to delivery-desk, e.g. in a fresh download.
  - One end-to-end test uses the real n8n when it's running.

## 2026-10-11: Module 3 tests were checked by breaking the code on purpose

- **What was broken**, one at a time:
  - a note written for clean deliveries;
  - no note when the alert wasn't delivered;
  - ai-triage run with the wrong Python;
  - delivery-ops-hub's exit code not passed on;
  - unknown settings accepted;
  - settings errors not exiting with 3.
- **Result:** a test failed every time.

## 2026-10-11: Engine additions for the Delivery Desk app

- **Context:** a desktop app (delivery-desk-app) now sits on top of this engine. The command line keeps its behaviour and tests.
- **A no-alerts route:** when the settings have no `ops_hub_path` (the app, when alerts aren't set up), `run_check` runs manifest-doctor directly into the reports folder, then ai-triage and the working note, exactly as before. It returns manifest-doctor's own code: 0, 1 or 2.
  - **It refuses `--out`,** because the reports folder is set by the settings. This is the same rule delivery-ops-hub applies.
  - **The command line's settings file is unchanged** and still always uses delivery-ops-hub.
- **Secrets handed over for one run:** `run_check(..., secrets=...)` lets the app pass the webhook secret and the AI key from Windows Credential Manager.
  - **Each tool sees only its own secret:** the webhook secret only for delivery-ops-hub, the AI key only for ai-triage, and manifest-doctor neither, even when the environment holds both.
  - **Why:** least privilege. A tool can't leak a secret it never had.
- **Progress:** no change was needed. delivery-ops-hub already passes extra options to manifest-doctor unchanged, so `--progress-file` reaches it on both routes, which a test confirms.
- **Tested by:**
  - 13 new tests, including ones that watch exactly which secrets each tool is started with;
  - 6 protections broken on purpose, each caught.
- **Known wording issue for the app:** when ai-triage isn't set up, the note says "not set up in delivery-desk.toml". The app has no such file. This will be handled when the app's screens are built.

## 2026-10-11: For the app: the full outcome, collected messages, no console windows, and Stop

- **Context:** the Delivery Desk app runs checks from a window. Planning its Checking screen showed three needs, plus one more:
  1. **No console windows.** A window app that starts command-line tools makes Windows flash a console window for each one, unless told not to.
  2. **Messages collected:** the app shows the tools' messages, such as "NOT DELIVERED … saved to the outbox", rather than losing them.
  3. **Stop really stops:** when alerts are on, delivery-ops-hub starts manifest-doctor as its own child program. On Windows, ending a program doesn't end the programs it started.
  4. **The app needs the report folder and the note,** not just an exit code.
- **Decision:**
  - `check(…, output=…, stop=…)` returns an `Outcome`: the exit code, report folder, result, note, and whether it was stopped.
  - **`run_check` is unchanged for the command line,** and still returns just the code.
  - **When `output` or `stop` is given:**
    - tools start with no console window;
    - their messages are read line by line in the background, so a chatty tool can't stall;
    - Stop ends the whole family of programs with Windows' own `taskkill /T`.
  - **Without them, tools run exactly as before.** A test holds this.
- **Stopping is safe:** every tool only reads the delivery. A stopped check returns code 130 ("interrupted"), with no report and no note.
- **Known limit:** on Linux and macOS, Stop ends the tool but not programs it started. The app is Windows-first.
- **Tested by:** 7 new tests, including a stand-in program that starts a child, to prove Stop ends both. 5 protections were broken on purpose, and each was caught.


## 2026-10-11: For the app: changing an answer on purpose

- **Context:** in the app, going Back to question 2 and changing the answer is a deliberate edit. The command line's `--ask` still uses `fill_section`, which only ever fills empty sections, so it can never clobber text typed in a text editor.
- **Decision:** `set_section` replaces the text under one of the email's seven sections (the two from the check and Georgi's five). Everything else in the note comes back exactly as it was.
  - **Clearing one of Georgi's sections** puts its "(fill in" placeholder back, so it counts as empty again and the email can't be made.
  - **The check's sections** can be reworded, but not emptied, because they go into the email.
  - **A line that looks like a heading** is refused, as with `--ask`.
  - **The private part** (probable causes, the ai-triage summary) can't be changed this way.
- **The app adds its own guard:** it saves only if the section still says what the app last read, so an edit made in a text editor meanwhile is never overwritten.
- **Wording:** "ai-triage is not set up in delivery-desk.toml" is now "ai-triage is not set up", because app users have no such file.
- **Tested by:** 5 new tests. 3 protections were broken on purpose, and each was caught.

## 2026-10-13: Stop now ends a tool's whole family on Linux and macOS too, and CI proves it

- **Found by an external reviewer:** `test_stop_ends_the_tool_and_any_program_it_started` failed on Linux. Stop ended the tool but not the programs it started, the limit noted in the 2026-10-11 entry. Worse, the test wasn't marked Windows-only, so anyone cloning on Linux or a Mac saw a failing suite. Linux matters here, because tape work runs on Linux.
- **Fix:**
  - on Linux and macOS, each tool starts in its own process group;
  - Stop signals the whole group: a polite request first, then a firm one if anything is still running after 5 seconds;
  - Windows keeps `taskkill /T`.
- **The test's own check was hardened:** on Linux, a stopped program can linger briefly as a "zombie" (finished, not yet tidied away). The test now counts that as stopped, not running.
- **CI (GitHub Actions):** the tests now run on GitHub's own Linux and Windows machines, with Python 3.11 and 3.13, after every push. That's how the Linux fix is proven, because the development PC is Windows-only. Tests that need the sibling repos or a running n8n skip themselves there.

## 2026-10-20: Tests run on GitHub after every push, and every Monday

- **Need:** Georgi asked which automations would genuinely improve the published tools (research in his private notes). The tests already ran on GitHub, but 18 joined-up tests skipped there because the sibling repos weren't present.
- **Options:** (a) leave as is; (b) fetch the siblings on every push; (c) fetch them on the weekly run only.
- **Decision (Georgi, 2026-10-20):** (b). **Sibling repos (Georgi's choice):** each run fetches the latest delivery-ops-hub, manifest-doctor (into `delivery-verify`) and ai-triage (with its own `.venv` holding the Anthropic library) next to this repo, so the joined-up tests run on GitHub too, not only on the development PC. A change in a sibling can turn this repo's tests red; that is the point.
  - **Every Monday at 06:00 UTC** the tests run again even if nothing was pushed, so a new Python version or a change in a sibling repo is noticed without anyone looking.
  - **Safety:** read-only permissions, no secrets (so no AI call is possible), and only GitHub's own official actions.
- **Known limits:**
  - GitHub pauses scheduled runs in a repo with no activity for 60 days.
  - **There's no n8n on GitHub,** so the one live end-to-end test skips there.
- **Tested by:** before pushing, each suite was run from fresh local clones laid out exactly as the workflow lays them out. A checker confirmed every workflow file follows the rules above, and each rule was broken on purpose once (write permission, no Monday run, a secret, a non-GitHub action, a wrong or missing sibling, the wrong machines); the checker caught every break. The workflow itself can only be fully proven on GitHub, by the first run after pushing.
