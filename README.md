# Tamil Transcriber

Paste a YouTube link, get back the Tamil transcript, an English translation,
subtitle files and a short summary. The audio is transcribed on this Mac — no
API key, no per-video cost.

**How it works, and why.** Whisper listens to the audio once and writes it out
in English, then Claude renders that into Tamil. This looks like a detour, but
it was chosen after testing: Whisper Medium *understands* Tamil speech well, and
spells it badly. On a real 6-minute sermon, asking Whisper for Tamil directly
gave 218 words at 38 per minute, riddled with stray English fragments; going via
English gave 365 words at 63 per minute, in clean Tamil script with no English
at all — and took 5 minutes instead of 33.

The trade-off: you get **fluent Tamil that carries the meaning**, not the
speaker's exact original words. For reading and understanding, that is the
better result. If you need the literal words, switch **Tamil style** to
*Verbatim* and read the caveat further down.

---

## First time only

Double-click **`setup.command`**.

It creates a private Python environment, installs `yt-dlp` and Whisper, and
downloads the Whisper *medium* model. The model is about **1.5 GB**, so this
step takes a while on a slow connection. You only ever do it once.

## Every time after that

Double-click **`start.command`**.

A Terminal window opens and your browser goes to
<http://127.0.0.1:8756>. Leave the Terminal window open while you work —
closing it stops the app. Press **Control-C** in that window to stop.

---

## Using it

1. Paste a YouTube link.
2. Pick a model (Medium is the default and the right choice most of the time).
3. Leave **Tamil style** on *Fluent* unless you specifically need Whisper's own
   literal Tamil. Untick **Summary** if you don't want it.
4. Press **Transcribe** and wait. The progress bar shows the real position in
   the audio, so it is honest about how long is left.

When it finishes you get buttons for each file:

| File | What it is |
|---|---|
| **Tamil** | `tamil.txt` — readable Tamil paragraphs, written by Claude |
| **English** | `english.txt` — what Whisper actually heard. The most faithful record |
| **Summary** | `summary.md` — a few bullet points in Tamil and English |
| **Tamil .srt** | subtitle file with timings, for a video player or YouTube |
| **English .srt** | the same, in English |

Everything is kept in the `data/` folder, one folder per video, and stays
listed in the app until you delete it. Restarting the app does not lose them.

---

## How long does it take?

**Measured on this Mac** (M1, 8 GB, Medium, Fluent mode): a 5m 46s video took
**5.2 minutes** end to end — audio fetch, one Whisper pass, the Tamil, the
subtitles and the summary. That is roughly **1x real time**: budget about a
minute of waiting per minute of video.

| Video length | Roughly |
|---|---|
| 5 minutes | ~5 minutes |
| 30 minutes | ~30 minutes |
| 1 hour | ~1 hour |

Verbatim mode is **far slower** — the same video took 31 minutes. That is not
just the extra work: when Whisper produces poor Tamil, its own quality check
rejects the result and re-decodes the passage at higher temperatures, over and
over. Bad output costs more compute than good output.

| Model | Download | Tamil quality |
|---|---|---|
| Small | 500 MB | rough, but fine as the English source for Fluent mode |
| **Medium** | 1.5 GB | the sensible default |
| Large-v3 | 3.1 GB | best, but needs 3.1 GB free and is 2-3x slower *(untested here)* |

Large-v3 has **not** been tested on this machine — there was not enough free
disk. It matters far less in Fluent mode anyway, since Claude writes the Tamil
and Whisper only has to produce good English.

## Things worth knowing

- **One video at a time.** If you submit several, they queue. That is
  deliberate — two Whisper runs at once will not fit in 8 GB of RAM.
- **The audio file is deleted** once the transcript is written, because disk
  space on this Mac is tight. Only the text is kept.
- **The summary uses the `claude` command** already installed here. If it
  isn't found, the transcript still completes and the app tells you the
  summary was skipped.
- **Clear speech transcribes well; heavy background music does not.** Whisper
  is at its weakest on songs and on several people talking over each other.
- **The Tamil is a translation, not a transcription.** In Fluent mode the Tamil
  is written by Claude from Whisper's English. It reads well and carries the
  meaning, but it is not word-for-word what the speaker said. When a passage
  matters, check `english.txt` — that is the closest record of the actual audio.
- **Verbatim mode exists but is genuinely rough.** On the sermon it was tested
  against, Whisper's own Tamil dropped about half the words and mixed English
  fragments into the script. Use it only when literal wording matters more than
  readability, and expect to correct it by hand.
- **Subtitle timings are Whisper's**, taken from the audio, so they stay in sync
  even though the Tamil words are Claude's. If a subtitle line ever comes back
  untranslated it stays in English rather than shifting every later line.
- **Whisper occasionally repeats a phrase** on long or silent stretches. If a
  transcript loops, re-running with Large-v3 usually fixes it.
- **Long videos are fine**, but the summary only reads the first ~60,000
  characters of the transcript, which is around two hours of speech.

## If something goes wrong

- **"That does not look like a YouTube link."** — the box needs a real
  `youtube.com` or `youtu.be` address.
- **"This video is not available"** — private, deleted, members-only or
  region-blocked. Nothing to fix on this end.
- **A job stops with an error** — the message on the card is the actual cause.
  Delete the card and try again.
- **`yt-dlp` stops working after a few months** — YouTube changes things and
  `yt-dlp` has to catch up. Update it:

```bash
./.venv/bin/pip install --upgrade yt-dlp
```

---

## What's in here

```
setup.command    run once — installs everything
start.command    run each time — starts the app
server.py        the local web server and job queue
pipeline.py      download → transcribe → translate → summarise
web/             the page you see in the browser
data/            finished transcripts, one folder per video
.venv/           the private Python environment (created by setup)
```

## What leaves this Mac

Worth being precise about, because it is easy to assume "local" means "nothing
goes anywhere":

- **The audio never leaves.** It is downloaded, transcribed by Whisper on this
  machine, and deleted afterwards.
- **The transcript text does leave.** Claude writes the Tamil and the summary,
  so the transcribed text is sent to Claude through the `claude` command already
  installed here. If that is not acceptable for a particular video, switch
  **Tamil style** to *Verbatim* and untick **Summary** — that path is fully
  offline, at the cost of much rougher Tamil.
- `yt-dlp` contacts YouTube to fetch the video, and the model downloads once.

Every Claude call runs with its tools switched off, so a transcript cannot cause
anything to be read or written on this machine.
