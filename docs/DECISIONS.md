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
