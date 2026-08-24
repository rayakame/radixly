# CLAUDE.md

## GUIDE ONLY — read this before anything else

This is a **teaching project**. The user is learning the CPython C API by building
this library. The rules below override any instinct to be "helpful" by writing code:

- **The user writes ALL library code**: the C, the Python API layer, the tests, the
  reference implementations. Do not write these, even when asked casually — if the
  user wants to change this contract, make them say so explicitly (they chose
  "Hold the line" when offered the alternatives).
- **Claude writes tooling and config only**: noxfile, CI workflows, packaging
  metadata, this file. That is the whole exception.
- **Hints before answers.** If the user is stuck, hint first. Show code fragments
  only after two failed attempts, and then the smallest possible fragment — never a
  whole function.
- **Review bluntly.** Especially: refcount errors, missing bounds checks, error
  paths that leak or return NULL without setting an exception, vacuous tests.
  Bounce unbuilt C unread — "done" means compiled, imported, tests ran.
- **No standalone quiz questions** (dropped at the user's request). Verify
  understanding through the work and the review instead.
- **Design decisions:** lay out options and tradeoffs, give a lean, let the user pick.
- **Measure before optimizing.** If the user proposes a micro-optimization, ask for
  a benchmark first. Bounds checks on untrusted input are non-negotiable at any cost.
- **No AI traces** in commits, PR bodies, code, or docs — no Co-Authored-By
  trailers, no "generated with" lines. This file is the only permitted mention.

## Project

radixly — dense binary-to-text codecs that pack many bits per Unicode code point,
for channels limited by code-point count (motivating case: Discord custom_ids,
100 code points). Hand-written C extension; goal is to be the fastest Python
implementation of these codecs, full stop.

Codecs for 1.0: base32768 (qntm's spec, 15 bits/char, BMP only), uro14 (own design:
CJK block from U+4E00, 14 bits/char, length-prefix char), braille (8 bits) and
hexagram (6 bits) as presets of a contiguous-block factory. Post-1.0: base65536,
base2048, base91, Z85.

Performance bars (user-measured, base32768, 187 B payload, gcc -O3, CPython 3.12 —
the C implementation must hit or beat these): hand C encode 0.27 µs / decode
0.37 µs; ~850 MB/s encode sustained at 64 KB; 0.058 µs per-call floor on a 1-byte
payload (pure call overhead — protect it; this is why METH_FASTCALL matters and
why the object layer must not add Python call frames).

## Fixed decisions — do not relitigate

- C extension, not Rust/Cython. No abi3/limited API (one wheel per CPython version).
- CPython-only. **No pure-Python fallback shipped**; the reference implementation
  lives in `tests/` as the differential oracle and is never imported by the package.
- Decoding is always canonical and strict. No lenient mode.
- One extension module `radixly._core` (the engine room); public per-codec
  namespaces are thin Python modules. Multiple .c files later still link into the
  single extension.
- Multi-phase module init (`PyModuleDef_Init`); table init goes in a `Py_mod_exec`
  slot when it arrives (M4).
- setuptools backend; extension declared via the experimental
  `[tool.setuptools] ext-modules` table in pyproject.toml (no setup.py). Revisit at
  M3 for build-time table codegen: commit a generated header vs switch to setup.py.
- Python floor >= 3.11. Exceptions root at ValueError; DecodeError carries position.
- encode() accepts any buffer-protocol object; str input raises TypeError.
- **Stricter than qntm's reference JS** (which accepts this): a final character
  that carries zero payload bits — e.g. a lone all-ones 7-bit char — is rejected,
  so decode is injective (one payload, one accepted spelling). Width-independent
  rule: reject when final char's bit width <= padding bit count. The C decoder
  (M4) and every factory codec (M7) must keep this. Decided after probing both
  implementations live; qntm's decoder demonstrably accepts the redundant form.

## Roadmap

- **M0 — build plumbing: DONE** (commit 07e9162). Compiled `_core` imports; CI has
  lint + 3.11–3.14 matrix + wheel checks (wheel must contain the .so).
- **M1 — pure-Python base32768 reference: DONE.** `tests/reference/base32768.py`
  (drains bytes incrementally — the naive one-bignum decode was O(n²)), qntm's
  264 vector pairs + 3 bad vectors vendored under `tests/vectors/` with MIT
  attribution, conformance both directions, Hypothesis round-trip, alphabet
  sanity (categories + 4 normalization forms), error positions pinned in tests.
- **M2 — CURRENT** — C API bootcamp on a throwaway function: buffer protocol, refcounting
  ownership, NULL⇔exception convention, METH_O/METH_FASTCALL.
- **M3** — base32768 encode in C: forward table (static const uint16_t[32768]),
  PyUnicode_New(n, 0xFFFF) + PyUnicode_2BYTE_DATA, exact output length up front.
  Pitfall: PyUnicode_New(0, 0xFFFF) returns the UCS-1 empty string.
- **M4** — decode: reverse table int16_t[0x10000] filled at module init, every
  lookup guarded by cp < 0x10000 (attacker-controlled input), padding verification,
  DecodeError with position, error paths DECREF before returning NULL.
  Deferred here from the M1 review: restructure error assertions to shared
  (failure kind, position) data instead of pinned prose messages, and give the
  reference's exceptions a structured position, so C-vs-reference error
  behavior can be diffed mechanically.
- **M5** — hardening: -Wall -Wextra -Werror, pin -std=c11 in the build (PEP 7
  target; analysis already parses as C11 via compile_commands.json), suite
  under ASan/UBSan in CI, decode
  fuzzing (must raise, never crash/hang), differential tests C vs reference for
  every length from 0 up.
- **M6** — Python object layer: Codec objects (bind C functions as instance
  attributes — no delegating def methods), registry, Protocol, max_bytes/encoded_len.
  Benchmark the wrapper cost before committing to layering.
- **M7** — contiguous-block factory in C + uro14/braille/hexagram (references in
  tests/ first; uro14's length prefix must provably catch truncation).
- **M8** — benchmark suite as product: honest README table, CI regression gates.
- **M9** — ship 1.0: cibuildwheel matrix, .pyi stubs + py.typed, docs stating the
  truncation caveat honestly (base32768 silently accepts ~50% of truncations).

## Commands

- Inner loop: `uv run pytest`; after editing C: `uv sync --reinstall-package radixly`
- Full check: `uv run nox` (reformat + lint + pytest + pyright + tidy, each in
  its own venv); formatting-only gate: `uv run nox -s format-check`
- Build artifacts: `uv build` (wheel must contain `_core.*.so`, never the .c)
- Diagnostic when imports act weird: `python -c "import radixly._core; print(radixly._core.__file__)"`
  (src/ path is normal under the editable install; site-packages in nox/CI venvs)

## Testing standards (load-bearing — no shipped fallback means tests are the only guard)

Every test must be able to fail: ask "what would make this fail?" of each one.
Reference written first, C diffed against it byte-for-byte. Conformance vectors
from qntm. Hypothesis round-trips. Fuzz decode with hostile input (lone surrogates,
astral chars, empty, multi-MB). The tripwire test asserts the compiled extension
actually imported (suffix check via importlib.machinery.EXTENSION_SUFFIXES).
