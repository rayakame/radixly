# The standard library's own base64 tests

`test_stdlib_base64.py` is `Lib/test/test_base64.py` from CPython 3.14, vendored under the
Python Software Foundation License (`LICENSE-PSF.txt`) and run against `radixly.compat.base64`.
Passing it is what "drop-in" means here.

Edits against the original, and nothing else:

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

To re-vendor: fetch the new file, reapply the edits without reformatting, run the suite.
