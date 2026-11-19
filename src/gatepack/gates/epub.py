"""epub: structural checks of an EPUB file, plus W3C EPUBCheck when it is installed.

Built-in checks cover the errors that most often stop an upload: the mimetype entry, container.xml,
the package document (title, language, identifier), missing manifest files, broken XHTML.
EPUBCheck is the reference validator; when found, its errors are reported as FAIL too.
"""
from __future__ import annotations

import os
import posixpath
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from ..core import Finding, Gate, GateError, Option, Source

OCF = Source("W3C EPUB 3.3: OCF ZIP container and mimetype file", "https://www.w3.org/TR/epub-33/#sec-zip-container-mime")
PKG = Source("W3C EPUB 3.3: package document metadata", "https://www.w3.org/TR/epub-33/#sec-pkg-metadata")
EPUBCHECK = Source("W3C EPUBCheck (reference validator)", "https://github.com/w3c/epubcheck")

MAX_ENTRIES = 10_000           # an EPUB with more entries than this is refused, not unpacked
MAX_MEMBER = 64 * 1024 * 1024  # bytes per file after decompression
MAX_TOTAL = 512 * 1024 * 1024  # bytes for the whole archive after decompression

NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container", "opf": "http://www.idpf.org/2007/opf",
      "dc": "http://purl.org/dc/elements/1.1/"}


def _epubcheck_cmd(explicit):
    if explicit:
        return [explicit] if not explicit.endswith(".jar") else ["java", "-jar", explicit]
    env = os.environ.get("GATEPACK_EPUBCHECK")
    if env:
        return ["java", "-jar", env] if env.endswith(".jar") else [env]
    found = shutil.which("epubcheck")
    return [found] if found else None


