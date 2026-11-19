"""freeze: stretches where the picture does not change (stuck render, missing clip, held frame).

Uses ffmpeg's freezedetect filter. The limit is ours, not a platform rule: a still frame longer than
2 s in a short video usually means a broken render. Slideshows and deliberate holds need a higher limit.
"""
from __future__ import annotations

import re

from .._media import NUMBER, probe, run_ffmpeg
from ..core import Finding, Gate, GateError, Option, Source

FREEZEDETECT = Source("FFmpeg filters: freezedetect", "https://ffmpeg.org/ffmpeg-filters.html#freezedetect")

EVENT = re.compile(r"freeze_(start|end):\s*(" + NUMBER + r")(?![\w.])")


def check(path, max_freeze=2.0, noise=0.003):
    if max_freeze <= 0 or not 0 < noise < 1:
        raise GateError("max_freeze must be above 0 and noise between 0 and 1")
    info = probe(path)
    if not info["video"]:
        raise GateError("no video stream in this file")
    dur = info["duration"] or (info["video"]["duration"] or 0.0)
    r = run_ffmpeg(path, info["video"]["index"], ["-vf", f"freezedetect=n={noise}:d={max_freeze}"])
    spans, start = [], None
    for kind, value in EVENT.findall(r.stderr.decode("utf-8", "replace")):
        if kind == "start":
            start = float(value)
        elif start is not None:
            spans.append((start, float(value)))
            start = None
    if start is not None:
        spans.append((start, dur))
    out = []
    for s, e in spans:
        what = "the whole video" if s <= 0.05 and e >= dur - 0.1 else f"{s:.2f}-{e:.2f} s"
        out.append(Finding("FAIL", "frozen-picture", f"picture does not change for {e - s:.2f} s ({what}); "
                           f"limit {max_freeze:g} s", details={"start": round(s, 2), "end": round(e, 2)}))
    return out, {"duration_s": round(dur, 2), "frozen_spans": [[round(s, 2), round(e, 2)] for s, e in spans]}


GATE = Gate(
    id="freeze",
    title="Frozen picture",
    summary="Spans where the video frame stays the same for longer than a limit.",
    category="media",
    sources=(FREEZEDETECT,),
    check=check,
    options=(
        Option("max_freeze", float, 2.0, "longest allowed still picture, seconds"),
        Option("noise", float, 0.003, "freezedetect noise tolerance (0-1; higher ignores more grain)"),
    ),
    requires=("ffmpeg", "ffprobe"),
)
