# Walkthrough

A plain-English explanation of each part, written for someone with no technical background.

---

## Module 1: the working note and the manager email

**In one sentence:** when a delivery check finds problems, the tool starts a notes page for you with the facts already filled in. Once you've written in what happened and how you'll fix it, it turns the page into a ready-to-paste email for your manager.

**Like this:** think of a paper incident form.
- The **top half** is pre-printed from the check: which delivery it was, and what's wrong (for example "2 errors: a file listed twice, a checksum mismatch").
- The **middle** has five blank boxes that only you can fill in:
  - when it happened;
  - how it happened;
  - what you'll do;
  - the best way to do it;
  - a one-line summary for the subject.
- The **bottom** is a tear-off strip for you only: the check's probable causes, the affected file names, and ai-triage's summary. It never goes to your manager.

When the boxes are filled, one command copies the top half and your boxes into an email file, in the order you asked for. If any box is still blank, it tells you which ones and makes no email.

**Things it is careful about:**
- **Your words go through unchanged.** No AI touches them, and no code rewrites them.
- **It never sends anything.** It writes a text file, and you paste it into an email.
- **It never overwrites.** A second email becomes `manager-email-2.txt`, so a copy you've edited is safe.
- **File names can't play tricks.** A file name containing a line break could pretend to be one of your boxes, so line breaks in names are shown as `\n` instead of being obeyed. The same applies to ai-triage's text.
- **If you rename a box's heading by accident,** it stops and tells you which heading to put back, rather than guessing.

**Tested by:** 25 automatic tests, using made-up reports. Nine protections were also broken on purpose, one at a time, to prove a test notices each one.

---

## Module 2: being asked for the empty boxes (`--ask`)

**In one sentence:** instead of opening the note in a text editor, you can let the tool ask you for each empty box in the terminal. It saves each answer into the note the moment you finish it.

**Like this:** a colleague holding the incident form asks, "When did it happen?" You answer, and they write it in straight away. Then they ask the next empty box. Boxes you've already filled in are skipped. If you get interrupted and walk off, everything you've already answered is on the form. Next time, they ask only for what's still blank.

**How you use it:**
```
python -m delivery_desk email "<path to incident-note.md>" --ask
```
- **Type your answer**, then press Enter on an empty line to finish it. The subject summary is one line.
- **Press Enter straight away** to skip a box for now.
- **When every box is filled**, the email is written straight after.

**Things it is careful about:**
- **It never changes what you've written.** It only fills boxes that are still empty.
- **If you fill a box in a text editor while it's asking,** it keeps your editor text, says so, and doesn't use the typed answer.
- **Saving is all-or-nothing.** It writes a temporary copy and swaps it in, in one step. A crash can't leave a half-written note.
- **It won't accept an answer line that looks like a heading** (e.g. `## How it happened`), because that would break the note. It asks again.

**Tested by:** 8 more automatic tests (33 in total). They include stopping halfway, pressing Ctrl-C, and editing the note while answering. Six protections were broken on purpose, and a test caught each one.
