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
