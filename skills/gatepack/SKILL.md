---
name: gatepack
license: MIT
description: >
  Check a file before it is published or uploaded: KDP book metadata, paperback and hardcover covers,
  interior PDF page counts, EPUB files, and audio or video files (dead air, frozen picture, loudness,
  clipped ending). Use before telling the user that a book, cover, EPUB, podcast episode, reel, short
  or other video is ready to upload, and whenever the user asks to check, lint, validate or preflight
  such a file.
---

# gatepack: check before you publish

`gatepack` runs local checks ("gates") on a file and returns PASS, WARN, FAIL or ERROR with the rule's
source. It never uploads or logs in anywhere.

## Setup

```bash
gatepack --version || pip install "gatepack[cover]"
```

Audio and video gates need `ffmpeg` and `ffprobe` on PATH. Run `gatepack list` to see all gates.

## Which gate for which file

| File | Command |
|---|---|
| KDP listing (title, subtitle, description, keywords) | write them to `book.json` (fields: format, trim, title, subtitle, description, keywords), then `gatepack check kdp-metadata book.json --json` |
| Paperback or hardcover interior PDF | `gatepack check kdp-pagecount interior.pdf --trim 6x9 [--format hardcover] --json` |
| Full wrap cover | `gatepack check kdp-cover-safezone cover.png --trim 6x9 --pages N --json` (hardcover: `--format hardcover --spine IN`) |
| EPUB | `gatepack check epub book.epub --author "Name on the cover" --json` |
| Video or audio for social platforms | run `dead-air`, `freeze`, `loudness` and `tail` on the file |
| Podcast episode | `gatepack check loudness ep.mp3 --profile podcast --json` and `dead-air` |

## How to act on the result

1. Run every gate that fits the file, with `--json`.
2. `FAIL`: do not call the file ready. Fix it, or tell the user exactly which finding blocks it and why,
   quoting the `message` and the source URL.
3. `WARN`: report each warning to the user with its message; they decide. Covers often warn on
   decorative art near the edge, which is allowed for pictures but not for text.
4. `ERROR` (exit code 2): the gate could not run (missing ffmpeg, missing file, wrong option). Fix the
   setup and run it again; an ERROR is not a pass.
5. Never describe a PASS as a guarantee that the platform will accept the file. Say which gates passed.
