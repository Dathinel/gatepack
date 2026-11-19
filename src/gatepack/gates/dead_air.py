"""dead-air: long silences in a voice-over, podcast clip or short video.

Uses ffmpeg's silencedetect filter. There is no platform rule for this: the thresholds are ours,
chosen for short-form narration (a 2 s gap mid-video reads as a mistake). Tune them per project.
"""
from __future__ import annotations

import re

from .._media import NUMBER, probe, run_ffmpeg
from ..core import Finding, Gate, GateError, Option, Source

SILENCEDETECT = Source("FFmpeg filters: silencedetect", "https://ffmpeg.org/ffmpeg-filters.html#silencedetect")

EVENT = re.compile(r"silence_(start|end):\s*(" + NUMBER + r")(?![\w.])")


def silences(path, stream, noise_db, min_len):
    """Return [(start, end)] silent intervals of at least min_len seconds; end is None at end of file."""
    r = run_ffmpeg(path, stream, ["-af", f"silencedetect=noise={noise_db}dB:d={min_len}"])
    out, start = [], None
    for kind, value in EVENT.findall(r.stderr.decode("utf-8", "replace")):
        t = float(value)
        if kind == "start":
            start = max(0.0, t)
        else:
            out.append((start if start is not None else 0.0, t))
            start = None
    if start is not None:
        out.append((start, None))  # silence runs to the end of the file
    return out


def check(path, max_gap=2.0, max_lead=1.0, noise=-50.0):
    info = probe(path)
    if not info["audio"]:
        raise GateError("no audio stream in this file")
    dur = info["duration"] or (info["audio"]["duration"] or 0.0)
    if max_gap <= 0 or max_lead < 0:
        raise GateError("max_gap must be above 0 and max_lead 0 or more")
    found = silences(path, info["audio"]["index"], noise, max(0.05, min(max_gap, max_lead or max_gap, 0.5)))
    out: list[Finding] = []
    gaps = []
    for s, e in found:
        e = dur if e is None else e
        gaps.append({"start": round(s, 2), "end": round(e, 2), "length": round(e - s, 2)})
        if s <= 0.05 and e >= dur - 0.05:
            out.append(Finding("FAIL", "all-silent", f"the whole file is below {noise:g} dBFS"))
        elif s <= 0.05:
            if e > max_lead:
                out.append(Finding("FAIL", "silent-start", f"{e:.2f} s of silence before the first sound (limit {max_lead:g} s)"))
        elif e >= dur - 0.05:
            if e - s > max_gap:
                out.append(Finding("WARN", "silent-end", f"file ends with {e - s:.2f} s of silence"))
        elif e - s >= max_gap:
            out.append(Finding("FAIL", "dead-air", f"{e - s:.2f} s of silence at {s:.2f}-{e:.2f} s (limit {max_gap:g} s)",
                               details={"start": round(s, 2), "end": round(e, 2)}))
    longest = max((g["length"] for g in gaps), default=0.0)
    return out, {"duration_s": round(dur, 2), "longest_silence_s": longest, "silences": gaps}


GATE = Gate(
    id="dead-air",
    title="Dead air",
    summary="Silences longer than a limit inside the audio, plus silent starts and fully silent files.",
    category="media",
    sources=(SILENCEDETECT,),
    check=check,
    options=(
        Option("max_gap", float, 2.0, "longest allowed silence inside the file, seconds"),
        Option("max_lead", float, 1.0, "longest allowed silence before the first sound, seconds"),
        Option("noise", float, -50.0, "level counted as silence, dBFS"),
    ),
    requires=("ffmpeg", "ffprobe"),
)
