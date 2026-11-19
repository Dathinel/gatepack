"""Command line: `gatepack list`, `gatepack check <gate> <file>`, `gatepack new <gate-id>`."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__
from .gates import all_gates
from .scaffold import create_gate


def _add_gate_options(parser: argparse.ArgumentParser, gate) -> None:
    for opt in gate.options:
        flag = "--" + opt.name.replace("_", "-")
        default = f" (default: {opt.default})" if opt.default is not None else ""
        parser.add_argument(flag, dest=opt.name, type=opt.type, choices=opt.choices, default=None,
                            help=opt.help + default)


def build_parser() -> argparse.ArgumentParser:
    gates = all_gates()
    p = argparse.ArgumentParser(prog="gatepack", description="Check files before you publish them.")
    p.add_argument("--version", action="version", version=f"gatepack {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    lp = sub.add_parser("list", help="list the available gates")
    lp.add_argument("--json", action="store_true", help="machine-readable output")

    cp = sub.add_parser("check", help="run one gate on one or more files")
    gsub = cp.add_subparsers(dest="gate", required=True, metavar="<gate>")
    for gate in gates.values():
        gp = gsub.add_parser(gate.id, help=gate.summary, description=gate.summary)
        gp.add_argument("files", nargs="+", metavar="FILE")
        gp.add_argument("--json", action="store_true", help="print JSON instead of text")
        gp.add_argument("--strict", action="store_true", help="exit 1 on WARN as well as FAIL")
        _add_gate_options(gp, gate)

    np_ = sub.add_parser("new", help="create the skeleton of a new gate (run inside a gatepack checkout)")
    np_.add_argument("gate_id", help="lowercase id with dashes, e.g. youtube-thumbnail")
    np_.add_argument("--category", default="other", help="kdp, video, image, ... (default: other)")
    return p


def _cmd_list(args) -> int:
    gates = all_gates()
    if args.json:
        print(json.dumps([{"id": g.id, "title": g.title, "category": g.category, "summary": g.summary,
                           "requires": list(g.requires), "sources": [s.url for s in g.sources]}
                          for g in gates.values()], indent=2))
        return 0
    width = max(len(g) for g in gates)
    for g in gates.values():
        print(f"{g.id:<{width}}  {g.category:<6} {g.summary}")
    return 0


def _cmd_check(args) -> int:
    gate = all_gates()[args.gate]
    opts = {o.name: getattr(args, o.name) for o in gate.options}
    results = [gate.run(f, **opts) for f in args.files]
    if args.json:
        payload = [r.to_dict() for r in results]
        print(json.dumps(payload[0] if len(payload) == 1 else payload, indent=2, ensure_ascii=False, default=str))
    else:
        print("\n\n".join(r.to_text() for r in results))
    return max(r.exit_code(args.strict) for r in results)


def _cmd_new(args) -> int:
    if not re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", args.gate_id):
        print("gate id must be lowercase letters, digits and single dashes, e.g. youtube-thumbnail", file=sys.stderr)
        return 2
    if args.gate_id in all_gates():
        print(f"gate {args.gate_id} already exists", file=sys.stderr)
        return 2
    try:
        created = create_gate(Path.cwd(), args.gate_id, args.category)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for path in created:
        print(f"created {path}")
    mod = args.gate_id.replace("-", "_")
    print(f'\nNext: add "{mod}" to GATE_MODULES in src/gatepack/gates/__init__.py, write the rule, '
          "add PASS/FAIL fixtures, run pytest. See docs/adding-a-gate.md.")
    return 0


def _utf8_output() -> None:
    """Redirected output on Windows defaults to a legacy code page; findings may quote any character."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty() and (stream.encoding or "").lower().replace("-", "") != "utf8":
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    args = build_parser().parse_args(argv)
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "check":
        return _cmd_check(args)
    return _cmd_new(args)

