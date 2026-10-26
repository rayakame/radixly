# Standard library drop-in

`radixly.compat.base64` is the standard library's `base64` module with the same
names, arguments, results and errors, every function in C.

```python
from radixly.compat import base64

base64.b32encode(b"hello")           # b'NBSWY3DP'
base64.b32decode("nbswy3dp", True)   # b'hello'
```

::::{grid} 1 3 3 3
:gutter: 2

:::{grid-item-card} Same contract
Results, exceptions, messages, warnings and `__context__` chains match the
running interpreter's `base64`. CPython's own `test_base64` passes against it.
:::

:::{grid-item-card} All 22 functions
`b16` to `z85`, the legacy four included. `z85encode` and `z85decode` from
3.13, where the standard library has them.
:::

:::{grid-item-card} 3.11 to 3.15
One wheel per interpreter, the right behavior chosen at import, the keywords
3.15 added (`padded`, `wrapcol`, `ignorechars`, `canonical`) included.
:::

::::

## Should you swap?

Speed is the only reason. The chart and the table are the committed benchmark
record, the drop-in timed against the standard library of the interpreter it
was measured on, on the same input.

```{include} benchmarks/compat.md
```

The gain is largest where the standard library loops byte by byte, and smallest
where it already runs a scalar C kernel over large input: there the drop-in
saves the call overhead, which shows on short input. Before 3.15 the `b32` and
85 functions are pure Python in the standard library, and the swap is worth
around a hundred times. The file pair `encode` and `decode` is slower on
purpose: it makes the standard library's `read`, `readline` and `write` calls
one for one, so a file object sees the same traffic.

New code wants the strict codecs instead: {doc}`guides/choosing-a-codec`.

## Where it differs

Reaching a difference takes an argument that breaks its own contract.

- A flag object whose `__bool__` resizes the input buffer raises `BufferError`
  where the standard library reads whatever is left.
- An input is judged by the buffer it offers, not by the methods the standard
  library would call on it.
- `foldspaces`, `adobe` and `wrapcol` are read once where the standard library
  reads them per group.

:::{dropdown} Swapping for code you cannot edit
Put the port into `sys.modules` before anything imports `base64`:

```python
import sys

import radixly.compat.base64

sys.modules["base64"] = radixly.compat.base64
```

The surface is `base64.__all__`: `MAXLINESIZE`, `MAXBINSIZE`, `bytes_types`
and `main` are not carried over, so code reading them breaks, and
`runpy.run_module("base64")` has no `main` to run.
:::

:::{dropdown} What changed in 3.15
CPython 3.15 rebuilt `base64` over new C functions in `binascii`. Every
function took the keywords that release added, the `altchars` and `map01`
length checks raise `ValueError` where they used to assert,
`urlsafe_b64decode` accepts unpadded input and warns about a stray `+` or `/`,
a one-character 85 tail is an error, and the 85 family raises
`binascii.Error`. The drop-in does all of it on 3.15 and none of it before.
:::

:::{dropdown} What importing it costs
An extension import, no subinterpreters, and no free threading: the import
succeeds on a free-threaded build but switches the GIL back on. See
{doc}`guides/subinterpreters`.
:::

## Reference

```{eval-rst}
.. automodule:: radixly.compat.base64
   :members:
   :undoc-members:
```
