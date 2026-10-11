# delivery-desk: design

Status: **Approved by Georgi on 2026-10-11.**

## 1. The problem (Georgi's words, from the kickoff)

When a delivery fails its check, the operator ("I", below) works out the problem, then relays it to the manager **by email**, "so she's in the loop, not for any other reason". After that, the operator and manager write the client explanation together, by hand.

My three published tools each cover one piece:
- **manifest-doctor** checks a delivery.
- **delivery-ops-hub** sends an alert and logs the check.
- **ai-triage** writes a checked summary.

Today I have to run them separately, then write the manager email from scratch.

**delivery-desk joins them into one flow** and helps me produce the manager email. It never decides the cause or the fix: **"the fix always comes from me."**

## 2. What it does: two stages, at different times

```
STAGE 1 (when the delivery is checked, automatic)        STAGE 2 (later, after I've investigated)
  python -m delivery_desk check <folder> --manifest X      python -m delivery_desk email <working note> [--ask]

  1. delivery-ops-hub check                                  1. reads the working note
     (= manifest-doctor + one alert + n8n log)               2. any of MY sections empty? →
  2. ai-triage draft on the report                              lists them and stops
     (its checked summary; code-written                         (or, with --ask, asks for just those,
      fallback without an API key)                               saving each answer into the note)
  3. if PROBLEMS FOUND: writes my WORKING NOTE               3. writes the MANAGER EMAIL
     next to the report                                         (subject + body) to a text file
```

**Words used in this document:**
- **Working note:** a plain text file (Markdown, which means plain text with `#` headings) that is my record of one incident. Some sections are filled in from the check. The others are left empty for me.
- **Manager email:** a text file containing a subject line and body, ready to paste into an email. **The tool never sends it.**

## 3. The working note (example, synthetic)

Written as `incident-note.md` inside the check's report folder, next to `report.json` and `triage.md`:

```markdown
# Incident note: show-a-ep01

How to use: write under each "(fill in)" heading, in any text editor, whenever you like.
Don't rename the headings. When all five are filled in, run:
    python -m delivery_desk email "<path to this file>"
Add --ask to be asked for the empty sections instead.

## Which delivery
D:/Incoming/show-a-ep01, checked against set1.md5 at 2026-10-11 14:02

## The problem
PROBLEMS FOUND: 2 errors, 0 warnings.
- HASH_MISMATCH: 2 files

## When it happened
(fill in)

## How it happened
(fill in)

## How we intend to fix it
(fill in)

## Most plausible way to do it
(fill in)

## Subject summary
(fill in: one line for the email subject, written once you know what went wrong)

---
Everything below is for me only and is not put in the email.

## Probable causes from the check (not verdicts)
- ERROR, CAUSE_DUPLICATE_LISTING: a file is listed twice with different checksums (1 file)

## ai-triage summary
FALLBACK: written by code from the report, because the AI could not be used (no API key).
<the summary text from triage.md>
Full triage note: triage.md
```

**Rules for the working note:**
- **Sections from the check** ("Which delivery", "The problem") are filled in by code, but they're mine to edit. I might reword "The problem" for my manager.
- **My five sections** start as "(fill in)":
  - When it happened: when the problem *occurred*, not when the check ran.
  - How it happened: the confirmed cause, which I decide after investigating.
  - How we intend to fix it.
  - Most plausible way to do it.
  - Subject summary: one line for the email subject, e.g. "duplicate file overwritten on S3".

  A section still starting with "(fill in)", or left blank, counts as empty.
- **Probable causes and the ai-triage summary** help me investigate. They stay in the note and **are not copied into the email**, because the email has exactly the six parts I listed.
- **File names from the delivery are shown as data** (inside code formatting). A file named like an instruction is never acted on.

## 4. The manager email (example, synthetic)

Written as `manager-email.txt` next to the working note:

```
Subject: Delivery issue: <my subject summary> (PROBLEMS FOUND)

The problem:
PROBLEMS FOUND: 2 errors, 0 warnings.
- HASH_MISMATCH: 2 files

Which delivery:
D:/Incoming/show-a-ep01, checked against set1.md5 at 2026-10-11 14:02

When it happened:
<my text, exactly as written>

How it happened:
<my text, exactly as written>

How we intend to fix it:
<my text, exactly as written>

Most plausible way to do it:
<my text, exactly as written>
```

- **My sections are copied word for word.** No AI touches them, and no code rewrites them.
- **The subject line follows Georgi's format:** `Delivery issue: <subject summary> (PROBLEMS FOUND)`. An email subject can't contain line breaks, so any line breaks in the summary become spaces. The delivery name is in the body. I can include it in the summary if I want.
- **No greeting or sign-off.** I add my own when I paste it into the email.
- **It never overwrites an earlier email.** A second run writes `manager-email-2.txt`.

## 5. How it reuses the three tools

delivery-desk **runs the other tools as separate programs**, exactly as I'd run them by hand. It doesn't import their code:

