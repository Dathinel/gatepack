# epub

**What it catches:** EPUB files that fail upload or validation: wrong `mimetype` entry, missing
`container.xml` or package document, missing title, language or identifier, files listed in the
manifest but absent, broken XHTML, an EPUB 3 package without a navigation document, and an author name
that differs from the one you expect.

**Input:** an `.epub` file.

## Rules and sources

- [EPUB 3.3, OCF ZIP container](https://www.w3.org/TR/epub-33/#sec-zip-container-mime): the first entry is
  `mimetype`, stored without compression, containing `application/epub+zip`.
- [EPUB 3.3, package metadata](https://www.w3.org/TR/epub-33/#sec-pkg-metadata): `dc:identifier`,
  `dc:title` and `dc:language` are required.
- [EPUBCheck](https://github.com/w3c/epubcheck) is the reference validator. When it is installed
  (`epubcheck` on PATH, or `GATEPACK_EPUBCHECK=/path/to/epubcheck.jar`), its ERROR and FATAL lines become
  FAIL findings. Without it, only the built-in checks run and the `epubcheck` measurement says so.

`author-mismatch` and `too-short` compare against your own expectations, passed as options.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--author` | none | expected `dc:creator` (same name as the cover and listing) |
| `--min-words` | 0 | fail below this word count |
| `--epubcheck` | auto | path to `epubcheck` or `epubcheck.jar` |
