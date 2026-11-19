"""kdp-metadata: title, subtitle, description and keywords of a KDP book, before Publish or before an edit.

Input: a JSON file such as
    {"format": "paperback", "trim": "6x9", "title": "...", "subtitle": "...",
     "description": "<p>...</p>", "keywords": ["...", "..."]}
"""
from __future__ import annotations

import csv
import difflib
import html
import json
import re
import unicodedata
from pathlib import Path

from ..core import Finding, Gate, GateError, Option, Source

META = Source("KDP: Metadata Guidelines for Books", "https://kdp.amazon.com/en_US/help/topic/G201097560")
KEYWORDS = Source("KDP: Make Your Book More Discoverable with Keywords", "https://kdp.amazon.com/en_US/help/topic/G201298500")
KINDLE = Source("KDP: Guide to Kindle Content Quality (content unsuited for Kindle)", "https://kdp.amazon.com/en_US/help/topic/G200952510")

# Example list only: a few widely known registered marks, so the mechanism has something to match.
# It is NOT a complete trademark database. Extend it with --brands FILE (one term or regex per line).
EXAMPLE_TRADEMARKS = (
    "disney", "pixar", "marvel", "star wars", "harry potter", r"pok[eé]mon", "minecraft", "lego",
    "barbie", "hello kitty", "crayola", "sharpie", "for dummies", "instant pot", "kindle unlimited", "kdp select",
)

WORKING_NOTE = re.compile(
    r"\b(todo|tbd|tbc|fixme|lorem ipsum|placeholder|insert (?:title|text|keyword)s?)\b|x{3,}|\{\{.*?\}\}|\[(?:insert|add|your)\b[^\]]*\]",
    re.I)
HTML_TAG = re.compile(r"<\s*/?\s*[a-z][a-z0-9]*(\s[^<>]*)?>", re.I)
SALES_RANK = re.compile(r"\b(best[- ]?sell(?:ing|er)s?|#\s?1\b|number one best)", re.I)
FREE_WORD = re.compile(r"(?<![-\w])free(?![-\w])", re.I)
TIME_SENSITIVE = re.compile(r"\b(new release|on sale|available now|limited time|pre-?order bonus|today only)\b", re.I)
URL = re.compile(r"\bhttps?://\S+|\bwww\.\S+|\b[\w.-]+\.(?:com|net|org|io|co)\b", re.I)
HREF = re.compile(r"""\b(?:href|src)\s*=\s*["']?(?:https?:|mailto:|tel:|www\.)""", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){9,14}\d(?!\d)")
REVIEW_REQUEST = re.compile(r"\b(leave|write|post) (?:a|an|your) (?:honest )?review\b", re.I)
TESTIMONIAL = re.compile(r"\b\d(?:\.\d)? ?stars?\b|[\"“][^\"”]{10,200}[\"”]\s*[-–—]\s*[A-Z]", re.I)
PROMISE = re.compile(r"\b(complete|ultimate|definitive|everything you need|all-in-one)\b", re.I)

PRINT_ONLY_TITLE = re.compile(
    r"\b(colou?ring|color by number|puzzles?|sudoku|crosswords?|word ?search|mazes?|blank journal|guided journal|"
    r"journal prompts?|writing prompts?|notebook|planner|log ?book|tracker|fill[- ]in|activity book|pattern book|"
    r"facing[- ]page)\b", re.I)
PRINT_ONLY_DESC = re.compile(
    r"\b(colou?ring pages|colou?ring book|puzzle book|sudoku|crossword|word search|blank pages|lined pages|"
    r"write (?:your answers )?in the book)\b", re.I)

SQUARE_TRIMS = (8.0, 8.25, 8.5)  # square book sizes; other "N x N" in a description are usually puzzle grids
TRIM_IN_TEXT = re.compile(r"(\d{1,2}(?:\.\d{1,3})?)\s*(?:\"|”|in(?:ch(?:es)?)?\.?)?\s*[x×]\s*(\d{1,2}(?:\.\d{1,3})?)\s*(?:\"|”|in(?:ch(?:es)?)?)?", re.I)
COUNT_IN_TEXT = re.compile(r"(\d{2,4})\s*\+?\s*(?:unique |original |detailed |simple |bold |large print )?"
                           r"(designs|illustrations|coloring pages|pages|puzzles|recipes|questions|prompts)\b", re.I)


