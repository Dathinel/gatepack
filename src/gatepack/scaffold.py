"""`gatepack new <id>`: writes the files a new gate needs, inside a gatepack checkout."""
from __future__ import annotations

from pathlib import Path

GATE_TEMPLATE = '''"""{id}: one sentence on what this gate catches.

Rule: quote or summarise the rule here, and put the link in SOURCES below.
"""
from __future__ import annotations

from pathlib import Path

from ..core import Finding, Gate, GateError, Option, Source

RULE = Source("Name of the official page or standard", "https://example.com/replace-with-the-real-source")


def check(path, limit=1.0):
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {{path}}")
    out = []
    # TODO: replace this line with a real measurement of the file. Until then the gate reports ERROR,
    # so it can never pass by accident.
    raise GateError("{id} is not implemented yet")
    measured_value = 0.0
    if measured_value > limit:
        out.append(Finding("FAIL", "{id}", f"value {{measured_value}} is above {{limit}}", "platform-rule"))
    return out, {{"value": measured_value}}


GATE = Gate(
    id="{id}",
    title="{title}",
    summary="One line shown by `gatepack list`.",
    category="{category}",
    sources=(RULE,),
    check=check,
    options=(Option("limit", float, 1.0, "what the limit means and its unit"),),
)
'''

DOC_TEMPLATE = """# {id}

**What it catches:** one or two sentences.

**Rule and source:** quote the rule and link the official page. If the threshold is your own
judgment rather than a published rule, say so and mark findings with basis "heuristic".

| Option | Default | Meaning |
|---|---|---|
| `--limit` | 1.0 | ... |

**Fixtures:** `tests/fixtures/{id}/pass/` and `tests/fixtures/{id}/fail/`.

**Known limits:** what this gate does not see.
"""


def find_root(start: Path) -> Path:
    for d in (start, *start.parents):
        pp = d / "pyproject.toml"
        if pp.is_file() and 'name = "gatepack"' in pp.read_text(encoding="utf-8"):
            return d
    raise FileNotFoundError("run `gatepack new` inside a gatepack source checkout (no pyproject.toml found)")


def create_gate(start: Path, gate_id: str, category: str = "other") -> list[Path]:
    root = find_root(start)
    mod = gate_id.replace("-", "_")
    title = gate_id.replace("-", " ").capitalize()
    files = {
        root / "src" / "gatepack" / "gates" / f"{mod}.py": GATE_TEMPLATE.format(id=gate_id, title=title, category=category),
        root / "docs" / "gates" / f"{gate_id}.md": DOC_TEMPLATE.format(id=gate_id),
        root / "tests" / "fixtures" / gate_id / "pass" / ".gitkeep": "",
        root / "tests" / "fixtures" / gate_id / "fail" / ".gitkeep": "",
    }
    for path in files:
        if path.exists():
            raise FileNotFoundError(f"{path} already exists")
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return [p.relative_to(root) for p in files]
