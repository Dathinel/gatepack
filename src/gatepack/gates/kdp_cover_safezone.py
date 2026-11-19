"""kdp-cover-safezone: is any cover artwork too close to the trim, wrap or spine hinge?

Input: the full wrap cover (back + spine + front) as PNG/JPEG/TIFF, or PDF when PyMuPDF is installed.
Method: for the back and front panel, pixels far from the panel's median colour count as foreground
(text, art); small specks are removed by erosion; large regions touching the panel edge are background art
meant to run into the bleed and are set aside; the bounding box of what is left is compared with the limits.
A photographic or gradient background makes most pixels "foreground": the gate then warns instead of guessing.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..core import Finding, Gate, GateError, Option, Source

PAPERBACK = Source("KDP: Create a Paperback Cover", "https://kdp.amazon.com/en_US/help/topic/G201953020")
HARDCOVER = Source("KDP: Create a Hardcover Cover", "https://kdp.amazon.com/en_US/help/topic/GDTKFJPNQCBTMRV6")

BLEED = 0.125            # paperback bleed on top, bottom and outside edges
PB_SAFE = 0.125          # paperback: text at least 0.125 in inside the trim lines
FOLD_VARIANCE = 0.0625   # paperback: fold lines can move 0.0625 in either way; spine text 0.0625 in from spine edges
SPINE_TEXT_MIN_PAGES = 79
SPINE_PER_PAGE = {"white": 0.002252, "cream": 0.0025, "premium-color": 0.002347, "standard-color": 0.002252}
HC_PAGE = 0.635          # hardcover help page: "All text and images should be 0.635 in (16 mm) from the edge"
HC_WRAP = 15 / 25.4      # 15 mm wrap (the help page prints 0.51 in next to 15 mm; 15 mm is 0.591 in)
HC_REVIEW = round(HC_WRAP + 0.125, 3)  # 0.716 in: 15 mm wrap + 0.125 in, the figure a KDP hardcover review quoted
HC_HINGE = 0.4           # 10 mm hinge between spine and the front/back safe area
RENDER_DPI = 100
THRESH = 45
BUSY_SHARE = 0.45
NEAR_ART = 0.1  # inches: artwork this close to bleed art counts as part of it
MAX_ROUNDS = 8
ART_CELL = 0.25  # inches: grid used to map the area an illustration fills
ART_FILL = 0.3   # a cell at least this much covered by bleed art belongs to the illustration
GLYPH_MAX = 0.6  # inches: a component no bigger than this both ways is text-sized
LINE_REACH = 2.5  # how far, in glyph sizes, to look for neighbouring letters
LINE_FILL = 0.6   # share of the neighbours' ink that must stay within the line band


def _trim(value):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*$", str(value or ""))
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        raise GateError('--trim is required and must look like "6x9"')
    return float(m.group(1)), float(m.group(2))


def _load(path, dpi, fmt, trim_h):
    """Return (RGB image, dots per inch, True when the physical size is known rather than assumed)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise GateError("this gate needs Pillow: pip install 'gatepack[cover]'") from exc
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {path}")
    if p.suffix.lower() == ".pdf":
        try:
            import pymupdf  # type: ignore
        except ImportError as exc:
            raise GateError("PDF covers need PyMuPDF (pip install pymupdf, AGPL-licensed) or export the cover as PNG") from exc
        page = pymupdf.open(str(p))[0]
        pm = page.get_pixmap(dpi=RENDER_DPI)
        return Image.frombytes("RGB", (pm.width, pm.height), pm.samples), float(RENDER_DPI), True
    im = Image.open(p).convert("RGB")
    if dpi is not None and dpi <= 0:
        raise GateError("--dpi must be above 0")
    if not dpi:
        info = im.info.get("dpi")
        dpi = float(info[0]) if info and info[0] and info[0] > 1 else None
    known = bool(dpi)
    if not dpi and fmt == "paperback":
        dpi = im.height / (trim_h + 2 * BLEED)  # assume the height is right; the size check is then skipped
    if not dpi:
        raise GateError("cannot tell the image resolution: pass --dpi (hardcover images need it)")
    if dpi > RENDER_DPI * 1.5:
        scale = RENDER_DPI / dpi
        im = im.resize((round(im.width * scale), round(im.height * scale)))
        dpi = RENDER_DPI
    return im, float(dpi), known