| Step | What runs | Why this way |
|---|---|---|
| Check + alert + log | `python -m delivery_ops_hub check <folder> <manifest-doctor options>` | It keeps its own alert, log, outbox and "never silent" behaviour unchanged. delivery-desk finds the new report folder by comparing the reports folder's contents before and after. |
| Summary | `ai-triage`'s own Python: `python -m ai_triage draft <report folder>` | ai-triage needs the Anthropic library, which lives only in its own `.venv`. A separate program keeps delivery-desk standard-library-only. |

This is different from job-watch, which imported delivery-ops-hub's sender. Here I want the **whole commands** unchanged, not just one part of them.

**If a step can't run, the rest still happens, and the note says what was missing:**
- **The alert wasn't delivered:** delivery-ops-hub already saves it to its outbox and says so. delivery-desk still writes the working note.
- **ai-triage isn't set up, or fails:** the working note says "ai-triage summary not available (reason)". Everything else is unchanged.
- **The check itself couldn't run** (NOT CHECKED, or delivery-ops-hub's settings or secret are missing): there's no report, so there's nothing to write a note about. delivery-desk shows delivery-ops-hub's message and stops with its exit code.

## 6. Settings: `delivery-desk.toml` (git-ignored, with an example file committed)

```toml
ops_hub_path = "C:/path/to/delivery-ops-hub"
ops_hub_config = "C:/path/to/delivery-ops-hub/ops-hub.toml"   # its reports folder, webhook, etc. are reused
ai_triage_path = "C:/path/to/ai-triage"                        # optional
ai_triage_python = "C:/path/to/ai-triage/.venv/Scripts/python.exe"
```

No secrets go in this file. The webhook secret stays in `OPS_HUB_WEBHOOK_SECRET`, and the AI key stays in `ANTHROPIC_API_KEY`, exactly as before.

## 7. Safety rules

- **It never sends the manager email.** It only writes a text file.
- **It never changes the delivery.** The check is read-only; that's manifest-doctor's rule, unchanged.
- **With `--ask`, it only fills sections that are empty.** It never changes text I've written. Each answer is saved straight away, written safely (to a temporary file that then replaces the note), so stopping halfway loses nothing and can't corrupt the note.
- **It won't produce a half-finished email.** Any empty section means no email, plus a list of what's missing.
- **No new AI code.** The only AI involved is ai-triage's existing, checked summary, and it stays in my private section.
- **Synthetic data only**, in the tests and the docs.

## 8. Exit codes

The exit code is the number a program reports when it ends, so other automation can react to it.
- **`check`:** passes on delivery-ops-hub's own codes:
  - 0: clean or warnings;
  - 1: problems found, and a working note was written;
  - 2: not checked;
  - 3: the alert wasn't delivered, or delivery-ops-hub's settings are wrong.
- **`email`:**
  - 0: email written;
  - 1: sections still empty;
  - 2: tool error (the note is missing, or its headings were renamed or removed).

## 9. Testing plan (tests written first, synthetic data only)

- **Note and email logic:** tested on its own, with small synthetic `report.json` files built by the tests. This needs none of the other repos.
- **`--ask`:** answers are fed in as if typed. Tests check:
  - only empty sections are asked;
  - written text is untouched;
  - quitting halfway keeps the answers already given.
- **The joined-up flow:** runs the real delivery-ops-hub, manifest-doctor and ai-triage on a synthetic delivery, with a small stand-in web server playing n8n. These tests are skipped if the sibling repos aren't next to delivery-desk. One end-to-end test runs against the real n8n when it's running.

## 10. Build order

1. **Module 1:** the working note and email from a report (`note.py`, `email.py`), plus the `email` command.
2. **Module 2:** `--ask`, the guided questions.
3. **Module 3:** `check`, joining delivery-ops-hub and ai-triage into stage 1.
4. **Module 4:** README, safety search, clean-copy test, publish, and the end-of-project quiz.

## 11. Not in this version (parked, with reasons)

- **A (fill manifest gaps) and B (rename preview):** they change files, so each needs its own safety design. Parked at the kickoff.
- **A client explanation draft:** outside-facing text stays with me and my manager.
- **New AI for polishing my wording:** my cause and fix go to my manager exactly as I wrote them.
- **A list of open incidents:** not asked for. It can be added later if it's useful.

## 12. Open questions for Georgi

1. **"How we intend to fix it" and "most plausible way to do it":** **answered, two separate sections.**
   - *How we intend to fix it* is **what** will be done, e.g. "re-deliver the newer file under a different name".
   - *Most plausible way to do it* is **how** best to do it, e.g. "copy it from tape 2, rename it with a version suffix, upload it with a note listing both versions".
2. **A note only for PROBLEMS FOUND:** **answered, yes.** There's no note for CLEAN or PASSED WITH WARNINGS, and none for NOT CHECKED, because there's no report.
3. **The email subject line:** **answered.** The format is `Delivery issue: <subject summary> (PROBLEMS FOUND)`. I write the summary myself (option a), as a fifth section in the working note.