def _run_epubcheck(cmd, path):
    try:
        r = subprocess.run([*cmd, str(path)], capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [Finding("WARN", "epubcheck-not-run", f"EPUBCheck could not run: {exc}")]
    text = (r.stdout + r.stderr).decode("utf-8", "replace")
    msgs = [ln.strip() for ln in text.splitlines() if re.match(r"\s*(ERROR|FATAL)\b", ln)]
    out = [Finding("FAIL", "epubcheck", m[:300], "standard") for m in msgs[:20]]
    if r.returncode != 0 and not out:
        out.append(Finding("FAIL", "epubcheck", f"EPUBCheck exited with {r.returncode}", "standard"))
    return out


def _safe_name(name):
    """False for absolute paths and names that climb out of the archive."""
    norm = posixpath.normpath(name.replace("\\", "/"))
    return not (norm.startswith(("/", "../")) or norm == ".." or re.match(r"^[A-Za-z]:", norm))


def _body_words(data):
    """Words of visible body text: <head>, <script> and <style> are left out."""
    root = ET.fromstring(data)
    body = root.find("{http://www.w3.org/1999/xhtml}body")
    if body is None:
        return 0
    for tag in ("script", "style"):
        for el in body.iter("{http://www.w3.org/1999/xhtml}" + tag):
            el.text = ""
    return len(" ".join(body.itertext()).split())


def check(path, author=None, min_words=0, epubcheck=None):
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {path}")
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile as exc:
        raise GateError(f"not a ZIP/EPUB file: {exc}") from exc
    with z:
        return _check_zip(z, p, author, min_words, epubcheck)


def _check_zip(z, p, author, min_words, epubcheck):
    out: list[Finding] = []
    infos = z.infolist()
    names = [i.filename for i in infos]
    measured = {"files": len(names)}
    total = sum(i.file_size for i in infos)
    if len(infos) > MAX_ENTRIES or total > MAX_TOTAL or any(i.file_size > MAX_MEMBER for i in infos):
        raise GateError(f"refusing to unpack: {len(infos)} entries, {total} bytes uncompressed "
                        f"(limits {MAX_ENTRIES} entries, {MAX_MEMBER} bytes per file, {MAX_TOTAL} total)")
    if len(set(names)) != len(names):
        out.append(Finding("FAIL", "duplicate-entry", "the ZIP has two entries with the same name", "standard"))
    bad = [n for n in names if not _safe_name(n)]
    if bad:
        out.append(Finding("FAIL", "unsafe-path", f"ZIP entry escapes the container: {bad[0]}", "standard"))

    first = infos[0] if infos else None
    if not first or first.filename != "mimetype":
        out.append(Finding("FAIL", "mimetype-first", "the first ZIP entry must be the file 'mimetype'", "standard"))
    else:
        if first.compress_type != zipfile.ZIP_STORED:
            out.append(Finding("FAIL", "mimetype-compressed", "'mimetype' must be stored without compression", "standard"))
        if z.read("mimetype") != b"application/epub+zip":
            out.append(Finding("FAIL", "mimetype-content", "'mimetype' must contain exactly application/epub+zip", "standard"))

    if "META-INF/container.xml" not in names:
        out.append(Finding("FAIL", "no-container", "META-INF/container.xml is missing", "standard"))
        return out, measured
    try:
        root = ET.fromstring(z.read("META-INF/container.xml"))
        opf_path = root.find(".//c:rootfile", NS).get("full-path")
    except (ET.ParseError, AttributeError):
        out.append(Finding("FAIL", "bad-container", "container.xml has no readable rootfile entry", "standard"))
        return out, measured
    if opf_path not in names:
        out.append(Finding("FAIL", "no-package", f"package document {opf_path} is missing", "standard"))
        return out, measured
    try:
        opf = ET.fromstring(z.read(opf_path))
    except ET.ParseError as exc:
        out.append(Finding("FAIL", "bad-package", f"package document is not well-formed XML: {exc}", "standard"))
        return out, measured
    if opf.tag != "{%s}package" % NS["opf"]:
        out.append(Finding("FAIL", "bad-package", "package document root is not an OPF <package>", "standard"))
        return out, measured

    measured["epub_version"] = opf.get("version")
    meta = opf.find("opf:metadata", NS)
    for tag in ("title", "language", "identifier"):
        el = meta.find(f"dc:{tag}", NS) if meta is not None else None
        if el is None or not (el.text or "").strip():
            out.append(Finding("FAIL", f"missing-{tag}", f"package metadata has no dc:{tag}", "standard"))
    creator = meta.find("dc:creator", NS) if meta is not None else None
    creator_text = (creator.text or "").strip() if creator is not None else ""
    measured["creator"] = creator_text
    if author is not None and creator_text != author.strip():
        out.append(Finding("FAIL", "author-mismatch", f'dc:creator is "{creator_text}", expected "{author}" '
                           "(use the same name as on the cover and in the listing)"))

    base = posixpath.dirname(opf_path)
    manifest = {}
    items = opf.findall("opf:manifest/opf:item", NS)
    if not items:
        out.append(Finding("FAIL", "no-manifest", "package has no manifest items", "standard"))
    for item in items:
        href = item.get("href", "")
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            continue  # remote resource (http:, https:, ...): not a file inside the container
        local = posixpath.normpath(posixpath.join(base, unquote(href.split("#")[0])))
        manifest[item.get("id")] = (local, item.get("media-type", ""), item.get("properties", ""))
        if not _safe_name(local):
            out.append(Finding("FAIL", "unsafe-path", f"manifest item points outside the container: {href}", "standard"))
        elif local not in names:
            out.append(Finding("FAIL", "missing-file", f"manifest lists {local} but the file is not in the EPUB", "standard"))
    spine = [ref.get("idref") for ref in opf.iterfind("opf:spine/opf:itemref", NS)]
    if not spine:
        out.append(Finding("FAIL", "no-spine", "package has no reading order (empty or missing <spine>)", "standard"))
    for idref in spine:
        if idref not in manifest:
            out.append(Finding("FAIL", "bad-spine", f"spine refers to unknown manifest id {idref}", "standard"))
    if (opf.get("version") or "").startswith("3") and not any("nav" in v[2].split() for v in manifest.values()):
        out.append(Finding("FAIL", "no-nav", "EPUB 3 package has no navigation document (item with properties=\"nav\")",
                           "standard"))

    words = 0
    for key, (local, mtype, props) in manifest.items():
        if mtype != "application/xhtml+xml" or local not in names:
            continue
        try:
            n = _body_words(z.read(local))
        except ET.ParseError as exc:
            out.append(Finding("FAIL", "bad-xhtml", f"{local} is not well-formed XHTML: {exc}", "standard"))
            continue
        if key in spine and "nav" not in props.split():
            words += n
    measured["words"] = words
    if min_words and words < min_words:
        out.append(Finding("FAIL", "too-short",
                           f"{words} words of body text in the reading order, below your minimum of {min_words}"))

    cmd = _epubcheck_cmd(epubcheck)
    if cmd:
        out.extend(_run_epubcheck(cmd, p))
        measured["epubcheck"] = "ran"
    else:
        # Not a finding: the built-in checks still ran. The text report shows this measurement.
        measured["epubcheck"] = "not found, built-in checks only (set GATEPACK_EPUBCHECK to epubcheck.jar)"
    return out, measured


GATE = Gate(
    id="epub",
    title="EPUB structure",
    summary="EPUB container, package metadata, manifest, XHTML well-formedness, author name; runs EPUBCheck if installed.",
    category="kdp",
    sources=(OCF, PKG, EPUBCHECK),
    check=check,
    options=(
        Option("author", str, None, "expected author name (must match dc:creator)"),
        Option("min_words", int, 0, "fail below this many words of body text"),
        Option("epubcheck", str, None, "path to epubcheck or epubcheck.jar"),
    ),
)
