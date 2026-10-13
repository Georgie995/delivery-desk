# delivery-desk

[![tests](https://github.com/Georgie995/delivery-desk/actions/workflows/tests.yml/badge.svg)](https://github.com/Georgie995/delivery-desk/actions/workflows/tests.yml) *Tests run on Linux and Windows after every change.*

One command takes a problem delivery from **check** to a **ready-to-fill incident note**. A second command turns my filled-in note into an **email for my manager**. It joins my three earlier tools into one flow, and **it never sends anything, never decides the cause or the fix, and never changes the delivery.**

**Prefer a window to the command line?** [ClearSum](https://github.com/Georgie995/clearsum) is the drag-and-drop desktop app built on this engine.

## The problem

When a delivery failed its check, the routine was always the same:
1. I worked out the problem.
2. I relayed it to my manager by email, so they were in the loop.
3. My manager and I wrote the client explanation together.

My tools each covered one piece:
- [manifest-doctor](https://github.com/Georgie995/manifest-doctor) checks a delivery and suggests probable causes;
- [delivery-ops-hub](https://github.com/Georgie995/delivery-ops-hub) sends one alert and logs every check in n8n;
- [ai-triage](https://github.com/Georgie995/ai-triage) writes a summary that's checked against the report.

But I still had to run them one by one, then retype the facts (which delivery, which manifest, what failed) into an email from a blank page.

## How it works

```
STAGE 1 (when the delivery is checked)              STAGE 2 (later, once I've investigated)
python -m delivery_desk check <folder> --manifest X   python -m delivery_desk email <note> [--ask]

1. delivery-ops-hub check                             1. reads my working note
   (manifest-doctor + one alert + n8n log)            2. any of my five sections empty?
2. ai-triage on the report                               → lists them, no email
   (code-written fallback without an API key)            (--ask: asks for just those, saving each answer)
3. PROBLEMS FOUND → working note in the report folder 3. writes manager-email.txt (never sends it)
```

**The working note** (`incident-note.md`) is plain text I can edit in any text editor:
- **Filled in from the check:** which delivery, and the problem.
- **Five sections only I can fill in:**
  - when it happened;
  - how it happened (the confirmed cause);
  - how we intend to fix it;
  - the most plausible way to do it;
  - a one-line subject summary.
- **A private part, never put in the email:** the check's probable causes with the affected file names, and ai-triage's summary.

**The email** has the subject line `Delivery issue: <my summary> (PROBLEMS FOUND)` and the six parts in my order. **My sections are copied word for word.**

**Safe by design:**
- **It never sends the email.** It writes a text file for me to paste.
- **It never changes the delivery.** The check is read-only, and a test confirms the files are untouched.
- **It never decides the cause or the fix.** The check's probable causes stay in my private part, marked "not verdicts".
- **It never overwrites.** A second note or email gets `-2` added to its name. With `--ask`, it only fills sections that are still empty, and re-reads the note first, so anything I wrote in a text editor meanwhile is kept. Each answer is saved straight away, in one safe step.
- **No new AI.** The only AI involved is ai-triage's existing, checked summary, and a draft that failed its checks isn't shown.
- **File names are data, not structure.** A Linux file name can contain a line break, and could otherwise fake one of my headings. Line breaks in names are shown as `\n`, and file names sit inside code formatting.
- **The other tools run exactly as they would by hand.** Their own alerts, outbox, messages and exit codes are unchanged.

## Example (real output, synthetic delivery; folder paths shortened)

A made-up delivery where one file is listed twice in the manifest, with two different checksums: a re-delivery overwrote the first version.

**Stage 1:**
```
> python -m delivery_desk check D:\Deliveries\show-a-ep01 --manifest D:\Deliveries\set1.md5
RESULT: PROBLEMS FOUND (2 errors, 0 warnings, 0 info)
  ERROR: 1 path is listed more than once in a manifest with different checksums. Only one version can exist at a path, so verification against the other entry will fail. Check which version was intended.
Reports: D:\Reports\report-2026-10-11_160742
PROBLEMS_FOUND: delivered to n8n (logged: True, alerted: True, alert mode: dry_run)
FALLBACK: triage note saved to D:\Reports\report-2026-10-11_160742\triage.md
  (AI not used: ANTHROPIC_API_KEY is not set)
[delivery-desk] Working note written: D:\Reports\report-2026-10-11_160742\incident-note.md
  Fill in its five "(fill in)" sections, then run:
    python -m delivery_desk email "D:\Reports\report-2026-10-11_160742\incident-note.md"
  (add --ask to be asked for them instead)
```

**Stage 2:** I answered the five questions with `--ask`, and it wrote `manager-email.txt`:
```
Subject: Delivery issue: clip_0004 overwritten on re-delivery (PROBLEMS FOUND)

The problem:
PROBLEMS FOUND: 2 errors, 0 warnings.
- DUPLICATE_ENTRY (error): 1 found
- HASH_MISMATCH (error): 1 found

Which delivery:
D:\Deliveries\show-a-ep01, checked against D:\Deliveries\set1.md5 at 2026-10-11 16:07

When it happened:
Delivered on 3 October. Re-delivered on 9 October, when the newer clip_0004.mov replaced the first one.

How it happened:
clip_0004.mov exists on two tapes with different content, and set1.md5 lists both versions.
Only one file can exist at that path, so the re-delivery overwrote the first version.

How we intend to fix it:
Re-deliver the first version under a different name, so both versions exist side by side.

Most plausible way to do it:
Restore it from tape 1, rename it clip_0004_v1.mov, upload it, and send a corrected
manifest listing both versions with their checksums.
```

The note's private part held the probable cause (`CAUSE_DUPLICATE_LISTING`, the file `ShowA/Reel01/clip_0004.mov`) and ai-triage's summary. Neither went into the email.

## Set-up

- **Requirements:** Python 3.11+, standard library only.
- **Run it:** `python -m delivery_desk …` from this folder. No install step is needed.
- **For `check`:**
  - **delivery-ops-hub,** set up as in its README. Its n8n workflow handles the alert and log, and it runs manifest-doctor.
  - **Optionally, ai-triage** with its own `.venv`.
  - Copy `delivery-desk.example.toml` to `delivery-desk.toml` and point it at both.
  - **No secrets in that file:** the webhook secret stays in `OPS_HUB_WEBHOOK_SECRET`, and the AI key stays in `ANTHROPIC_API_KEY`.
- **`email`** needs nothing else. It works on any working note.
- **Tests:**
  ```
  python -m pytest
  ```
  - **76 tests.** 58 run anywhere: the note, the email, `--ask`, the settings checks, the secrets rules and how tools are run.
  - **The joined-up tests** run the real delivery-ops-hub, manifest-doctor and ai-triage on a tiny synthetic delivery, with a stand-in for n8n. They run when those repos sit next to this folder. The AI key is always removed in the tests, so no AI call is ever made.
  - **One end-to-end test** uses a real, running n8n.
  - **The tests were checked by breaking the code on purpose:** 35 protections were broken one at a time, and a test failed every time.

## Exit codes

- **`check`** passes on delivery-ops-hub's own codes:
  - 0: clean or warnings;
  - 1: problems found, and a note was written;
  - 2: not checked;
  - 3: the alert wasn't delivered, or the settings are wrong.
- **`email`:**
  - 0: email written;
  - 1: sections still empty;
  - 2: the note is missing or its headings were changed.

## Why not just…

- **…write the email by hand, as before?** That's what this replaces. The facts were retyped from the report each time, and nothing made sure all five of my parts were there. Now the facts are filled in from the report, and the email can't be written while any of my sections is empty.
- **…have AI write the whole email?** My cause and my fix must reach my manager exactly as I wrote them. AI is used only where it's already checked (ai-triage), and only in my private part.
- **…use a ticketing system's incident form?** If a team has one, use it. This is for incidents reported by email. The note is plain text, so it can be pasted into a ticket too.

## Known limits

- **Developed and tested on Windows** with synthetic deliveries.
- **ai-triage's live AI run is still pending** (see its README). So far only its code-written fallback summary has appeared in a note.
- **One check at a time per reports folder.** The new report is found by comparing the folder before and after. Two checks writing to the same reports folder at the same moment could be confused.
- **Notes are only made for PROBLEMS FOUND.** A check that couldn't run has no report, so there's nothing to write a note about, but delivery-ops-hub's alert still says so.
- **Answers typed with `--ask` can't contain blank lines,** because an empty line finishes the answer. For paragraphs, edit the note in a text editor.
- **The note's headings must stay exactly as they are.** If one is renamed, the tool stops and names it rather than guessing.

## Documentation

- [DESIGN.md](docs/DESIGN.md)
- [DECISIONS.md](docs/DECISIONS.md)
- [walkthrough.md](docs/walkthrough.md): plain-English explanation of each part

All test data is synthetic. No client names, project or tape codes, hostnames or internal paths appear anywhere.

## AI assistance

The code in this repository was written with an AI coding assistant (Claude, by Anthropic). I did not write the Python by hand.

What I did:

- **The idea came from my own work:** how delivery incidents were actually handled. I diagnosed the problem, relayed it to my manager by email, and we wrote the client explanation together.
- **I set the requirements:**
  - **the content of the manager update, in my own words:** the problem, how it happened, which delivery, when, how we intend to fix it, and the most plausible way to do it;
  - **which parts come from the check and which only I can know;**
  - **"the fix always comes from me";**
  - **the email format and subject line;**
  - **a note only when problems are found;**
  - **no client draft and no new AI;**
  - **both ways of filling in the note:** by hand, or by being asked.
- **I approved the design** before any code was written, and answered its open questions. The decisions are logged in `docs/DECISIONS.md`.
- **I learned how it works** through a plain-English explanation of each part.

## Licence

[MIT](LICENSE) © 2026 Georgi Stoyanov
