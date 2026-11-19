"""Contract every gate must meet: metadata, sources, docs page, options with help text."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import gatepack
from gatepack.gates import GATE_MODULES

ROOT = Path(__file__).resolve().parents[1]
GATES = gatepack.all_gates()


def test_every_module_in_folder_is_registered():
    on_disk = {p.stem for p in (ROOT / "src" / "gatepack" / "gates").glob("*.py") if p.stem != "__init__"}
    assert on_disk == set(GATE_MODULES)


@pytest.mark.parametrize("gate", GATES.values(), ids=list(GATES))
def test_gate_contract(gate):
    assert re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", gate.id)
    assert gate.title and gate.summary and gate.category
    assert gate.sources, "every gate cites at least one source"
    for s in gate.sources:
        assert s.url.startswith("https://") and "example.com" not in s.url
    for o in gate.options:
        assert o.help, f"option {o.name} needs help text"
    doc = ROOT / "docs" / "gates" / f"{gate.id}.md"
    assert doc.is_file(), f"missing docs page {doc.relative_to(ROOT)}"
    text = doc.read_text(encoding="utf-8")
    for s in gate.sources:
        assert s.url in text, f"docs page of {gate.id} must link {s.url}"


@pytest.mark.parametrize("gate", GATES.values(), ids=list(GATES))
def test_missing_file_is_error_not_crash(gate, tmp_path):
    defaults = {"kdp-cover-safezone": {"trim": "6x9"}}.get(gate.id, {})
    r = gate.run(str(tmp_path / "does-not-exist.bin"), **defaults)
    assert r.status == "ERROR"
    assert r.exit_code() == 2


def test_unknown_option_is_error():
    with pytest.raises(gatepack.GateError):
        gatepack.get("loudness").run("x.wav", nonsense=1)
