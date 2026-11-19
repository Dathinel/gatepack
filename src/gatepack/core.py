"""Shared types: findings, results, gate metadata and output formatting."""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable

#: Errors that mean "this input could not be read", reported as ERROR instead of a crash.
#: JSONDecodeError and UnicodeDecodeError are ValueErrors; Pillow's UnidentifiedImageError is an OSError.
INPUT_ERRORS = (OSError, ValueError, EOFError, zipfile.BadZipFile, subprocess.SubprocessError)

#: Gate requirements that are Python modules rather than executables on PATH.
REQUIREMENT_MODULES = {"Pillow": "PIL", "pypdf": "pypdf"}

#: Ordered from best to worst. A result takes the worst level among its findings.
LEVELS = ("PASS", "WARN", "FAIL", "ERROR")

#: Why a finding exists. "platform-rule" and "standard" findings quote a published document;
#: "heuristic" findings are thresholds we chose and document, so you can tune them.
BASES = ("platform-rule", "standard", "heuristic")


class GateError(Exception):
    """The gate could not run (missing tool, unreadable file, bad option). Reported as ERROR."""


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class Option:
    name: str
    type: Callable[[str], Any]
    default: Any
    help: str
    choices: tuple | None = None


@dataclass
class Finding:
    level: str
    code: str
    message: str
    basis: str = "heuristic"
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"unknown level {self.level!r}")
        if self.basis not in BASES:
            raise ValueError(f"unknown basis {self.basis!r}")

    def to_dict(self) -> dict:
        d = {"level": self.level, "code": self.code, "message": self.message, "basis": self.basis}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class Gate:
    """One check. `check(path, **options)` returns a list of findings and a dict of measurements."""

    id: str
    title: str
    summary: str
    category: str
    sources: tuple[Source, ...]
    check: Callable[..., tuple[list[Finding], dict]]
    options: tuple[Option, ...] = ()
    requires: tuple[str, ...] = ()

    def defaults(self) -> dict:
        return {o.name: o.default for o in self.options}

    def run(self, path: str, **options: Any) -> "Result":
        opts = self.defaults()
        unknown = set(options) - set(opts)
        if unknown:
            raise GateError(f"{self.id}: unknown option(s): {', '.join(sorted(unknown))}")
        opts.update({k: v for k, v in options.items() if v is not None})
        try:
            for k, v in opts.items():
                if isinstance(v, float) and not math.isfinite(v):
                    raise GateError(f"option {k} must be a finite number, got {v}")
            findings, measurements = self.check(path, **opts)
        except GateError as exc:
            findings, measurements = [Finding("ERROR", "gate-error", str(exc))], {}
        except INPUT_ERRORS as exc:  # unreadable or malformed input, a tool that failed to start
            findings, measurements = [Finding("ERROR", "unreadable-input", f"{type(exc).__name__}: {exc}")], {}
        return Result(self, str(path), findings, measurements, opts)

    def missing_requirements(self) -> list[str]:
        """Requirements (executables or importable modules) that are not available here."""
        missing = []
        for req in self.requires:
            module = REQUIREMENT_MODULES.get(req)
            if module is not None:
                if importlib.util.find_spec(module) is None:
                    missing.append(req)
            elif shutil.which(req) is None:
                missing.append(req)
        return missing


@dataclass
class Result:
    gate: Gate
    target: str
    findings: list[Finding]
    measurements: dict
    options: dict

    @property
    def status(self) -> str:
        if not self.findings:
            return "PASS"
        return max((f.level for f in self.findings), key=LEVELS.index)

    def exit_code(self, strict: bool = False) -> int:
        s = self.status
        if s == "ERROR":
            return 2
        if s == "FAIL" or (strict and s == "WARN"):
            return 1
        return 0

    def to_dict(self) -> dict:
        from . import __version__

        return {
            "gatepack": __version__,
            "gate": self.gate.id,
            "target": self.target,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "measurements": self.measurements,
            "options": {k: v for k, v in self.options.items()},
            "sources": [{"title": s.title, "url": s.url} for s in self.gate.sources],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str)

    def to_text(self) -> str:
        lines = [f"{self.status}  {self.gate.id}  {self.target}"]
        if not self.findings:
            lines.append("  no issues found")
        for f in self.findings:
            tag = "" if f.basis == "heuristic" else f" [{f.basis}]"
            lines.append(f"  {f.level:<5} {f.code}: {f.message}{tag}")
        if self.measurements:
            shown = ", ".join(f"{k}={v}" for k, v in self.measurements.items() if not isinstance(v, (list, dict)))
            if shown:
                lines.append(f"  measured: {shown}")
        counts = {lv: sum(f.level == lv for f in self.findings) for lv in ("FAIL", "WARN")}
        lines.append(f"  result: {self.status} ({counts['FAIL']} fail, {counts['WARN']} warn)")
        lines.append("  rule sources:")
        lines.extend(f"    - {s.title}: {s.url}" for s in self.gate.sources)
        return "\n".join(lines)
