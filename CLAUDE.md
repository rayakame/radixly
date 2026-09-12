# CLAUDE.md

## Rules

- This is a teaching project: the user writes the library code (C, Python API,
  tests, references) unless they explicitly hand a task over. Claude owns
  tooling: noxfile, CI, packaging, docs scaffolding, this file.
- Review bluntly: refcounts, bounds checks, error paths that leak or return
  NULL without an exception, vacuous tests. "Done" means compiled, imported,
  tests ran.
- Measure before optimizing; bounds checks on untrusted input are never traded.
- Design decisions: options and trade-offs, a lean, the user picks.
- No AI traces anywhere: no Co-Authored-By, no "generated with", not in
  commits, PRs, code or docs.
- Comments and docstrings: one short plain sentence, only where needed. Lint
  suppressions are `# ruff: ignore[rule-name]`, never `noqa`.

## Project

radixly: fast binary-to-text codecs for Python, hand-written C extension
(`radixly._core`), CPython 3.11+, no pure-Python fallback shipped. Codecs:
base32768 (qntm's spec, 15 bits/char), base65536 (qntm, 16 bits/char, mostly
astral), base2048 (qntm, 11 bits/char below U+1100), uro14 (own design, 14
bits/char from U+4E00 with a length prefix), braille (8), hexagram (6).
Candidates: base91, Z85.

## Fixed decisions

- One extension module; public per-codec modules are thin Python faces
  (`src/radixly/<codec>/_api.py` + `__init__.py`), shared C in `_common/`.
  Submodules import siblings directly, never `radixly` itself.
- No abi3, one wheel per CPython version. No subinterpreters (declared).
- Decoding is strict and canonical: one payload, one spelling. A final
  character carrying no payload bits is rejected (stricter than qntm's JS).
- `encode` takes any buffer, `str` raises TypeError. `DecodeError` is a
  ValueError with `position`; `message` is keyword-only.
- uro14's truncation guarantee is windowed at 16,384 bytes; every doc says so.
- Codec is a frozen dataclass, registry via `get_codec`/`CODECS`/`register`.
- Performance bars are the committed record
  (`benchmarks/results/i9-14900KF-performance.json`), rendered into README and
  docs; regressions need a reason, CI gates the C-vs-reference ratio.

## Commands

- `uv run pytest`; after editing C: `uv sync --reinstall-package radixly`
- `uv run nox` runs everything (reformat, pytest, pyright, verifytypes, tidy,
  lint, docs); `nox -s asan` for sanitizers; `nox -s docs-serve` for live docs
- Benchmarks: `uv run python -m benchmarks` (`--quick` for a smoke); record
  refresh on a clean tree adds `--json benchmarks/results/i9-14900KF-performance.json
  --graphs benchmarks/charts --inject README.md --docs docs/benchmarks`
- Version lives in `src/radixly/_about.py` only.

## Testing standards

Every test must be able to fail. Reference first, C diffed byte-for-byte
against it; qntm's vectors; Hypothesis round-trips; fuzz with hostile input
(surrogates, astral, empty, multi-MB); error contracts pinned as
(input, position) data shared by both implementations.
