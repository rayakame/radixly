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

To re-vendor: fetch the new file, reapply the edits, run the suite.
