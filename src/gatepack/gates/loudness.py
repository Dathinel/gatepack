"""loudness: integrated loudness (LUFS) and true peak against a published delivery target.

Measured with ffmpeg's ebur128 filter (ITU-R BS.1770 / EBU R 128 meter).
"""
from __future__ import annotations

import re

from .._media import NUMBER, probe, run_ffmpeg
from ..core import Finding, Gate, GateError, Option, Source

EBUR128 = Source("FFmpeg filters: ebur128", "https://ffmpeg.org/ffmpeg-filters.html#ebur128-1")
SPOTIFY = Source("Spotify for Artists: Loudness normalization (-14 LUFS, true peak below -1 dB)",
                 "https://support.spotify.com/us/artists/article/loudness-normalization/")
APPLE = Source("Apple Podcasts for Creators: Audio requirements (-16 LKFS +/-1 dB, peak -1 dBFS)",
               "https://podcasters.apple.com/support/893-audio-requirements")
EBU = Source("EBU R 128: loudness normalisation (-23 LUFS)", "https://tech.ebu.ch/publications/r128")

# profile -> (target LUFS, tolerance LU, max true peak dBTP, basis note)
PROFILES = {
    "streaming": (-14.0, 2.0, -1.0, "Spotify normalizes to -14 LUFS; the +/-2 LU window is ours"),
    "podcast": (-16.0, 1.0, -1.0, "Apple Podcasts: -16 LKFS +/-1 dB"),
    "broadcast": (-23.0, 0.5, -1.0, "EBU R 128: -23 LUFS +/-0.5 LU"),
}

INTEGRATED = re.compile(r"I:\s+(" + NUMBER + r"|-inf)\s+LUFS")
PEAK = re.compile(r"True peak:\s+Peak:\s+(" + NUMBER + r"|-inf)\s+dB(?:FS|TP)")
LRA = re.compile(r"LRA:\s+(" + NUMBER + r")\s+LU")


def measure(path, stream):
    """(integrated LUFS, true peak dBTP, loudness range LU) from the ebur128 summary."""
    r = run_ffmpeg(path, stream, ["-af", "ebur128=peak=true"])
    log = r.stderr.decode("utf-8", "replace")
    if "Summary:" not in log:
        raise GateError("ffmpeg printed no ebur128 summary")
    summary = log[log.rfind("Summary:"):]
    i, p, lra = INTEGRATED.findall(summary), PEAK.findall(summary), LRA.findall(summary)
    if not i or not p:
        raise GateError("could not read integrated loudness and true peak from the ffmpeg summary")
    num = lambda v: -120.0 if v == "-inf" else float(v)  # noqa: E731
    return num(i[-1]), num(p[-1]), (float(lra[-1]) if lra else None)


def check(path, profile="streaming", target=None, tolerance=None, max_true_peak=None):
    if profile not in PROFILES:
        raise GateError(f"unknown profile {profile!r}; choose from {', '.join(PROFILES)}")
    p_target, p_tol, p_peak, note = PROFILES[profile]
    custom = target is not None or tolerance is not None or max_true_peak is not None
    target = p_target if target is None else target
    tolerance = p_tol if tolerance is None else tolerance
    max_true_peak = p_peak if max_true_peak is None else max_true_peak
    if tolerance < 0:
        raise GateError("tolerance must be 0 or more")
    audio = probe(path)["audio"]
    if not audio:
        raise GateError("no audio stream in this file")
    lufs, peak, lra = measure(path, audio["index"])
    # streaming: the -14 LUFS target is Spotify's, but the window and its use for video are ours
    basis = "heuristic" if custom or profile == "streaming" else ("platform-rule" if profile == "podcast" else "standard")
    out = []
    if lufs <= -70:
        out.append(Finding("FAIL", "silent", "no measurable programme loudness (silent file?)"))
    elif abs(lufs - target) > tolerance:
        word = "too quiet" if lufs < target else "too loud"
        out.append(Finding("FAIL", "integrated-loudness", f"{lufs:.1f} LUFS is {word}: target {target:g} +/- {tolerance:g} LU "
                           f"({profile}; {note})", basis, {"lufs": lufs, "target": target}))
    if peak > max_true_peak:
        out.append(Finding("FAIL", "true-peak", f"true peak {peak:.1f} dBTP is above {max_true_peak:g} dBTP", basis,
                           {"true_peak": peak}))
    return out, {"integrated_lufs": lufs, "true_peak_dbtp": peak, "loudness_range_lu": lra, "profile": profile,
                 "target_lufs": target, "tolerance_lu": tolerance}


GATE = Gate(
    id="loudness",
    title="Loudness",
    summary="Integrated loudness and true peak against Spotify/streaming, Apple Podcasts or EBU R 128 targets.",
    category="media",
    sources=(EBUR128, SPOTIFY, APPLE, EBU),
    check=check,
    options=(
        Option("profile", str, "streaming", "delivery target", tuple(PROFILES)),
        Option("target", float, None, "override the target, LUFS"),
        Option("tolerance", float, None, "override the allowed distance from the target, LU"),
        Option("max_true_peak", float, None, "override the true peak limit, dBTP"),
    ),
    requires=("ffmpeg", "ffprobe"),
)
