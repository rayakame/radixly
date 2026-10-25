# Standard library drop-in

`radixly.compat.base64` is the standard library's `base64` module with the same
names, arguments, results and errors, every function in C. Swap the import, keep
the behavior.

- **Use it** for code that already calls `base64` and is not going to be
  rewritten: a vendored module, a dependency, a call site three layers down.
- **Skip it** in new code, which wants the strict codecs instead. See
  {doc}`../guides/choosing-a-codec`.
- **The numbers**, every function at two sizes: {doc}`performance`.

## Is the swap worth it?

Speed is the only reason to swap, and it depends on which functions the code
calls.

| what the code calls | gain at 64 KiB | verdict |
|---|---|---|
| `b32`, `b32hex` and the 85 family | 54x to 115x | swap |
| `b16`, `b64`, `standard_b64`, `urlsafe_b64`, `encodebytes`, `decodebytes` | 1.04x to 5.88x | swap for the contract, not the clock |
| `encode`, `decode`, the file-object pair | 0.57x to 0.80x | keep the standard library |

The standard library writes the first group as Python loops and the second as a
thin wrapper around `binascii`, so the port has a loop to replace in one and only
a wrapper to remove in the other.

## Swapping the import

At a call site the import is the whole change:

```python
from radixly.compat import base64

base64.b32encode(b"hello")           # b'NBSWY3DP', as the standard library returns it
base64.b32decode("nbswy3dp", True)   # b'hello', casefold and all
```

Code you cannot edit takes the drop-in through `sys.modules`, before anything
imports the standard library's module:

```python
import sys

import radixly.compat.base64

sys.modules["base64"] = radixly.compat.base64  # every later import base64 gets the port
```

:::{warning}
The surface is `base64.__all__`. `MAXLINESIZE`, `MAXBINSIZE`, `bytes_types`,
`main` and the `binascii` and `struct` references are not carried over, so a
process-wide swap breaks code that reads `base64.MAXLINESIZE`. The missing `main`
also rules the port out as a stand-in for `runpy.run_module("base64")`.
:::

## What matches

- **The test suite.** CPython's own `test_base64` runs against the port, and a
  second suite compares every function with the standard library's on random and
  hostile input, down to the exception type, its message, and the context a
  `raise ... from None` keeps hidden behind it.
- **The errors.** Where the standard library raises `binascii.Error`, so does the
  port, fetched from the real `binascii` at import, so an existing
  `except binascii.Error` keeps working. Where it raises a plain `ValueError`, as
  the 85 decoders do, the port does too.
- **The lenient behavior.** `b64decode` still discards characters outside the
  alphabet unless you pass `validate=True`, `b32decode` still accepts nonzero pad
  bits, and the 85 family keeps the standard library's shortcuts and its accidents
  alike. This is not the strict codec API.
- **The interpreter.** `binascii.a2b_base64` changed its reading of stray padding
  in CPython 3.12.4, 3.13.13 and 3.14.4. The port carries all three readings and
  picks one from `Py_Version` at import, so it agrees with the `base64` next to it
  on every patch release.
- **The surface.** All 22 functions on CPython 3.13 and later, 20 before it, where
  the standard library itself has no `z85encode` or `z85decode`.

## Python 3.15

CPython 3.15 rebuilt `base64` as a thin shell over new C functions in
`binascii`, and the module's surface moved with it: every function takes the
keywords that release added (`padded` and `wrapcol` on the encoders,
`padded`, `ignorechars` and `canonical` on the decoders, `wrapcol` on
`b16encode` and the 85 encoders, `pad` on `z85encode`), the length checks on
`altchars` and `map01` raise `ValueError` where they used to assert,
`urlsafe_b64decode` accepts unpadded input by default and warns about a stray
`+` or `/`, a one-character 85 tail is rejected instead of decoding to
nothing, and the 85 family raises `binascii.Error` rather than a plain
`ValueError`. The drop-in carries all of it: on 3.15 the port of that
`binascii` runs underneath, with its exact messages, argument order and
warnings, and CPython 3.15's own `test_base64` runs against it. The choice is
made at import from the running interpreter, so one install behaves like the
`base64` next to it on every release.

## Where it differs

Reaching a difference takes an argument that breaks its own contract. The `str`
subclasses and lazy-string proxies that real code passes go through `encode`
exactly as they do in the standard library.

- A `casefold`, `map01`, `altchars` or `validate` object that resizes the input
  buffer from its own `__bool__` or `encode` raises `BufferError`. Holding that
  buffer instead of copying it up front is what makes the port allocation-free,
  and refusing a resize is the safe direction.
- An input is judged by the buffer it offers rather than by the methods the
  standard library would call on it, so an object claiming to be `bytes` without
  being one, or a `str` subclass whose `encode` returns neither `bytes` nor
  `bytearray`, can come out differently.
- A flag that is not the plain `bool` or `int` it is meant to be is read a
  different number of times: `foldspaces` once where the standard library reads it
  per group, `adobe` once where it reads it two to four times, and `wrapcol`
  converted once where the standard library threads the object itself through
  `max`, `range` and the slice.

## What importing it costs

- **An extension import.** It pulls in `radixly._core`, which the standard
  library's `base64` never made a program pay for.
- **No subinterpreters.** Importing `_core` inside one raises `ImportError`.
- **No free threading.** The import succeeds, but CPython switches the GIL back on
  for that interpreter and warns, so the rest of the program loses its free
  threading. See {doc}`../guides/subinterpreters`.
- **CPython 3.11 to 3.14 only.** No abi3 wheel and no pure-Python fallback, so an
  interpreter without a wheel means a source build, never a slower `base64`.

## Strict codecs versus the drop-in

The codecs radixly registers are the other contract, and the drop-in never reaches
them. {doc}`../codecs/base16`, {doc}`../codecs/base32`, {doc}`../codecs/base32hex`,
{doc}`../codecs/base64`, {doc}`../codecs/base64url`, {doc}`../codecs/base85` and
{doc}`../codecs/z85` reject characters outside the alphabet, wrong padding, nonzero
pad bits and, for the single-case alphabets, the other case, so one payload has
exactly one accepted spelling and anything else raises
{class}`~radixly.DecodeError`. Same C underneath, two contracts on top.
