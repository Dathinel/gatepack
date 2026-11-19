"""tail: does the file end cleanly, or is the last word or note cut off?

A clean ending decays: the final milliseconds are near silence. A cut ending still carries full-level
sound in the last samples. The gate also compares audio and video lengths, because an audio track that
ends before or after the picture is the other common way an ending gets clipped. Thresholds are ours.
"""
from __future__ import annotations

from .._media import decode_tail, probe, rms_dbfs
from ..core import Finding, Gate, GateError, Option, Source

SSEOF = Source("FFmpeg main options (-ss, -sseof: reading the end of a stream)", "https://ffmpeg.org/ffmpeg.html#Main-options")
RATE = 16000


def check(path, window_ms=20.0, max_end_level=-40.0, max_av_gap=0.5):
    if window_ms <= 0 or max_av_gap < 0:
        raise GateError("window_ms must be above 0 and max_av_gap 0 or more")
    info = probe(path)
    a, v = info["audio"], info["video"]
    if not a:
        raise GateError("no audio stream in this file")
    samples, channels = decode_tail(path, a, 1.0, RATE)
    frames = len(samples) // channels
    if frames < RATE * 0.05:
        raise GateError("could not read at least 50 ms of audio at the end of the stream")
    n = max(1, int(RATE * window_ms / 1000))
    end_level = rms_dbfs(samples, channels, frames - n)
    body_level = rms_dbfs(samples, channels, 0, frames - n)
    out = []
    if end_level > max_end_level:
        out.append(Finding("FAIL", "cut-ending", f"the last {window_ms:g} ms are at {end_level:.1f} dBFS (limit {max_end_level:g}): "
                           "sound is cut off instead of fading out; add a tail or a short fade",
                           details={"end_level_dbfs": end_level}))
    measured = {"end_level_dbfs": end_level, "last_second_level_dbfs": body_level, "channels": channels}
    if v and a.get("end") is not None and v.get("end") is not None:
        diff = round(a["end"] - v["end"], 3)
        measured["audio_minus_video_s"] = diff
        if diff > max_av_gap:
            out.append(Finding("FAIL", "audio-past-picture", f"audio runs {diff:.2f} s past the last video frame; "
                               "players and platforms may cut it"))
        elif -diff > max_av_gap:
            out.append(Finding("WARN", "audio-ends-early", f"audio ends {-diff:.2f} s before the picture"))
    return out, measured


GATE = Gate(
    id="tail",
    title="Clipped ending",
    summary="Audio that stops at full level (cut word or note) and audio/video length mismatch at the end.",
    category="media",
    sources=(SSEOF,),
    check=check,
    options=(
        Option("window_ms", float, 20.0, "length of the final window that is measured, ms"),
        Option("max_end_level", float, -40.0, "highest allowed RMS level in the final window, dBFS"),
        Option("max_av_gap", float, 0.5, "allowed difference between audio and video length, seconds"),
    ),
    requires=("ffmpeg", "ffprobe"),
)
