"""ffmpeg/ffprobe helpers shared by the audio and video gates. Standard library only.

Inputs are read with a file-only protocol whitelist, so a playlist or reference file cannot make
ffmpeg open network URLs. Every gate maps the same stream that `probe` describes.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from array import array
from pathlib import Path

from .core import GateError

#: A number as ffmpeg prints it in filter logs: 12, -0.5, 1e-06, 3.2E+01.
NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
INPUT_FLAGS = ["-protocol_whitelist", "file"]


def _tool(name: str) -> str:
    env = os.environ.get(f"GATEPACK_{name.upper()}")
    path = env or shutil.which(name)
    if not path:
        raise GateError(f"{name} not found on PATH (install ffmpeg, or set GATEPACK_{name.upper()})")
    return path


def media_path(path: str) -> str:
    """Absolute path of an existing file, so a name starting with '-' is never read as an option."""
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {path}")
    return str(p.resolve())


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise GateError(f"{Path(cmd[0]).name} timed out after {timeout} s") from exc
    except OSError as exc:
        raise GateError(f"could not start {cmd[0]}: {exc}") from exc


def run_ffmpeg(path: str, stream: int, filter_args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run ffmpeg on one input stream with output discarded; the filter logs are in stderr."""
    cmd = [_tool("ffmpeg"), "-hide_banner", "-nostdin", "-nostats", *INPUT_FLAGS, "-i", media_path(path),
           "-map", f"0:{stream}", *filter_args, "-f", "null", "-"]
    r = _run(cmd, timeout)
    if r.returncode != 0:
        raise GateError(f"ffmpeg failed: {r.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    return r


def probe(path: str) -> dict:
    """First audio and video stream: {'duration', 'audio': {...}|None, 'video': {...}|None}.

    Each stream dict has index, codec, channels (audio), start and end in seconds (end may be None).
    """
    cmd = [_tool("ffprobe"), "-v", "error", *INPUT_FLAGS, "-print_format", "json", "-show_format", "-show_streams",
           "-i", media_path(path)]
    r = _run(cmd, 120)
    if r.returncode != 0:
        raise GateError(f"ffprobe could not read the file: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    data = json.loads(r.stdout or b"{}")
    fmt_dur = _num(data.get("format", {}).get("duration"))
    out: dict = {"duration": fmt_dur or 0.0, "audio": None, "video": None}
    for s in data.get("streams", []):
        kind = s.get("codec_type")
        if kind not in ("audio", "video") or out[kind] is not None:
            continue
        if kind == "video" and s.get("disposition", {}).get("attached_pic"):
            continue  # cover art inside an audio file is not a video track
        start = _num(s.get("start_time")) or 0.0
        dur = _num(s.get("duration"))
        out[kind] = {"index": int(s["index"]), "codec": s.get("codec_name"), "channels": int(s.get("channels") or 1),
                     "start": start, "duration": dur, "end": start + dur if dur is not None else None}
    return out


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def decode_tail(path: str, stream: dict, seconds: float, rate: int = 16000) -> tuple[array, int]:
    """Decode the last `seconds` of an audio stream as interleaved 16-bit samples; returns (samples, channels)."""
    channels = max(1, min(int(stream.get("channels") or 1), 8))
    start = max(0.0, (stream["end"] - seconds)) if stream.get("end") is not None else None
    cmd = [_tool("ffmpeg"), "-hide_banner", "-nostdin", "-nostats", *INPUT_FLAGS]
    cmd += ["-ss", f"{start:.3f}"] if start is not None else ["-sseof", f"-{seconds}"]
    cmd += ["-i", media_path(path), "-map", f"0:{stream['index']}", "-ac", str(channels), "-ar", str(rate),
            "-f", "s16le", "-"]
    r = _run(cmd, 600)
    if r.returncode != 0:
        raise GateError(f"ffmpeg could not decode audio: {r.stderr.decode('utf-8', 'replace').strip()[-200:]}")
    samples = array("h")
    samples.frombytes(r.stdout[: len(r.stdout) // (2 * channels) * 2 * channels])
    return samples, channels


def rms_dbfs(samples, channels: int = 1, start: int = 0, end: int | None = None) -> float:
    """Loudest per-channel RMS level of frames[start:end] in dBFS (full-scale sine = -3 dBFS); -120 for silence."""
    frames = len(samples) // channels
    end = frames if end is None else min(end, frames)
    start = max(0, start)
    if end <= start:
        return -120.0
    best = 0.0
    for c in range(channels):
        chunk = samples[start * channels + c:end * channels:channels]
        best = max(best, sum(s * s for s in chunk) / len(chunk))
    if best <= 0:
        return -120.0
    return round(20 * math.log10(math.sqrt(best) / 32768.0), 1)


def times(pattern: str, text: str) -> list[float]:
    """All numbers that follow `pattern` (e.g. 'silence_start:') in ffmpeg log text."""
    return [float(v) for v in re.findall(re.escape(pattern) + r"\s*(" + NUMBER + r")(?![\w.])", text)]
