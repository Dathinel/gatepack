# kdp-metadata

**What it catches:** metadata that KDP rejects or that gets a live book flagged after an edit:
trademarked terms, sales-rank claims, contact details in the description, review requests,
print-only formats (coloring, puzzles, journals) listed as Kindle eBooks, a trim size in the text that
differs from the real one, conflicting "N designs" counts, and working notes left in the fields.

**Input:** a JSON file.

```json
{"format": "paperback", "trim": "6x9", "title": "...", "subtitle": "...",
 "description": "<p>...</p>", "keywords": ["...", "..."]}
```

`format` is `paperback`, `hardcover` or `kindle ebook`. `trim` is optional for eBooks. Text fields must be
strings and `keywords` a list of strings; anything else is reported as ERROR rather than guessed.

## Rules and sources

| Code | Level | Basis | Rule |
|---|---|---|---|
| `title-too-long` | FAIL | platform rule | "Your title and subtitle together must be fewer than 200 characters." ([Metadata Guidelines](https://kdp.amazon.com/en_US/help/topic/G201097560)) |
| `html-tag` | FAIL | platform rule | No HTML tags in title or keywords |
| `sales-rank-claim` | FAIL | platform rule | No reference to sales rank such as "bestselling" |
| `promotion-word` | WARN | platform rule | No promotional "free"; only a warning because "sugar free" is a topic, not a promotion |
| `trademark` | FAIL for terms in your `--brands` file, WARN for the built-in example list | platform rule | No unauthorized reference to a trademarked term; in keywords, no "brands you don't own" ([Keywords help](https://kdp.amazon.com/en_US/help/topic/G201298500)). The gate cannot know whether you are authorized, so only your own list blocks |
| `contact-info` | FAIL | platform rule | Description must not contain phone numbers, e-mail addresses or website URLs (including `<a href>` links) |
| `review-request` | FAIL | platform rule | Description must not request customer reviews |
| `testimonial` | WARN | platform rule | Description must not contain reviews, quotes or testimonials (detected heuristically, so WARN) |
| `time-sensitive` | WARN | platform rule | No time-sensitive wording such as "on sale" or "available now" |
| `too-many-keywords` | FAIL | platform rule | "Use up to seven keywords or short phrases." |
| `quoted-keyword` | WARN | platform rule | No quotation marks around search terms |
| `print-only-content` | FAIL when the description names the format ("coloring pages", "write in the book"), WARN when only the title does ("Sudoku Solving Techniques" may be prose) | platform rule | Puzzle books, blank journals, pattern books and coloring books are "unsuited for reading on Kindle" and "may be rejected upon submission or removed from sale" ([Guide to Kindle Content Quality](https://kdp.amazon.com/en_US/help/topic/G200952510)) |
| `trim-mismatch` | FAIL | heuristic | Trim size named in the text differs from `trim` |
| `conflicting-counts` | FAIL | heuristic | Two different counts of the same thing ("50 designs" and "100 designs") |
| `working-note` | FAIL | heuristic | TODO, TBD, lorem ipsum, `{{placeholder}}`, `[insert ...]` left in a field |
| `promise-word` | WARN | heuristic | "complete", "ultimate", "definitive" in the title: check the content delivers it |
| `near-duplicate` | FAIL | heuristic | 85% or more similar to a title in your `--catalog` file |

Rows marked "platform rule" without a link come from the
[Metadata Guidelines for Books](https://kdp.amazon.com/en_US/help/topic/G201097560) (title, description)
or the [Keywords help page](https://kdp.amazon.com/en_US/help/topic/G201298500) (keywords).

## Options

| Option | Default | Meaning |
|---|---|---|
| `--brands FILE` | none | extra trademark terms or regexes, one per line, `#` for comments |
| `--default-brands false` | true | turn off the built-in list |
| `--catalog FILE` | none | CSV (comma, semicolon or tab) with a `title` column: your other books |
| `--max-keywords N` | 7 | keyword limit |

The built-in trademark list is a short **example** of well-known marks so the mechanism has something to
match. It is not a trademark database. Add the marks that matter in your niche with `--brands`.

## Known limits

- Text rules are regular expressions. They catch the common cases, not every phrasing.
- Passing this gate does not mean KDP will accept the book. KDP also reviews content and covers by hand.
