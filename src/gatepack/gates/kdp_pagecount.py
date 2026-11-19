"""kdp-pagecount: page count and page size of a KDP print interior PDF."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .._pdf import pages as read_pages
from ..core import Finding, Gate, GateError, Option, Source

PRINT_OPTIONS = Source("KDP: Print Options (page count limits)", "https://kdp.amazon.com/en_US/help/topic/G201834180")
TRIM_BLEED = Source("KDP: Set Trim Size, Bleed, and Margins", "https://kdp.amazon.com/en_US/help/topic/GVBQ3CMEQW3W2VL6")

# (format, ink, paper) -> (min, max). Values from the KDP Print Options table (US marketplace, 5 x 8 in rows).
# The maximum can be lower for other trim sizes: check the table for yours.
LIMITS = {
    ("paperback", "black", "white"): (24, 828),
    ("paperback", "black", "cream"): (24, 776),
    ("paperback", "premium-color", "white"): (24, 828),
    ("paperback", "standard-color", "white"): (72, 600),
    ("hardcover", "black", "white"): (75, 550),
    ("hardcover", "black", "cream"): (75, 550),
    ("hardcover", "premium-color", "white"): (75, 550),
}
BLEED_W, BLEED_H = 0.125, 0.25  # KDP: page width + 0.125 in, page height + 0.25 in when the interior has bleed
TOL = 0.01
CLAIM = re.compile(r"\b(\d{2,4})\s*(?:\+\s*)?(?:full[- ]?size |printed |total )?pages\b", re.I)


def _trim(value):
    if not value:
        return None
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*$", str(value))
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        raise GateError(f'trim must look like "6x9", got {value!r}')
    return float(m.group(1)), float(m.group(2))


def _claimed_from(meta_path):
    p = Path(meta_path)
    if not p.is_file():
        raise GateError(f"metadata file not found: {meta_path}")
    meta = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise GateError("metadata file must hold a JSON object")
    text = re.sub(r"<[^>]+>", " ", " ".join(str(meta.get(k, "")) for k in ("title", "subtitle", "description")))
    return sorted({int(m.group(1)) for m in CLAIM.finditer(text)})


def check(path, format="paperback", ink="black", paper="white", trim=None, claimed=None, metadata=None):
    key = (format, ink, paper)
    if key not in LIMITS:
        raise GateError(f"no KDP page limits for format={format}, ink={ink}, paper={paper}")
    info = read_pages(path)
    sizes = [pg["media"] for pg in info]  # the MediaBox is the physical page KDP prints
    pages = len(sizes)
    lo, hi = LIMITS[key]
    out: list[Finding] = []
    if pages < lo:
        out.append(Finding("FAIL", "too-few-pages", f"{pages} pages; KDP minimum for {format} ({ink}, {paper}) is {lo}",
                           "platform-rule"))
    if pages > hi:
        out.append(Finding("FAIL", "too-many-pages", f"{pages} pages; KDP maximum for {format} ({ink}, {paper}) "
                           f"is {hi} at 5 x 8 in (lower for some trims)", "platform-rule"))

    first = sizes[0]
    odd = sorted({s for s in sizes if abs(s[0] - first[0]) > TOL or abs(s[1] - first[1]) > TOL})
    if odd:
        out.append(Finding("FAIL", "mixed-page-sizes", f"pages have different sizes: {first} and {odd[:3]}"))

    measured = {"pages": pages, "page_width_in": first[0], "page_height_in": first[1],
                "limits_basis": f"KDP Print Options table, 5 x 8 in rows: {lo}-{hi} pages"}
    if info[0]["trim"] and info[0]["trim"] != first:
        measured["trimbox_in"] = info[0]["trim"]
    t = _trim(trim)
    if t:
        plain = abs(first[0] - t[0]) <= TOL and abs(first[1] - t[1]) <= TOL
        bleed = abs(first[0] - t[0] - BLEED_W) <= TOL and abs(first[1] - t[1] - BLEED_H) <= TOL
        measured["bleed"] = bleed
        if not (plain or bleed):
            out.append(Finding("FAIL", "trim-mismatch",
                               f"page is {first[0]:g} x {first[1]:g} in; for a {t[0]:g} x {t[1]:g} trim KDP expects "
                               f"{t[0]:g} x {t[1]:g} (no bleed) or {t[0] + BLEED_W:g} x {t[1] + BLEED_H:g} (bleed)",
                               "platform-rule"))

    claims = [int(claimed)] if claimed else []
    if metadata:
        claims += _claimed_from(metadata)
    for c in sorted(set(claims)):
        if c > pages:
            out.append(Finding("FAIL", "page-claim", f"listing promises {c} pages, the PDF has {pages}"))
        elif c < pages * 0.8:
            out.append(Finding("WARN", "page-claim", f"listing says {c} pages, the PDF has {pages}"))
    return out, measured


GATE = Gate(
    id="kdp-pagecount",
    title="KDP page count",
    summary="Interior PDF: page count within KDP limits, one page size, trim/bleed size, and pages promised in the listing.",
    category="kdp",
    sources=(PRINT_OPTIONS, TRIM_BLEED),
    check=check,
    options=(
        Option("format", str, "paperback", "paperback or hardcover", ("paperback", "hardcover")),
        Option("ink", str, "black", "ink type", ("black", "standard-color", "premium-color")),
        Option("paper", str, "white", "paper type", ("white", "cream")),
        Option("trim", str, None, 'trim size such as "6x9" (checks page size, with or without bleed)'),
        Option("claimed", int, None, "page count stated in your listing"),
        Option("metadata", str, None, "kdp-metadata JSON file: reads 'N pages' claims from title/description"),
    ),
    requires=("pypdf",),
)