def _drop_bleed_art(mask, dpi):
    """Set aside background art that runs into the bleed; return (mask of the rest, share set aside).

    KDP wants background art to extend past the trim, so a region touching the panel edge is not a
    safe-zone problem. Loose pieces of the same illustration (leaves, sparks) go with it when they lie
    within NEAR_ART inches of it, or inside the area the illustration fills (cells of ART_CELL inches
    at least ART_FILL covered, plus one cell around them). Text printed on top of such art merges with
    it and is not checked (see the gate docs).
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    W, H = mask.size
    total = mask.histogram()[255] or 1
    border = [(x, 0) for x in range(W)] + [(x, H - 1) for x in range(W)]
    border += [(0, y) for y in range(H)] + [(W - 1, y) for y in range(H)]
    for xy in border:
        if mask.getpixel(xy) == 255:
            ImageDraw.floodfill(mask, xy, 100)
    art = mask.point(lambda v: 255 if v == 100 else 0)
    gw, gh = max(1, round(W / (ART_CELL * dpi))), max(1, round(H / (ART_CELL * dpi)))
    cells = art.resize((gw, gh), Image.BOX).point(lambda v: 255 if v >= ART_FILL * 255 else 0)
    area = cells.filter(ImageFilter.MaxFilter(3)).resize((W, H), Image.NEAREST)
    for _ in range(MAX_ROUNDS):  # pieces near the art join it, then pieces near those, and so on
        near = mask.point(lambda v: 255 if v == 100 else 0)
        if near.getbbox() is None:
            break
        for _ in range(max(1, round(NEAR_ART * dpi))):
            near = near.filter(ImageFilter.MaxFilter(3))
        near = ImageChops.lighter(near, area)
        grew = False
        while True:
            hit = ImageChops.multiply(mask.point(lambda v: 255 if v == 255 else 0), near)
            box = hit.getbbox()
            if box is None:
                break
            x0, y0, x1, _ = box
            seed = next(x for x in range(x0, x1) if hit.getpixel((x, y0)))
            ImageDraw.floodfill(mask, (seed, y0), 100)
            grew = True
        if not grew:
            break
    share = mask.histogram()[100] / total
    return mask.point(lambda v: 255 if v == 255 else 0), share


def _mask(panel, dpi, drop_bleed_art=True):
    """Foreground mask of a panel; returns (mask, foreground share, share set aside as bleed art, pad px)."""
    from PIL import Image, ImageChops, ImageFilter, ImageStat

    med = tuple(int(v) for v in ImageStat.Stat(panel).median)
    diff = ImageChops.difference(panel, Image.new("RGB", panel.size, med))
    r, g, b = diff.split()
    total = ImageChops.add(ImageChops.add(r, g), b)  # clipped at 255, enough for a threshold of 45
    mask = total.point(lambda v: 255 if v > THRESH else 0)
    share = mask.histogram()[255] / (mask.width * mask.height)
    erode = max(3, int(round(dpi * 0.027)) | 1)
    mask = mask.filter(ImageFilter.MinFilter(erode))
    removed = 0.0
    if drop_bleed_art:
        mask, removed = _drop_bleed_art(mask, dpi)
    return mask, share, removed, erode // 2


def _runs(values):
    """Number of separate non-zero runs in a sequence."""
    n, prev = 0, False
    for v in values:
        on = v > 0
        n += on and not prev
        prev = on
    return n


def _in_a_line(mask, box):
    """True when the component has at least two neighbours on its own text line (horizontal or vertical).

    Letters sit in rows of similar height; loose specks of an illustration (leaves, stars) do not.
    The band is the component's own rows (or columns, for spine-style vertical text), extended by
    LINE_REACH times its size on both sides; neighbours are separate runs of foreground in that band.
    Neighbours only count when most of their ink stays inside the band, as letters of one line do.
    """
    from PIL import Image

    W, H = mask.size
    l, t, r, b = box
    h, w = max(1, b - t), max(1, r - l)

    def side(x0, y0, x1, y1, horizontal):
        if x1 <= x0 or y1 <= y0:
            return 0
        if horizontal:
            m = h // 2
            ext = mask.crop((x0, max(0, y0 - m), x1, min(H, y1 + m)))
            core = mask.crop((x0, y0, x1, y1))
            profile = core.resize((core.width, 1), Image.BOX).tobytes()
        else:
            m = w // 2
            ext = mask.crop((max(0, x0 - m), y0, min(W, x1 + m), y1))
            core = mask.crop((x0, y0, x1, y1))
            profile = core.resize((1, core.height), Image.BOX).tobytes()
        inside, total = core.histogram()[255], ext.histogram()[255]
        return _runs(profile) if total and inside / total >= LINE_FILL else 0

    reach = int(LINE_REACH * h)
    horiz = side(max(0, l - reach), t, l, b, True) + side(r, t, min(W, r + reach), b, True)
    reach = int(LINE_REACH * w)
    vert = side(l, max(0, t - reach), r, t, False) + side(l, b, r, min(H, b + reach), False)
    return horiz >= 2 or vert >= 2


def _near_edges(mask, dpi, limits, pad):
    """Components that come closer to an edge than its limit: [(edge, distance_in, text_sized)].

    limits: {"left": in, "right": in, "top": in, "bottom": in}. A component whose box is at most
    GLYPH_MAX inches in both directions is "text-sized" (a letter, a small logo); bigger ones are pictures.
    """
    from PIL import Image, ImageDraw

    W, H = mask.size
    zone = Image.new("L", mask.size, 0)
    d = ImageDraw.Draw(zone)
    lp = {k: int(round(v * dpi)) + pad for k, v in limits.items()}
    d.rectangle([0, 0, lp["left"], H], fill=255)
    d.rectangle([W - 1 - lp["right"], 0, W, H], fill=255)
    d.rectangle([0, 0, W, lp["top"]], fill=255)
    d.rectangle([0, H - 1 - lp["bottom"], W, H], fill=255)
    black = Image.new("L", mask.size, 0)
    work = mask.copy()
    found = []
    while True:
        hit = Image.composite(work, black, zone).point(lambda v: 255 if v == 255 else 0)
        box = hit.getbbox()
        if box is None:
            return found
        x0, y0, x1, _ = box
        seed = next(x for x in range(x0, x1) if hit.getpixel((x, y0)))
        ImageDraw.floodfill(work, (seed, y0), 100)
        l, t, r, b = work.point(lambda v: 255 if v == 100 else 0).getbbox()
        work = work.point(lambda v: 50 if v == 100 else v)
        text_sized = (r - l) / dpi <= GLYPH_MAX and (b - t) / dpi <= GLYPH_MAX and _in_a_line(mask, (l, t, r, b))
        l, t, r, b = max(0, l - pad), max(0, t - pad), min(W, r + pad), min(H, b + pad)
        dist = {"left": l / dpi, "right": (W - r) / dpi, "top": t / dpi, "bottom": (H - b) / dpi}
        for edge, lim in limits.items():
            if dist[edge] < lim:
                found.append((edge, round(dist[edge], 3), text_sized))


def check(path, format="paperback", trim=None, spine=None, pages=None, paper="white", dpi=None):
    tw, th = _trim(trim)
    if spine is None and pages and format == "paperback":
        spine = round(pages * SPINE_PER_PAGE[paper], 4)
    im, dpi, size_known = _load(path, dpi, format, th)
    w_in, h_in = im.width / dpi, im.height / dpi
    out: list[Finding] = []
    measured = {"file_width_in": round(w_in, 3), "file_height_in": round(h_in, 3), "dpi": round(dpi, 1)}

    if not size_known:
        out.append(Finding("WARN", "size-unverified", "the image stores no resolution, so its physical size was assumed "
                           "from the trim height; pass --dpi to check the cover size"))
    if format == "paperback":
        if size_known and abs(h_in - (th + 2 * BLEED)) > 0.03:
            out.append(Finding("FAIL", "cover-height", f"file is {h_in:.3f} in high; paperback with {th:g} in trim "
                               f"needs {th + 2 * BLEED:.3f} in (trim + 0.125 in bleed top and bottom)", "platform-rule"))
        if spine is None:
            spine = round(w_in - 2 * tw - 2 * BLEED, 4)
            measured["spine_in_derived"] = spine
        elif size_known and abs(w_in - (2 * tw + spine + 2 * BLEED)) > 0.03:
            out.append(Finding("FAIL", "cover-width", f"file is {w_in:.3f} in wide; expected {2 * tw + spine + 2 * BLEED:.3f} "
                               f"(2 x {tw:g} trim + {spine:g} spine + 2 x 0.125 bleed)", "platform-rule"))
        edge_limit, spine_limit = BLEED + PB_SAFE, PB_SAFE
    elif format == "hardcover":
        if spine is None:
            raise GateError("hardcover needs --spine (inches, from the KDP cover calculator)")
        edge_limit, spine_limit = HC_REVIEW, HC_HINGE
    else:
        raise GateError("format must be paperback or hardcover")

    if spine <= 0 or spine >= w_in:
        raise GateError(f"spine width {spine} in does not fit a {w_in:.3f} in wide file")
    measured["spine_in"] = spine
    panel_w = (w_in - spine) / 2
    W, H = im.size
    sx0, sx1 = int(round(panel_w * dpi)), int(round((panel_w + spine) * dpi))

    for name, box, spine_side in (("back", (0, 0, sx0, H), "right"), ("front", (sx1, 0, W, H), "left")):
        mask, share, bleed_art, pad = _mask(im.crop(box), dpi)
        measured[f"{name}_foreground_share"] = round(share, 2)
        measured[f"{name}_bleed_art_share"] = round(bleed_art, 2)
        if mask.getbbox() is None:
            out.append(Finding("WARN", "empty-panel", f"{name} panel has no artwork apart from background"))
            continue
        if share > BUSY_SHARE:
            out.append(Finding("WARN", "busy-background", f"{name} panel: {share:.0%} of pixels differ from the main colour "
                               "(photo or gradient background); check the margins by eye as well"))
        outer_side = "left" if spine_side == "right" else "right"
        limits = {outer_side: edge_limit, spine_side: spine_limit, "top": edge_limit, "bottom": edge_limit}
        worst: dict = {}
        for edge, dist, text_sized in _near_edges(mask, dpi, limits, pad):
            key = ("spine" if edge == spine_side else "outer" if edge == outer_side else edge, text_sized)
            worst[key] = min(dist, worst.get(key, dist))
        for (edge, text_sized), dist in sorted(worst.items()):
            limit = spine_limit if edge == "spine" else edge_limit
            where = "the spine fold" if edge == "spine" else f"the {edge} file edge"
            # Hardcover: KDP asks for all text and images inside the safe area, so any artwork fails.
            # Paperback: the rule covers text; pixels alone cannot prove what is text, so this warns.
            what = "artwork that looks like a line of text" if text_sized else "a picture or shape"
            if format == "hardcover" and edge != "spine" and dist >= HC_PAGE:
                level, note = "WARN", (f"; this meets the {HC_PAGE} in on the help page, but a KDP review has cited "
                                       f"{HC_REVIEW} in (15 mm wrap + 0.125 in)")
                out.append(Finding(level, f"{name}-{edge}-margin", f"{name}: {what} {dist:.3f} in from {where}{note}",
                                   "platform-rule", {"measured_in": dist, "limit_in": HC_REVIEW, "text_sized": text_sized}))
                continue
            elif format == "hardcover":
                level, note = "FAIL", ""
                if edge != "spine":
                    limit = HC_PAGE
            elif text_sized:
                level, note = "WARN", " (if this is text, move it inside the safe area)"
            else:
                level, note = "WARN", " (fine for background art, not for text or important images)"
            out.append(Finding(level, f"{name}-{edge}-margin",
                               f"{name}: {what} {dist:.3f} in from {where}; KDP safe area starts at {limit:.3f} in{note}",
                               "platform-rule", {"measured_in": dist, "limit_in": round(limit, 3), "text_sized": text_sized}))

    if format == "paperback" and sx1 - sx0 >= 3:
        mask, _, _, pad = _mask(im.crop((sx0, 0, sx1, H)), dpi)
        box = mask.getbbox()
        if box is not None:
            if pages is not None and pages < SPINE_TEXT_MIN_PAGES:
                out.append(Finding("FAIL", "spine-text-page-count",
                                   f"spine has artwork but the book has {pages} pages; KDP allows spine text from "
                                   f"{SPINE_TEXT_MIN_PAGES} pages", "platform-rule"))
            near = min(max(0, box[0] - pad), (sx1 - sx0) - min(sx1 - sx0, box[2] + pad)) / dpi
            if near < FOLD_VARIANCE:
                out.append(Finding("FAIL", "spine-text-margin", f"spine artwork is {near:.3f} in from a spine edge; "
                                   f"KDP asks for {FOLD_VARIANCE} in", "platform-rule"))
    return out, measured


GATE = Gate(
    id="kdp-cover-safezone",
    title="KDP cover safe zone",
    summary="Full wrap cover: artwork distance from trim, wrap and spine hinge, cover size, spine text rules.",
    category="kdp",
    sources=(PAPERBACK, HARDCOVER),
    check=check,
    options=(
        Option("format", str, "paperback", "paperback or hardcover", ("paperback", "hardcover")),
        Option("trim", str, None, 'trim size such as "6x9" (required)'),
        Option("spine", float, None, "spine width in inches (required for hardcover; paperback can use --pages)"),
        Option("pages", int, None, "page count (paperback spine width and the 79-page spine text rule)"),
        Option("paper", str, "white", "paperback paper", tuple(SPINE_PER_PAGE)),
        Option("dpi", float, None, "image resolution when the file does not store it"),
    ),
    requires=("Pillow",),
)
