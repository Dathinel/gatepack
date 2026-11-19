# tail

**What it catches:** an ending that is cut off. A clean ending decays to near silence; a cut ending still
has full-level sound in its last milliseconds (a word or note chopped by a trim or an export). The gate
also compares audio and video length, since audio that runs past the last frame gets cut by players.

**Input:** any audio or video file ffmpeg can decode.

## Rule and source

The last second is decoded with FFmpeg (`-sseof`, see [main options](https://ffmpeg.org/ffmpeg.html#Main-options))
and the RMS level of the final window is measured. Thresholds are **ours** (basis `heuristic`).

## Options

| Option | Default | Meaning |
|---|---|---|
| `--window-ms` | 20 | length of the final window, ms |
| `--max-end-level` | -40 | highest allowed RMS level in that window, dBFS |
| `--max-av-gap` | 0.5 | allowed audio/video length difference, seconds |

## Known limits

- A song that ends on a hard stop by design will fail; raise `--max-end-level` for it.
- Cuts in the middle of the file (a word ending trimmed before a pause) need the raw take for comparison.
  That is a planned extension.
