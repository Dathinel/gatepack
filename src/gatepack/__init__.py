"""gatepack: check-before-you-publish gates for KDP books and short videos."""
from __future__ import annotations

__version__ = "0.1.0"

from .core import Finding, Gate, GateError, Option, Result, Source  # noqa: E402
from .gates import all_gates, get  # noqa: E402


def check(gate_id: str, path: str, **options) -> Result:
    """Run one gate on one file: `gatepack.check("loudness", "clip.mp4", profile="podcast")`."""
    return get(gate_id).run(path, **options)


__all__ = ["Finding", "Gate", "GateError", "Option", "Result", "Source", "all_gates", "check", "get", "__version__"]
