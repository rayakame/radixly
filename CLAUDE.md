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

Performance bars (measured by benchmarks/bench_base32768.py, i9-13900K,
performance governor, CPython 3.13 — protect these; regressions need a reason):
encode 0.112 µs / 187 B, 1880 MB/s at 64 KiB (flat to 1 MiB), 0.020 µs per-call
floor at 1 B (METH_O, no arg parsing — why the object layer must not add Python
call frames). 103x the pure-Python reference. Decode (measured M4): 0.196 µs /
187 B (legacy bar 0.37 beaten 1.9x), 1118 MB/s at 64 KiB (flat to 1 MiB),
0.017 µs floor at 1 B, 100x the reference — two-pass design's throughput cost
vs encode is known and accepted; single-pass-resize is the measured-decision
alternative if ever needed.

## Fixed decisions — do not relitigate

- C extension, not Rust/Cython. No abi3/limited API (one wheel per CPython version).
- CPython-only. **No pure-Python fallback shipped**; the reference implementation
  lives in `tests/` as the differential oracle and is never imported by the package.
- Decoding is always canonical and strict. No lenient mode.
- One extension module `radixly._core` (the engine room); public per-codec
  namespaces are thin Python modules. Multiple .c files later still link into the
  single extension.
- **Layout convention (decided M3, user's call): one folder per codec**, always,
  even one-file presets — `src/radixly/<codec>/` holds its `__init__.py` (public
  face), bespoke `.c` if any, generated `_tables.h` if any. Shared C engine lives
  in `src/radixly/_common/` (born M4 with errors.c — DecodeError + raise helper
  are engine-wide; user's call). `_core.c` stays a wiring hub (module init +
  method table + one exec slot per codec, engine slot first). Uniformity is
  deliberate: "where is X?" has one answer for every codec.
- Multi-phase module init (`PyModuleDef_Init`); table init goes in a `Py_mod_exec`
  slot when it arrives (M4).
- setuptools backend; extension declared via the experimental
  `[tool.setuptools] ext-modules` table in pyproject.toml (no setup.py). Revisit at
  M3 for build-time table codegen: commit a generated header vs switch to setup.py.
- Python floor >= 3.11. Exceptions root at ValueError; DecodeError carries position.
- encode() accepts any buffer-protocol object; str input raises TypeError.
- **DecodeError message contract (M4 review round, user's call — option c):** `message`
  stays keyword-only forever; `message=None` → generated text; `""` is a legal explicit
  message (reference tightened from truthiness to `is None`). Pickle/copy work via
  `__reduce__` + `__setstate__` (state carries the message) — never by making message
  positional. Both implementations must match.
- **Subinterpreters: not supported, and declared so** (M4 review round):
  `Py_mod_multiple_interpreters` NOT_SUPPORTED slot in `_core.c` (3.12+; 3.11 has no
  refusal mechanism for multi-phase modules — README documents it instead). The static
  globals (DecodeError type object, REV table) are the reason. If ever demanded:
  per-module state (`m_size > 0`, functions reach it via their module `self`) is the shape.
- **M6 API shape (user's rulings, 2026-08-26):** per-codec modules bind the raw C
  functions under bare names (base32768.encode — the module namespaces, like base64's
  prefixes do); root exports DecodeError and imports codec modules eagerly (the one .so
  loads anyway; registry guaranteed populated after `import radixly`). Codec = frozen
  slots dataclass in `_codec.py` — private on purpose: one public path per name, and a
  public `radixly.codec` would read like a codec named "codec" next to radixly.base32768.
  Size math (encoded_len = ceil(8n/15), max_bytes = floor(15N/8); integer arithmetic
  only, never floats) defined in the codec module, Codec fields hold those same objects.
  Registry: get_codec() with a helpful unknown-name error + CODECS MappingProxy, one
  dict behind both; registration explicit only — never automatic in __post_init__.
  **No typing Protocol through 1.0**: the one concrete Codec class is the interface;
  revisit only if a structurally different codec type (C-implemented, third-party)
  ever appears.
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
- **M2 — C API bootcamp: DONE.** Throwaway function written under both METH_O and
  METH_FASTCALL, all exit paths correct, then deleted with its spike branch as
  designed. Free rejection message for non-buffer args ("a bytes-like object is
  required, not 'str'") measured and judged sufficient for the charter.
- **M3 — base32768 encode in C: DONE.** Committed generated header (option A);
  per-codec layout born; encode byte-identical to the oracle (265 vectors,
  lengths 0-600 x 3 payload flavors, Hypothesis); conftest hook dedups vector
  parametrization; _core.pyi stub begun. Benchmarked 2.4x ahead of the legacy
  bars (see Performance bars above).
- **M4 — decode in C: DONE.** Two-pass decoder (validate-and-size, then fill):
  every reverse-table index behind the cp <= MAX_CHAR guard, surrogates die on
  painted cells, canonicality rule enforced in C (comment mirrored from the
  oracle). DecodeError is a full C heap type (position member, message getset,
  tp_init chaining to ValueError, GC delegation) in _common/errors.c with a
  goto-ladder raise helper. Error contract shared as data
  (tests/base32768/error_cases.py): both implementations pinned to the same
  (input, position) tables. Suite 6566 tests. Measured: see bars above.
- **M5 — hardening: DONE.** -std=c11 -Wall -Wextra pinned in the build metadata;
  -Werror rides dev/CI builds only (CFLAGS in nox sync — a stranger building the
  sdist under a future compiler must not fail). asan nox session: extension
  rebuilt under ASan+UBSan, non-editable install on purpose (editable envs share
  the one in-place .so), LD_PRELOAD'd runtime, PYTHONMALLOC=malloc (pymalloc
  arenas hide object overflows from ASan), leak detection off (CPython exits
  dirty by design); CI gate across the full 3.11–3.14 matrix. Fuzz suite
  (tests/base32768/test_fuzz.py): oracle-parity property over hostile inputs —
  raw-code-point strings incl. surrogates, alphabet-biased corruption fuzz,
  exhaustive 65,536 single-char sweep (256 accepted, pinned), multi-MB hostile
  tail. 6,571 tests, all clean under sanitizers. The planned every-length
  differential was already satisfied by the M3/M4 sweeps.
- **M6 — CURRENT** — Python object layer: Codec objects (bind C functions as instance
  attributes — no delegating def methods), registry, Protocol, max_bytes/encoded_len.
  Benchmark the wrapper cost before committing to layering.
- **M7** — contiguous-block factory in C + uro14/braille/hexagram (references in
  tests/ first; uro14's length prefix must provably catch truncation).
- **M8** — benchmark suite as product: honest README table, CI regression gates.
- **M9** — ship 1.0: cibuildwheel matrix, .pyi stubs + py.typed, docs stating the
  truncation caveat honestly (base32768 silently accepts ~50% of truncations).

## Commands

- Inner loop: `uv run pytest`; after editing C: `uv sync --reinstall-package radixly`
- Full check: `uv run nox` (reformat + pytest + pyright + tidy); CI gates:
  `nox -s format-check` and `nox -s lint`
- Build artifacts: `uv build` (wheel must contain `_core.*.so`, never the .c)
- Diagnostic when imports act weird: `python -c "import radixly._core; print(radixly._core.__file__)"`
  (src/ path is normal under the editable install; site-packages in nox/CI venvs)

## Testing standards (load-bearing — no shipped fallback means tests are the only guard)

Every test must be able to fail: ask "what would make this fail?" of each one.
Reference written first, C diffed against it byte-for-byte. Conformance vectors
from qntm. Hypothesis round-trips. Fuzz decode with hostile input (lone surrogates,
astral chars, empty, multi-MB). The tripwire test asserts the compiled extension
actually imported (suffix check via importlib.machinery.EXTENSION_SUFFIXES).
