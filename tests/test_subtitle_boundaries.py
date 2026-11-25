import pytest

from gatepack.gates.subtitles import check


@pytest.mark.parametrize("ext", ["srt", "vtt"])
def test_missing_separator_before_second_timing(tmp_path, ext):
    path = tmp_path / f"captions.{ext}"
    if ext == "vtt":
        text = "WEBVTT\n\n00:00.000 --> 00:02.000\nA\n00:03.000 --> 00:02.000\nB"
    else:
        text = "1\n00:00:00,000 --> 00:00:02,000\nA\n2\n00:00:03,000 --> 00:00:02,000\nB"
    path.write_text(text, encoding="utf-8")
    findings, _ = check(path)
    assert any(f.level == "FAIL" and f.code == "separator" for f in findings)


@pytest.mark.parametrize("space", [" ", "\t"])
def test_whitespace_line_in_vtt_payload(tmp_path, space):
    path = tmp_path / "captions.vtt"
    path.write_text(f"WEBVTT\n\n00:00.000 --> 00:02.000\nA\n{space}\nB", encoding="utf-8")
    assert check(path) == ([], {"cues": 1})


def test_srt_whitespace_separator_and_literal_arrow(tmp_path):
    path = tmp_path / "captions.srt"
    path.write_text("1\n00:00:00,000 --> 00:00:01,000\nA --> B\n \t\n"
                    "2\n00:00:01,000 --> 00:00:02,000\nC", encoding="utf-8")
    assert check(path) == ([], {"cues": 2})


@pytest.mark.parametrize(("left", "right", "valid"), [
    (" ", " ", True),
    ("\t", "\t", True),
    ("\u00a0", " ", False),
    (" ", "\u00a0", False),
    (" \u00a0 ", "\t", False),
])
def test_webvtt_arrow_delimiters(tmp_path, left, right, valid):
    path = tmp_path / "delimiters.vtt"
    path.write_text(f"WEBVTT\n\n00:00.000{left}-->{right}00:02.000 line:90%\nCaption", encoding="utf-8")
    findings, measured = check(path)
    assert measured["cues"] == 1
    if valid:
        assert not findings
    else:
        assert any(f.level == "FAIL" and f.code == "timing" for f in findings)
