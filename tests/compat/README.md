# The standard library's own base64 tests

`test_stdlib_base64.py` is `Lib/test/test_base64.py` from CPython v3.14.6 (upstream sha256
`681d2ca1cd1e937fc5b27b43078ca39ac55068ed0fe3577c70e92fac4fb40ba3`), vendored under the Python
Software Foundation License (`LICENSE-PSF.txt`) and run against `radixly.compat.base64`. Passing
it is what "drop-in" means here; 34 of its 35 test methods have a ported function as their subject,
and the one that does not, `test_ErrorHeritage`, checks `binascii.Error`'s own class hierarchy.

Edits against the original, and nothing else:

- A five-line comment at the top names the source, the license and these edits.
- `import base64` became `from radixly.compat import base64`; `os` and the `test.support`
  imports are gone.
- `LazyImportTest` and `TestMain` are removed: they test CPython's lazy imports and the
  `python -m base64` command line, neither of which the drop-in provides.
- `assertIsSubclass` is spelled `assertTrue(issubclass(...))` so the suite also runs on 3.11.
- `sys` is imported; the three z85 tests skip, and `test_decode_nonascii_str` leaves z85 out, on
  interpreters before 3.13, where the standard library has no z85. The gate is the version, not the
  module under test, so a drop-in that lost z85 on 3.13 fails instead of skipping.

The file is excluded from ruff, so it keeps upstream's formatting byte for byte; `diff` against the
original shows only the edits above.

- The module skips from 3.15 on: that release rewrote `base64`, and `test_stdlib_base64_py315.py` describes it.

`test_stdlib_base64_py315.py` is `Lib/test/test_base64.py` from CPython v3.15.1 (upstream sha256
`b112b3c06d757cb77ad9e74c20050a0c6619781b849166616fcc3108c75b2c3e`), vendored the same way and run from
3.15 on. Its edits:

- A five-line comment at the top names the source, the license and these edits.
- `import base64` became `from radixly.compat import base64`; `os` and the `test.support` imports are gone,
  and with them `LazyImportTest` and `TestMain`.
- `from test.support.hypothesis_helper import hypothesis` became `import hypothesis` and
  `import hypothesis.strategies`; the suite's property tests run on the real Hypothesis the project depends on.
- `check_impl_detail` is a local function returning `True`: the suite runs on CPython only.
- The module skips before 3.15 with `unittest.SkipTest`.

To re-vendor: fetch the new file, reapply the edits without reformatting, run the suite.
