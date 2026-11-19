# dead-air

**What it catches:** long silences in narration, podcasts and short videos: a gap inside the audio, a
slow silent start, a file that is silent throughout. A trailing silence longer than the limit is a WARN.

**Input:** any audio or video file ffmpeg can decode.

## Rule and source

Measured with the FFmpeg [silencedetect](https://ffmpeg.org/ffmpeg-filters.html#silencedetect) filter.
No platform publishes a dead-air rule, so the thresholds are **ours** (basis `heuristic`): in short-form
narration a 2-second gap reads as a mistake and a silent first second loses viewers. Change them per
project.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--max-gap` | 2.0 | longest allowed silence inside the file, seconds |
| `--max-lead` | 1.0 | longest allowed silence before the first sound, seconds |
| `--noise` | -50 | level counted as silence, dBFS |

## Known limits

- Music or room tone under a pause is not silence. For a voice-over, check the voice stem before mixing.
