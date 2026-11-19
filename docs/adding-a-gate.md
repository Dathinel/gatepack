# Adding a gate

A gate is one Python module, one docs page and at least two test files. Most gates take under an hour.

## 1. Pick a rule you can cite

Good gates check something a platform or standard writes down, for example "YouTube thumbnails are
1280 x 720 and under 2 MB". Find the official page first and keep its URL. If there is no written rule
and you want to check a threshold of your own (like "no 2-second silences"), that is fine: mark it
`heuristic` and explain the reasoning in the docs page.

Out of scope: anything that logs in, scrapes a website, uploads or publishes. Gates read local files.

## 2. Generate the skeleton

```bash
pip install -e ".[dev]"
gatepack new youtube-thumbnail --category image
```

This writes:

| File | What to put there |
|---|---|
| `src/gatepack/gates/youtube_thumbnail.py` | the `check()` function and the `GATE` description |
| `docs/gates/youtube-thumbnail.md` | what it catches, the rule quoted with its link, options, known limits |
| `tests/fixtures/youtube-thumbnail/pass/` | at least one file that must PASS |
| `tests/fixtures/youtube-thumbnail/fail/` | at least one file that must FAIL |

Then add `"youtube_thumbnail"` to `GATE_MODULES` in `src/gatepack/gates/__init__.py`.

## 3. Write `check()`

```python
def check(path, max_mb=2.0):
    ...
    return findings, measurements
```

- Return a list of `Finding(level, code, message, basis)` and a dict of the numbers you measured.
- `level` is `PASS`, `WARN` or `FAIL`. Use WARN when the file might be fine (you cannot be sure from
  the data), FAIL when the rule is clearly broken.
- `basis` is `platform-rule`, `standard` or `heuristic`.
- Raise `GateError("...")` when the gate cannot run (missing file, missing tool, unreadable input).
  The result then becomes ERROR with exit code 2.
- Every option needs a default and help text; the CLI flags are generated from them.
- Standard library first. If you need a package, make it optional (like Pillow for the cover gate) and
  raise `GateError` with the install command when it is missing.
- List what the gate needs in `requires=` (executables such as `"ffmpeg"`, or modules registered in
  `REQUIREMENT_MODULES` in `core.py`). Tests skip a gate whose requirements are missing.
- The generated `check()` raises "not implemented" until you replace the TODO, so a half-written gate
  can never report PASS.
- For audio and video, use the helpers in `_media.py` (`probe`, `run_ffmpeg`): they map the same stream
  in every call and keep ffmpeg on local files.

## 4. Fixtures

Keep fixture files tiny (a few KB) and make them reproducible: add the code that creates them to
`scripts/make_fixtures.py`. A fixture can have a sidecar `name.ext.args.json` with gate options:

```json
{"trim": "6x9", "pages": 120}
```

Never commit real customer files, real book interiors or anything you do not have the right to share.

## 5. Run the tests

```bash
pytest
```

`tests/test_registry.py` checks the contract (id format, sources, docs page linking every source,
option help). `tests/test_fixtures.py` runs every fixture.