def _load_terms(path: str | None, defaults: bool) -> list[str]:
    terms = list(EXAMPLE_TRADEMARKS) if defaults else []
    if path:
        p = Path(path)
        if not p.is_file():
            raise GateError(f"brands file not found: {path}")
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                terms.append(line)
    return terms


def _trim(value: str):
    m = re.match(r"\s*([\d.]+)\s*[x×]\s*([\d.]+)", value or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def _norm(text: str) -> str:
    """Letters and digits of any script, case-folded, single spaces, bracketed parts removed."""
    text = unicodedata.normalize("NFKC", re.sub(r"\(.*?\)", " ", text)).casefold()
    return " ".join(re.sub(r"[^\w ]+|_", " ", text).split())


def _load_catalog(path: str | None) -> list[str]:
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        raise GateError(f"catalog file not found: {path}")
    with p.open(encoding="utf-8", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel  # a single column has no delimiter to detect
        reader = csv.DictReader(f, dialect=dialect)
        if "title" not in (reader.fieldnames or []):
            raise GateError("catalog CSV needs a 'title' column")
        return [row["title"] for row in reader if row.get("title")]


def check(path, brands=None, default_brands=True, catalog=None, max_keywords=7):
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {path}")
    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateError(f"not valid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise GateError("expected a JSON object with title, subtitle, description, keywords")

    for key in ("title", "subtitle", "description", "format", "trim"):
        if meta.get(key) is not None and not isinstance(meta[key], str):
            raise GateError(f'"{key}" must be a string')
    keywords = meta.get("keywords") or []
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise GateError('"keywords" must be a list of strings')
    title, sub = meta.get("title") or "", meta.get("subtitle") or ""
    raw_desc = meta.get("description") or ""
    desc = html.unescape(HTML_TAG.sub(" ", raw_desc))
    fmt = (meta.get("format") or "").lower()
    if fmt and not any(w in fmt for w in ("paperback", "hardcover", "ebook", "kindle")):
        raise GateError('"format" must be paperback, hardcover or kindle ebook')
    out: list[Finding] = []
    fields = {"title": title, "subtitle": sub, "description": desc, "keywords": " | ".join(keywords)}

    if not title.strip():
        out.append(Finding("FAIL", "missing-title", "title is empty"))
    n = len(title) + len(sub)
    if n >= 200:
        out.append(Finding("FAIL", "title-too-long", f"title + subtitle is {n} characters; KDP requires fewer than 200",
                           "platform-rule"))

    for name, text in fields.items():
        m = WORKING_NOTE.search(text)
        if m:
            out.append(Finding("FAIL", "working-note", f'{name} still contains a working note: "{m.group(0)}"'))

    for name in ("title", "subtitle", "keywords"):
        raw = {"title": title, "subtitle": sub, "keywords": " | ".join(keywords)}[name]
        if HTML_TAG.search(raw):
            out.append(Finding("FAIL", "html-tag", f"HTML tag in {name}", "platform-rule"))
        m = SALES_RANK.search(raw)
        if m:
            out.append(Finding("FAIL", "sales-rank-claim", f'{name} refers to sales rank: "{m.group(0)}"', "platform-rule"))
        m = FREE_WORD.search(raw)
        if m:
            out.append(Finding("WARN", "promotion-word", f'{name} contains "free"; KDP disallows promotional "free" '
                               '(fine when it is the topic, e.g. "sugar free")', "platform-rule"))

    # Your own --brands list is a decision you made: FAIL. The built-in example list cannot know whether
    # you are authorized or whether the word is used in its ordinary sense: WARN.
    for source, terms, level in (("your brands file", _load_terms(brands, False), "FAIL"),
                                 ("the example trademark list", list(EXAMPLE_TRADEMARKS) if default_brands else [], "WARN")):
        if not terms:
            continue
        rx = re.compile(r"\b(" + "|".join(terms) + r")\b", re.I)
        for name, text in fields.items():
            for hit in sorted({m.group(0) for m in rx.finditer(text)}, key=str.lower):
                out.append(Finding(level, "trademark", f'{name} mentions "{hit}" ({source}); KDP disallows '
                                   "unauthorized references to trademarked terms", "platform-rule"))

    # description content KDP lists as not allowed
    phone = any("isbn" not in desc[max(0, m.start() - 12):m.start()].lower() for m in PHONE.finditer(desc))
    links = HREF.findall(raw_desc)  # <a href="..."> links vanish when tags are stripped
    if URL.search(desc) or EMAIL.search(desc) or phone or links:
        out.append(Finding("FAIL", "contact-info", "description contains a URL, e-mail address or phone number", "platform-rule"))
    if REVIEW_REQUEST.search(desc):
        out.append(Finding("FAIL", "review-request", "description asks readers for reviews", "platform-rule"))
    m = TESTIMONIAL.search(desc)
    if m:
        out.append(Finding("WARN", "testimonial", f'description seems to quote a review or rating: "{m.group(0)[:60]}"',
                           "platform-rule"))
    for name in ("description", "keywords"):
        m = TIME_SENSITIVE.search(fields[name])
        if m:
            out.append(Finding("WARN", "time-sensitive", f'{name} has time-sensitive wording: "{m.group(0)}"', "platform-rule"))

    if len(keywords) > max_keywords:
        out.append(Finding("FAIL", "too-many-keywords", f"{len(keywords)} keywords; KDP takes up to {max_keywords}", "platform-rule"))
    for k in keywords:
        if '"' in k or "“" in k:
            out.append(Finding("WARN", "quoted-keyword", f"keyword has quotation marks: {k}", "platform-rule"))

    m = PROMISE.search(f"{title} {sub}")
    if m:
        out.append(Finding("WARN", "promise-word", f'title promises "{m.group(0)}": make sure the content delivers it'))

    real = _trim(str(meta.get("trim", "")))
    if real:
        for m in TRIM_IN_TEXT.finditer(f"{title} {sub} {desc}"):
            said = (float(m.group(1)), float(m.group(2)))
            if said[0] == said[1] and said[0] not in SQUARE_TRIMS:
                continue  # grid sizes such as "9 x 9 sudoku", not a trim
            if 4 <= said[0] <= 12 and 4 <= said[1] <= 14 and said != real:
                out.append(Finding("FAIL", "trim-mismatch",
                                   f"text says {m.group(0).strip()} but the book is {real[0]:g} x {real[1]:g} in"))
    elif fmt in ("paperback", "hardcover"):
        out.append(Finding("WARN", "trim-unknown", 'no "trim" field: cannot compare trim sizes mentioned in the text'))

    counts: dict[str, set] = {}
    for m in COUNT_IN_TEXT.finditer(" ".join(fields.values())):
        kind = m.group(2).lower().replace("coloring ", "")
        counts.setdefault(kind, set()).add(int(m.group(1)))
    for kind, nums in sorted(counts.items()):
        if len(nums) > 1:
            out.append(Finding("FAIL", "conflicting-counts", f"different counts of {kind}: {sorted(nums)}"))

    if "ebook" in fmt or "kindle" in fmt:
        # The description naming the format ("coloring pages", "write in the book") is strong evidence: FAIL.
        # A title word alone ("Sudoku Solving Techniques") may describe a prose book: WARN.
        m_desc, m_title = PRINT_ONLY_DESC.search(desc), PRINT_ONLY_TITLE.search(f"{title} {sub}")
        m = m_desc or m_title
        if m:
            out.append(Finding("FAIL" if m_desc else "WARN", "print-only-content",
                               f'Kindle eBook looks like write-in or coloring content ("{m.group(0)}"); KDP lists books '
                               "whose main purpose is writing or coloring as unsuited for Kindle", "platform-rule"))

    mine = _norm(f"{title} {sub}")
    for other in _load_catalog(catalog):
        theirs = _norm(other)
        if not mine or not theirs:
            continue
        ratio = difflib.SequenceMatcher(None, mine, theirs).ratio()
        if ratio >= 0.85:
            out.append(Finding("FAIL", "near-duplicate", f'{ratio:.0%} similar to catalog title "{other[:70]}"'))

    return out, {"title_subtitle_chars": n, "keywords": len(keywords)}


GATE = Gate(
    id="kdp-metadata",
    title="KDP metadata",
    summary="Title, subtitle, description and keywords against KDP metadata rules and common self-inflicted errors.",
    category="kdp",
    sources=(META, KEYWORDS, KINDLE),
    check=check,
    options=(
        Option("brands", str, None, "file with extra trademark terms or regexes, one per line"),
        Option("default_brands", lambda v: str(v).lower() not in ("0", "false", "no"), True,
               "use the built-in example trademark list (true/false)"),
        Option("catalog", str, None, "CSV with a 'title' column (your other books) to catch near-duplicates"),
        Option("max_keywords", int, 7, "keyword limit (KDP: up to seven)"),
    ),
)
