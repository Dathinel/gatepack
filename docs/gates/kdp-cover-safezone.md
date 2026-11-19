# kdp-cover-safezone

**What it catches:** cover artwork that sits inside the area KDP trims, folds or wraps, a cover file of
the wrong size, and spine text on books too thin for it.

**Input:** the full wrap cover (back + spine + front) as PNG, JPEG or TIFF. PDF works when PyMuPDF is
installed (`pip install pymupdf`). PyMuPDF is AGPL-licensed, so it is not a gatepack dependency.

## Rules and sources

Paperback ([Create a Paperback Cover](https://kdp.amazon.com/en_US/help/topic/G201953020)):

- Bleed: 0.125 in on top, bottom and outside edges, so the file is `trim height + 0.25 in` high and
  `2 x trim width + spine + 0.25 in` wide.
- "Keep front and back cover text at least 0.125 in inside the trim lines." The gate measures from the
  file edge, so the limit there is 0.25 in.
- Fold lines can vary by 0.0625 in either way; spine text needs 0.0625 in from the spine edges.
- Spine text needs at least 79 pages.
- Spine width per page: white 0.002252 in, cream 0.0025 in, premium color 0.002347 in, standard color 0.002252 in.

Hardcover ([Create a Hardcover Cover](https://kdp.amazon.com/en_US/help/topic/GDTKFJPNQCBTMRV6)):

- "All text and images should be 0.635 in (16 mm) from the edge of the book." Artwork closer than
  0.635 in to the file edge is a **FAIL**.
- Wrap: the same page says the artwork extends "0.51 in (15 mm)" past the board edge, but 15 mm is
  0.591 in. With 15 mm the safe line is 0.591 + 0.125 = **0.716 in**, the figure a KDP hardcover review
  quoted when it rejected a cover the online previewer had accepted. Artwork between 0.635 and 0.716 in
  is a **WARN**.
- Hinge: "a 0.4 in (10 mm) space between the spine and safe area on the front and back covers". Artwork
  closer than 0.4 in to the spine is a FAIL.

## How it measures

1. Each panel (back, front, spine) is split off using the spine width. Pixels far from the panel's
   median colour count as artwork; erosion removes specks smaller than about 0.03 in.
2. Background art that touches the panel edge is set aside: KDP wants it to run into the bleed. Loose
   pieces of the same illustration (leaves, confetti) go with it when they are within 0.1 in of it or
   inside the area it fills.
3. Every remaining object that comes closer to an edge than the limit is reported with its distance.
   Objects no larger than 0.6 in that have at least two neighbours on the same line are described as
   "looks like a line of text"; others as "a picture or shape".

## Levels

| Finding | Paperback | Hardcover |
|---|---|---|
| Wrong file height or width | FAIL (needs a stored resolution or `--dpi`; otherwise `size-unverified` WARN) | not checked (needs the KDP calculator) |
| Artwork inside the margin | WARN: the rule covers text, and pixels cannot prove what is text. Use `--strict` to block on it | FAIL under 0.635 in or 0.4 in from the spine (KDP asks for all text **and images** inside the safe area); WARN from 0.635 to 0.716 in |
| Spine artwork with fewer than 79 pages, or within 0.0625 in of a spine edge | FAIL | not checked |

PDFs are measured at 100 DPI, so distances are accurate to about 0.01 in. Images are measured at their
own resolution, scaled down to 100 DPI when larger.

## What it found on real covers

Run on 11 paperback covers made for KDP (illustrated and flat designs): 3 PASS, 7 WARN, 1 FAIL
(spine text 0.050 in from the spine edge). The warnings were decorative lines 0.22 in from the trim,
confetti and plant leaves near the edge, which is what the WARN level is for. A hardcover cover from
the same set fails on the 0.4 in hinge and warns on the 0.716 in line, the two limits a KDP reviewer
cited for that title.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--format` | paperback | paperback or hardcover |
| `--trim` | required | trim size, e.g. `6x9` |
| `--spine` | derived | spine width in inches; required for hardcover (use the KDP cover calculator) |
| `--pages` | none | paperback: computes spine width and applies the 79-page spine text rule |
| `--paper` | white | white, cream, premium-color, standard-color |
| `--dpi` | from file | image resolution if the file does not store it |

## Known limits

- Text printed on top of edge-to-edge art merges with the art and is not checked. On photo backgrounds
  the gate says `busy-background`: check those margins by eye.
- "Looks like text" is a guess from shape and alignment, not OCR.
- It does not check the barcode area or image resolution yet.
