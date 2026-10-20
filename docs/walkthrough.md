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

---

## Module 3: `check`, one command for stage 1

**In one sentence:** one command checks a delivery with your existing tools and, if problems are found, leaves a ready-to-fill working note in the report folder.

**Like this:** before, you'd run delivery-ops-hub (which runs manifest-doctor and sends the alert), then run ai-triage, then start writing notes from scratch. Now one command runs them in that order and starts the note for you:

```
python -m delivery_desk check "<delivery folder>" --manifest "<manifest file>"
```

1. **delivery-ops-hub runs exactly as it always does.** It checks with manifest-doctor, sends one alert to n8n and logs it, and you see its usual messages.
2. **If problems were found,** ai-triage writes its checked summary next to the report. It uses its own Python, because that's where the Claude library lives. Without an API key, it uses its code-written version.
3. **The working note** is written in the same report folder. The tool prints the exact `email` command to run once you've filled it in.

**When something's missing:**
- **The alert couldn't be delivered:** delivery-ops-hub keeps it in its outbox as before, and you still get your note.
- **ai-triage isn't set up:** the note says so, and everything else still happens.
- **The check couldn't run at all** (e.g. a wrong manifest path): there's no report, so there's no note, and you see delivery-ops-hub's explanation.
- **Clean or warnings-only deliveries:** the alert and log happen as usual, with no note.

**Settings:** `delivery-desk.toml` just says where delivery-ops-hub and ai-triage live. No secrets go in it.

**Tested by:** 18 more tests (51 in total).
- Nine run the **real** three tools on a tiny made-up delivery, with a stand-in for n8n, and never a real AI call.
- One goes end to end into your real n8n.
- Six protections were broken on purpose, and a test caught each one.
- A test also confirms **the delivery's files are never changed.**

## Module 4: the copy → verify → alert chain (`tools/copy-and-verify.sh`, 2026-10-20)

**In plain words:** one command does what used to be four steps by hand. It makes a fingerprint list of the source, runs the copy while job-watch keeps an eye on it, and as soon as the copy succeeds, checks the copy against the list. Then it sends the alert and writes the incident note if anything is wrong.

**Why it refuses so much up front:** every refusal is a way the check could quietly mean nothing. For example, a destination inside the source would put the copy into the very thing being listed.

**Why exit code 4 for a failed copy:** the copy's own code might be 1 or 2, which would look like "problems found" or "not checked". A separate number keeps "the copy failed" unmistakable for any automation that runs the chain.

**How it's tested:** the tests run the real script with fake copies, written as short Python commands: a good one, a bad one that changes a file, one that fails, and one that deletes a source file as it goes. The last one proves the list really is made before the copy.
