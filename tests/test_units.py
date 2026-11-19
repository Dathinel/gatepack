"""Small rule-level tests that do not need fixture files."""
from __future__ import annotations

import json

import pytest

import gatepack
from gatepack.core import Finding

from conftest import make_pdf


def meta_result(tmp_path, **fields):
    p = tmp_path / "meta.json"
    p.write_text(json.dumps(fields), encoding="utf-8")
    return gatepack.check("kdp-metadata", str(p))


def codes(result):
    return {f.code for f in result.findings}


def test_title_length_limit(tmp_path):
    r = meta_result(tmp_path, title="A" * 150, subtitle="B" * 50)
    assert "title-too-long" in codes(r)
    assert "title-too-long" not in codes(meta_result(tmp_path, title="A" * 150, subtitle="B" * 49))


def test_free_as_topic_is_only_a_warning(tmp_path):
    r = meta_result(tmp_path, title="Sugar Free Baking", format="kindle ebook")
    assert r.status == "WARN" and "promotion-word" in codes(r)
    assert "promotion-word" not in codes(meta_result(tmp_path, title="Gluten-free Baking", format="kindle ebook"))


def test_isbn_is_not_a_phone_number(tmp_path):
    r = meta_result(tmp_path, title="Notes", description="ISBN 9781234567897, second edition.", format="kindle ebook")
    assert "contact-info" not in codes(r)


def test_review_request_fails(tmp_path):
    r = meta_result(tmp_path, title="Notes", description="If you liked it, please leave a review!", format="kindle ebook")
    assert "review-request" in codes(r)


def test_custom_brand_file(tmp_path):
    brands = tmp_path / "brands.txt"
    brands.write_text("# my list\nacme widgets\n", encoding="utf-8")
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"title": "Acme Widgets Repair Log", "format": "paperback", "trim": "6x9"}), encoding="utf-8")
    assert "trademark" in codes(gatepack.check("kdp-metadata", str(p), brands=str(brands)))


def test_catalog_near_duplicate(tmp_path):
    cat = tmp_path / "catalog.csv"
    cat.write_text("title;asin\nQuiet Garden Word Search: 120 Large Print Puzzles;X\n", encoding="utf-8")
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"title": "Quiet Garden Word Search", "subtitle": "120 Large Print Puzzles!",
                             "format": "paperback", "trim": "8.5x11"}), encoding="utf-8")
    assert "near-duplicate" in codes(gatepack.check("kdp-metadata", str(p), catalog=str(cat)))


def test_grid_sizes_are_not_trim_sizes(tmp_path):
    r = meta_result(tmp_path, title="Sudoku", description="Easy 9 x 9 grids", format="paperback", trim="6x9")
    assert "trim-mismatch" not in codes(r)


def test_trimbox_does_not_hide_the_physical_page(tmp_path):
    pdf = tmp_path / "i.pdf"
    pdf.write_bytes(make_pdf(30, 8.5, 11).replace(b"/MediaBox [0 0 612.0 792]",
                                                  b"/MediaBox [0 0 612.0 792] /TrimBox [0 0 432 648]"))
    r = gatepack.check("kdp-pagecount", str(pdf), trim="6x9")
    assert r.measurements["trimbox_in"] == (6.0, 9.0)
    assert "trim-mismatch" in codes(r)


def test_pdf_without_pages_is_error(tmp_path):
    pdf = tmp_path / "e.pdf"
    pdf.write_bytes(make_pdf(0, 6, 9))
    assert gatepack.check("kdp-pagecount", str(pdf)).status == "ERROR"


def test_metadata_page_claim(tmp_path):
    pdf = tmp_path / "i.pdf"
    pdf.write_bytes(make_pdf(30, 6, 9))
    meta = tmp_path / "m.json"
    meta.write_text(json.dumps({"description": "<p>Over 50 pages of puzzles.</p>"}), encoding="utf-8")
    r = gatepack.check("kdp-pagecount", str(pdf), metadata=str(meta))
    assert "page-claim" in codes(r)


def test_finding_rejects_unknown_level():
    with pytest.raises(ValueError):
        Finding("MAYBE", "x", "y")


def test_result_status_is_worst_level():
    gate = gatepack.get("epub")
    r = gatepack.Result(gate, "f", [Finding("WARN", "a", "b"), Finding("FAIL", "c", "d")], {}, {})
    assert r.status == "FAIL" and r.exit_code() == 1


def test_metadata_types_are_validated(tmp_path):
    for bad in ({"title": None, "keywords": "word search"}, {"title": "A", "keywords": [1, 2]}, {"title": 5}):
        p = tmp_path / "m.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        assert gatepack.check("kdp-metadata", str(p)).status == "ERROR"


def test_link_in_description_html_is_contact_info(tmp_path):
    r = meta_result(tmp_path, title="Notes", format="kindle ebook",
                    description='<p>More at <a href="https://example.com">our site</a>.</p>')
    assert "contact-info" in codes(r)


def test_print_only_word_in_title_alone_is_a_warning(tmp_path):
    r = meta_result(tmp_path, title="Sudoku Solving Techniques", format="kindle ebook",
                    description="<p>A guide to the logic behind hard grids.</p>")
    assert r.status == "WARN" and "print-only-content" in codes(r)


def test_example_trademark_list_warns_but_own_list_fails(tmp_path):
    r = meta_result(tmp_path, title="Lego Brick Notes", format="paperback", trim="6x9")
    assert r.status == "WARN"


def test_non_latin_titles_are_not_duplicates(tmp_path):
    cat = tmp_path / "catalog.csv"
    cat.write_text("title\n猫の本\n", encoding="utf-8")
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"title": "犬の旅", "format": "kindle ebook"}), encoding="utf-8")
    r = gatepack.check("kdp-metadata", str(p), catalog=str(cat))
    assert r.status == "PASS", r.to_text()


def test_non_finite_option_is_error():
    r = gatepack.check("loudness", "x.flac", tolerance=float("nan"))
    assert r.status == "ERROR"


def test_epub_with_traversal_entry_fails(tmp_path):
    import zipfile
    f = tmp_path / "evil.epub"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("../outside.xhtml", "<html/>")
    assert "unsafe-path" in codes(gatepack.check("epub", str(f)))


def test_cover_without_dpi_says_size_unverified(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    f = tmp_path / "c.png"
    Image.new("RGB", (500, 370), (230, 230, 230)).save(f)
    r = gatepack.check("kdp-cover-safezone", str(f), trim="6x9")
    assert "size-unverified" in codes(r)
