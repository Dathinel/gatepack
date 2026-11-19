# freeze

**What it catches:** a picture that stops changing: a stuck render, a missing clip replaced by a held
frame, a video exported with a still image track.

**Input:** a video file.

## Rule and source

Measured with the FFmpeg [freezedetect](https://ffmpeg.org/ffmpeg-filters.html#freezedetect) filter.
The 2-second limit is **ours** (basis `heuristic`). Slideshows and deliberate holds need a higher
`--max-freeze`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--max-freeze` | 2.0 | longest allowed still picture, seconds |
| `--noise` | 0.003 | freezedetect noise tolerance; raise it for grainy footage |
