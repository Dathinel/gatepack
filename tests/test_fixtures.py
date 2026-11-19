"""Every gate must PASS each file in fixtures/<gate>/pass and FAIL each file in fixtures/<gate>/fail.

An optional fixtures/<gate>/warn folder holds files that must end as WARN.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import gatepack

FIXTURES = Path(__file__).parent / "fixtures"
# CI sets GATEPACK_REQUIRE_TOOLS=1 so a missing ffmpeg fails the run instead of skipping media tests.
STRICT = os.environ.get("GATEPACK_REQUIRE_TOOLS") == "1"


def cases():
    for gate_dir in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        for kind in ("pass", "warn", "fail"):
            for f in sorted((gate_dir / kind).glob("*")):
                if f.is_file() and not f.name.endswith(".args.json") and f.name != ".gitkeep":
                    yield pytest.param(gate_dir.name, kind, f, id=f"{gate_dir.name}/{kind}/{f.name}")


@pytest.mark.parametrize("gate_id, kind, path", list(cases()))
def test_fixture(gate_id, kind, path):
    gate = gatepack.get(gate_id)
    missing = gate.missing_requirements()
    if missing:
        if STRICT:
            pytest.fail(f"{gate_id} needs {', '.join(missing)}")
        pytest.skip(f"{', '.join(missing)} not installed")
    sidecar = Path(f"{path}.args.json")
    args = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    result = gate.run(str(path), **args)
    assert result.status == kind.upper(), result.to_text()


@pytest.mark.parametrize("gate_id", sorted(gatepack.all_gates()))
def test_every_gate_has_pass_and_fail_fixtures(gate_id):
    for kind in ("pass", "fail"):
        files = [f for f in (FIXTURES / gate_id / kind).glob("*") if not f.name.endswith(".args.json") and f.name != ".gitkeep"]
        assert files, f"{gate_id} needs at least one fixture in tests/fixtures/{gate_id}/{kind}/"
