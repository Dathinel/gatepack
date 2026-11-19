## What this changes

<!-- One gate per pull request. Link the issue if there is one: Closes #123 -->

## Rule source

<!-- Link to the platform page or standard, or "heuristic" with a one-line reason. -->

## Checklist

- [ ] One gate (or one fix) in this pull request
- [ ] Source linked in the module and in `docs/gates/<gate-id>.md`
- [ ] At least one PASS and one FAIL fixture, small and reproducible (`scripts/make_fixtures.py`)
- [ ] `pytest` passes locally
- [ ] The gate reads local files only: no network, login, scraping, upload or publishing
- [ ] No private data in fixtures (names, titles, account details)
