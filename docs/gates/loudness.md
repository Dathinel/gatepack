# loudness

**What it catches:** audio that is far from its delivery loudness target, and true peaks that will clip
after encoding.

**Input:** any audio or video file ffmpeg can decode.

## Rules and sources

Measured with the FFmpeg [ebur128](https://ffmpeg.org/ffmpeg-filters.html#ebur128-1) filter
(integrated loudness per ITU-R BS.1770, true peak with oversampling).

| Profile | Target | Window | True peak | Source |
|---|---|---|---|---|
| `streaming` (default) | -14 LUFS | +/-2 LU (ours) | -1 dBTP | [Spotify: Loudness normalization](https://support.spotify.com/us/artists/article/loudness-normalization/): "We adjust tracks to -14 dB LUFS"; "Keep it below -1dB TP" |
| `podcast` | -16 LUFS | +/-1 LU | -1 dBTP | [Apple Podcasts: Audio requirements](https://podcasters.apple.com/support/893-audio-requirements): "-16 dB LKFS, with a +/- 1 dB tolerance"; true peak that "doesn't exceed -1 dB FS" |
| `broadcast` | -23 LUFS | +/-0.5 LU | -1 dBTP | [EBU R 128](https://tech.ebu.ch/publications/r128) |

Short-video platforms do not publish a loudness target. The `streaming` profile is a common choice for
them, which is why its window is wider and marked as ours.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--profile` | streaming | streaming, podcast or broadcast |
| `--target` | from profile | override, LUFS |
| `--tolerance` | from profile | override, LU |
| `--max-true-peak` | from profile | override, dBTP |

Findings are marked `platform-rule` for `podcast`, `standard` for `broadcast`, and `heuristic` for
`streaming` (the target is Spotify's, the window and its use for short video are ours) or whenever you
override a value.
