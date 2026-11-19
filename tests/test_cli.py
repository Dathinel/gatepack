from __future__ import annotations

import json
from pathlib import Path

import pytest

from gatepack import all_gates
from gatepack.cli import main
from gatepack.scaffold import create_gate

FIX = Path(__file__).parent / "fixtures"


def test_list_text(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for gid in all_gates():
        assert gid in out


def test_list_json(capsys):
    assert main(["list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [g["id"] for g in data] == list(all_gates()) and all(g["sources"] for g in data)


def test_check_pass_exit_0_and_json(capsys):
    f = FIX / "kdp-metadata" / "pass" / "ebook_prose.json"
    assert main(["check", "kdp-metadata", str(f), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "PASS" and data["gate"] == "kdp-metadata" and data["sources"]


def test_check_fail_exit_1_text(capsys):
    f = FIX / "kdp-metadata" / "fail" / "ebook_coloring_book.json"
    assert main(["check", "kdp-metadata", str(f)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("FAIL") and "print-only-content" in out and "rule sources:" in out


def test_check_options_reach_the_gate(capsys):
    f = FIX / "kdp-pagecount" / "fail" / "wrong_trim_letter_size.pdf"
    assert main(["check", "kdp-pagecount", str(f)]) == 0  # no --trim: size is not compared
    assert main(["check", "kdp-pagecount", str(f), "--trim", "6x9"]) == 1


def test_strict_turns_warn_into_failure(tmp_path, capsys):
    meta = tmp_path / "m.json"
    meta.write_text(json.dumps({"format": "paperback", "title": "The Ultimate Bread Guide"}), encoding="utf-8")
    assert main(["check", "kdp-metadata", str(meta)]) == 0
    assert main(["check", "kdp-metadata", str(meta), "--strict"]) == 1


def test_error_exit_2(tmp_path, capsys):
    assert main(["check", "epub", str(tmp_path / "missing.epub")]) == 2


def test_unknown_gate_is_usage_error():
    with pytest.raises(SystemExit):
        main(["check", "no-such-gate", "x"])


def test_new_gate_scaffold(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "gatepack"\n', encoding="utf-8")
    created = create_gate(tmp_path, "youtube-thumbnail", "image")
    names = {p.as_posix() for p in created}
    assert "src/gatepack/gates/youtube_thumbnail.py" in names
    assert "docs/gates/youtube-thumbnail.md" in names
    code = (tmp_path / "src/gatepack/gates/youtube_thumbnail.py").read_text(encoding="utf-8")
    compile(code, "youtube_thumbnail.py", "exec")
    assert 'id="youtube-thumbnail"' in code
