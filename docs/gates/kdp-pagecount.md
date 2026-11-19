# kdp-pagecount

**What it catches:** an interior PDF with too few or too many pages for KDP print, pages of different
sizes, a page size that does not match the trim (with or without bleed), and a listing that promises
more pages than the file has.

**Input:** the interior PDF, read with `pypdf` (installed with gatepack). Page size is the MediaBox,
the physical page KDP prints; a TrimBox is reported as a measurement but does not replace it.

## Rules and sources

Page limits from [KDP Print Options](https://kdp.amazon.com/en_US/help/topic/G201834180) (US, 5 x 8 in rows):

| Format | Ink, paper | Min | Max |
|---|---|---|---|
| paperback | black, white | 24 | 828 |
| paperback | black, cream | 24 | 776 |
| paperback | premium color, white | 24 | 828 |
| paperback | standard color, white | 72 | 600 |
| hardcover | black or premium color | 75 | 550 |

The maximum is lower for some trim sizes; check the table for yours. The gate uses these baseline rows
for every trim and says so in the `limits_basis` measurement (trim-specific limits: a good first issue).

Bleed from [Set Trim Size, Bleed, and Margins](https://kdp.amazon.com/en_US/help/topic/GVBQ3CMEQW3W2VL6):
with bleed the page is trim width + 0.125 in and trim height + 0.25 in (6 x 9 becomes 6.125 x 9.25).

`page-claim` and `mixed-page-sizes` are heuristics: a listing that promises 100 pages for a 60-page book
invites refunds and complaints.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--format` | paperback | paperback or hardcover |
| `--ink` | black | black, standard-color, premium-color |
| `--paper` | white | white or cream |
| `--trim` | none | e.g. `6x9`; enables the page size check |
| `--claimed` | none | page count your listing states |
| `--metadata` | none | the kdp-metadata JSON; "N pages" in title or description are compared |

## Known limits

- Margins are not checked yet (the margin table is on the same KDP page: a good first issue).
